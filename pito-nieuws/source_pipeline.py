"""Strapi sources -> RSS/Firecrawl -> private inbox -> reviewed CMS concepts."""
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

import publication
from newsroom_worker import NewsroomWorker, WorkerError, _atomic_json, _load
from scripts.intake import canonical, merge_signal, parse_feed
from scripts.source_security import fetch_public_https
from source_registry import SourceRegistryClient


class SourcePipeline:
    def __init__(self, data_dir, environment=None, registry=None, writer=None, fetcher=None, firecrawl=None, now=None):
        self.data_dir = Path(data_dir)
        self.private = self.data_dir/'newsroom'
        self.private.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.environment = os.environ if environment is None else environment
        self.registry = registry or SourceRegistryClient.from_environment(self.environment)
        self.writer, self.firecrawl = writer, firecrawl
        self.fetcher = fetcher or fetch_public_https
        self.clock = now or publication.utcnow

    def _feed(self, source, now):
        try:
            raw = self.fetcher(source['feed'], max_bytes=2_000_000, timeout=20,
                               user_agent='PITO-feed-intake/1.0', max_redirects=0)
            stats = {}
            items, skipped = parse_feed(raw, source, (now-dt.timedelta(days=14)).date().isoformat(), now.date().isoformat(), stats)
            return {'source': source['id'], 'status': 'ok', 'received': len(items), 'skipped': skipped}, items
        except Exception:
            return {'source': source['id'], 'status': 'error', 'reason': 'Nieuwsfeed niet opgehaald of ongeldig'}, []

    def run(self, limit=3, collect_only=False, retry=False, source_ids=None):
        if type(limit) is not int or not 1 <= limit <= 3:
            raise WorkerError('Per uitvoering zijn één tot drie schrijfconcepten toegestaan')
        with (self.private/'source-pipeline.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise WorkerError('Er draait al een bronnenverwerking') from None
            # Fetch a whole validated registry before any source/provider call.
            # A disabled/deleted source is never restored from the local catalog.
            registry = self.registry.sources()
            if source_ids and set(source_ids)-{s['id'] for s in registry}:
                raise WorkerError('De gekozen bron staat niet in het CMS-register')
            sources = [s for s in registry if s['active'] and s['discovery'] != 'manual' and (not source_ids or s['id'] in source_ids)]
            worker = NewsroomWorker(self.data_dir, writer=self.writer, fetcher=self.fetcher,
                                    now=self.clock, environment=self.environment, sources=sources, firecrawl=self.firecrawl)
            now = self.clock()
            report = {'runAt': publication.stamp(now), 'sourceCount': len(registry), 'activeSources': len(sources),
                      'sources': [], 'autoPublish': False}
            _atomic_json(self.private/'source-registry.json', registry)
            path = self.data_dir/'cms-source-inbox.json'
            inbox = _load(path, [])
            known = {row['sourceUrl']: row for row in inbox}
            feeds = [s for s in sources if s['discovery'] == 'rss']
            # Six feeds at once, at most two requests per upstream host.
            import threading
            host_limits = {urlsplit(s['feed']).hostname: threading.BoundedSemaphore(2) for s in feeds}
            def read_feed(source):
                with host_limits[urlsplit(source['feed']).hostname]:
                    return self._feed(source, now)
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                for status, rows in pool.map(read_feed, feeds):
                    status['added'] = sum(merge_signal(known, inbox, row, report['runAt']) for row in rows)
                    report['sources'].append(status)
            discovery = _load(self.private/'source-discovery.json', {})
            robots = {}
            for source in (s for s in sources if s['discovery'] == 'page'):
                status = {'source': source['id'], 'added': 0}
                if worker.writer is None and not collect_only:
                    status.update(status='awaiting_writer', reason='Geen betaalde bronlezing zonder ingestelde schrijver of --collect-only')
                elif discovery.get(source['id']) and publication._date(discovery[source['id']]) > now-dt.timedelta(hours=1):
                    status['status'] = 'scheduled'
                else:
                    try:
                        delay = worker._robots(source['url'], robots)
                        links = worker._firecrawl().links(source['url'])
                        accepted = 0
                        for link in dict.fromkeys(links):
                            try:
                                url = canonical(link)
                            except ValueError:
                                continue
                            parsed = urlsplit(url)
                            if parsed.hostname not in source['articleHosts'] or not parsed.path.startswith(source['articlePathPrefix']) or url == canonical(source['url']):
                                continue
                            row = {'id': hashlib.sha256(url.encode()).hexdigest()[:20], 'sourceUrl': url,
                                   'sourceId': source['id'], 'sourceIds': [source['id']], 'sourceTitle': '',
                                   'sourcePublishedAt': None, 'sourceMunicipality': source.get('municipality') or '',
                                   'municipalityCandidates': source['coverageCandidates'], 'discovery': 'page',
                                   'discoveredAt': report['runAt'], 'notBefore': publication.stamp(now+dt.timedelta(seconds=delay)),
                                   'fingerprint': hashlib.sha256(url.encode()).hexdigest(), 'status': 'needs_review'}
                            if url not in known:
                                inbox.append(row); known[url] = row; status['added'] += 1
                            accepted += 1
                            if accepted >= source['maxLinks']:
                                break
                        discovery[source['id']] = report['runAt']
                        status.update(status='ok', selected=accepted)
                    except Exception:
                        status.update(status='error', reason='Bronlinks niet opgehaald; controleer robots, Firecrawl en broninstellingen')
                report['sources'].append(status)
            _atomic_json(self.private/'source-discovery.json', discovery)
            _atomic_json(path, inbox)
            report['worker'] = worker.run(limit=limit, collect_only=collect_only, retry=retry)
            report['firecrawlRequests'] = worker.firecrawl.requests if worker.firecrawl else 0
            report['status'] = 'error' if (any(s['status'] == 'error' for s in report['sources']) or
                                           report['worker']['draftSync']['errors'] or
                                           any(report['worker']['statuses'].get(k) for k in ('source_blocked', 'processing_error'))) else 'ok'
            report['completedAt'] = publication.stamp(self.clock())
            _atomic_json(self.private/'source-pipeline-report.json', report)
            return report
