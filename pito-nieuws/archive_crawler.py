"""Collect first: resumable fourteen-day source crawl, independent of any writer."""
import concurrent.futures
import datetime as dt
import fcntl
import os
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit

import publication
from firecrawl_client import FirecrawlClient
from newsroom_worker import NewsroomWorker, WorkerError, extract_article, _atomic_json, _resolve_source
from scripts.intake import canonical, parse_feed
from scripts.source_security import fetch_public_https
from source_archive import SourceArchive
from source_registry import SourceRegistryClient


class ArchiveCrawler:
    def __init__(self, data_dir, environment=None, registry=None, fetcher=None, firecrawl=None, now=None):
        self.data_dir = Path(data_dir)
        self.environment = os.environ if environment is None else environment
        self.registry = registry or SourceRegistryClient.from_environment(self.environment)
        self.fetcher = fetcher or fetch_public_https
        self.firecrawl = firecrawl
        self.clock = now or publication.utcnow
        self.private = self.data_dir/'newsroom'; self.private.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _feed(self, source, now):
        try:
            raw = self.fetcher(source['feed'], max_bytes=2_000_000, timeout=20, max_redirects=3, user_agent='PITO-feed-intake/1.0')
            rows, skipped = parse_feed(raw, source, (now-dt.timedelta(days=14)).date().isoformat(), now.date().isoformat())
            return source, rows, {'status': 'feed_ok', 'received': len(rows), 'skipped': skipped}
        except Exception as error:
            code = re.search(r'HTTP-status (\d{3})', str(error))
            return source, [], {'status': 'feed_error', 'reason': 'Nieuwsfeed niet bereikbaar of niet bruikbaar',
                                'httpStatus': int(code[1]) if code else None}

    def run(self, discover=True, collect=True, source_ids=None, include_inactive=False):
        with (self.private/'archive-crawler.lock').open('a') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise WorkerError('Er draait al een archiefcrawl') from None
            registry = self.registry.sources()
            if source_ids and set(source_ids)-{s['id'] for s in registry}:
                raise WorkerError('De gekozen bron staat niet in Strapi')
            sources = {s['id']: s for s in registry if (include_inactive or s['active']) and (not source_ids or s['id'] in source_ids)}
            _atomic_json(self.private/'source-registry.json', registry)
            report = {'runAt': publication.stamp(self.clock()), 'windowDays': 14, 'sourcesSelected': len(sources),
                      'includeInactive': include_inactive, 'writerRequests': 0, 'published': 0, 'newLinks': 0, 'items': []}
            with SourceArchive(self.data_dir) as archive:
                if discover:
                    feeds = [s for s in sources.values() if s.get('feed')]
                    host_limits = {urlsplit(s['feed']).hostname: threading.BoundedSemaphore(2) for s in feeds}
                    def read(source):
                        with host_limits[urlsplit(source['feed']).hostname]: return self._feed(source, self.clock())
                    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                        for source, rows, status in pool.map(read, feeds):
                            for row in rows: report['newLinks'] += archive.enqueue(row, source['id'])
                            archive.source_status(source['id'], self.clock(), **status)
                    for source in sources.values():
                        if not source.get('feed'):
                            report['newLinks'] += archive.enqueue({'sourceUrl': source['url'], 'sourceId': source['id']}, source['id'], seed=True)
                            archive.source_status(source['id'], self.clock(), 'seed_queued')
                    archive.refresh(self.clock())
                if collect:
                    client = self.firecrawl or FirecrawlClient.from_environment(self.environment)
                    env = dict(self.environment, PITO_DOCUMENT_SOURCE='live')
                    worker = NewsroomWorker(self.data_dir, environment=env, sources=[dict(s, reader='firecrawl') for s in sources.values()], fetcher=self.fetcher, firecrawl=client)
                    robots, host_next = {}, {}
                    # Paid request budget belongs to the client; also bound free
                    # blocked-URL processing so a damaged queue cannot spin forever.
                    for _ in range(500):
                        if client.requests >= client.max_requests: break
                        now = self.clock()
                        pending = archive.pending(sources, now)
                        entry = next((r for r in pending if host_next.get(urlsplit(r['url']).hostname, now) <= now), None)
                        if entry is None: break
                        source = sources[entry['source_keys'][0]]
                        url, host = entry['url'], urlsplit(entry['url']).hostname
                        item = {'sourceUrl': url, 'sourceId': source['id']}
                        try:
                            row = dict(entry['metadata'], sourceUrl=url, sourceId=source['id'])
                            _resolve_source(row,worker.sources)
                            delay = worker._robots(url, robots)
                            host_next[host] = now+dt.timedelta(seconds=delay)
                            if entry['kind'] == 'seed':
                                page = archive.raw(url,now)
                                if page is None:
                                    page = client.page(url)
                                    archive.save_raw(url,page['rawHtml'],page['links'],now)
                                try: document = extract_article(page['rawHtml'], row, now)
                                except (ValueError, KeyError, TypeError): document = None
                                if document is None:
                                    links = []
                                    for value in page['links']:
                                        try: link = canonical(value)
                                        except ValueError: continue
                                        parsed = urlsplit(link)
                                        prefix = source['articlePathPrefix']
                                        news_path = prefix != '/' or re.search(r'/nieuws|/news|/actueel|/berichten|/20\d\d/', parsed.path, re.I)
                                        if link != url and parsed.hostname in source['articleHosts'] and parsed.path.startswith(prefix) and news_path:
                                            links.append(link)
                                    links = list(dict.fromkeys(links))
                                    for link in links[:source['maxLinks']]:
                                        report['newLinks'] += archive.enqueue({'sourceUrl': link, 'sourceId': source['id']}, source['id'], not_before=publication.stamp(now+dt.timedelta(seconds=delay)))
                                    archive.finish(url, now, 'index_truncated' if len(links)>source['maxLinks'] else 'index')
                                    item.update(status='index', discoveredLinks=min(len(links), source['maxLinks']), truncated=len(links)>source['maxLinks'])
                                elif publication._date(document['publishedAt']) < now-dt.timedelta(days=14):
                                    archive.finish(url, now, 'outside_window'); item['status'] = 'outside_window'
                                else:
                                    document['reader'] = 'firecrawl'
                                    item.update(status='collected', revision=archive.save(url, document, now))
                            else:
                                page = archive.raw(url,now)
                                if page is None:
                                    page={'rawHtml':client.article_html(url)}
                                    archive.save_raw(url,page['rawHtml'],None,now)
                                document=extract_article(page['rawHtml'],row,now)
                                if publication._date(document['publishedAt'])<now-dt.timedelta(days=14):
                                    archive.finish(url,now,'outside_window');item['status']='outside_window'
                                else:
                                    document['reader']='firecrawl'
                                    item.update(status='collected', revision=archive.save(url, document, now))
                        except WorkerError as error:
                            archive.finish(url, now, 'blocked', str(error)[:300]); item.update(status='blocked', reason=str(error)[:300])
                        except Exception:
                            archive.finish(url, now, 'error', 'Bronpagina kon niet volledig en betrouwbaar worden uitgelezen')
                            item.update(status='error', reason='Bronpagina kon niet volledig en betrouwbaar worden uitgelezen')
                        report['items'].append(item)
                    report['firecrawlRequests'] = client.requests
                    report['requestLimit'] = client.max_requests
                else: report['firecrawlRequests'] = 0
                report['archive'] = archive.summary()
                report['remaining'] = sum(report['archive']['queue'].get(s, 0) for s in ('pending', 'error'))
                report['status'] = 'incomplete' if (report['remaining'] or report['archive']['queue'].get('blocked') or report['archive']['queue'].get('index_truncated') or any(s['status']=='feed_error' for s in report['archive']['sources'])) else 'collected'
                report['completedAt'] = publication.stamp(self.clock())
                _atomic_json(self.private/'archive-crawl-report.json', report)
                return report
