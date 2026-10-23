"""Explicit, bounded batch intake for a frozen local-test crawl plan.

Submission reserves its complete URL set before contacting Firecrawl. Polling
and reprocessing saved responses never create another paid job. No writer or
publication action is available here.
"""
import argparse
import collections
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from firecrawl_client import public_url
from newsroom_worker import _atomic_json, extract_article
from runtime_config import load_env_file
from source_archive import SourceArchive
import publication

UUID = re.compile(r'[0-9a-f-]{36}\Z')


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def status_path(value, job_id):
    parsed = urlsplit(value)
    if (parsed.scheme or parsed.netloc) and (parsed.scheme != 'https' or parsed.netloc != 'api.firecrawl.dev'):
        raise ValueError('Firecrawl-paginering verwijst buiten het vaste API-domein')
    expected = '/v2/batch/scrape/'+job_id
    if parsed.path != expected or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('Firecrawl-paginering verwijst buiten de bestaande batch')
    return parsed.path+('?' +parsed.query if parsed.query else '')


def api(method, path, body=None):
    if not re.fullmatch(r'/v2/batch/scrape(?:/[0-9a-f-]{36})?(?:\?[^\s#]*)?', path):
        raise ValueError('Onverwacht Firecrawl-endpoint')
    connection = http.client.HTTPSConnection('api.firecrawl.dev', timeout=40, context=ssl.create_default_context())
    try:
        connection.request(method, path, json.dumps(body).encode() if body is not None else None,
                           {'Authorization': 'Bearer '+os.environ['FIRECRAWL_API_KEY'],
                            'Content-Type': 'application/json', 'Accept': 'application/json'})
        response = connection.getresponse()
        if response.status not in (200, 201):
            raise ValueError('Firecrawl-batch gaf HTTP '+str(response.status))
        if response.getheader('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise ValueError('Firecrawl-batch gaf geen JSON')
        raw = response.read(12_000_001)
        if len(raw) > 12_000_000:
            raise ValueError('Firecrawl-batchantwoord overschrijdt de leeslimiet')
        return json.loads(raw)
    finally:
        connection.close()


def submit(folder):
    path = folder/'batch-jobs.json'
    if path.exists():
        raise ValueError('Bestaande batchreservering behouden; gebruik poll, nooit opnieuw indienen')
    plan = read(folder/'crawl-plan.json')
    checks = read(folder/'preflight.json')['items']
    pilot = {r['url'] for r in read(folder/'pilot-results.json', [])}
    redirects = read(folder/'redirect-checks.json', [])
    gated_hosts = {urlsplit(r['url']).hostname for r in redirects
                   if urlsplit(r.get('redirect', '')).hostname == 'myprivacy.dpgmedia.nl'}
    approved = {r['url']:r for r in checks if r['allowed']}
    groups = collections.defaultdict(list)
    blocked = []
    for entry in plan['entries']:
        url = entry['url']; host = urlsplit(url).hostname
        if host in gated_hosts:
            blocked.append({'url': url, 'status': 'access_gate', 'reason': 'Bronhost verwijst naar DPG-toestemmingspagina; artikeltekst niet ontvangen'})
        elif url not in approved:
            reason = next(r['reason'] for r in checks if r['url'] == url)
            blocked.append({'url': url, 'status': 'blocked', 'reason': reason})
        elif url not in pilot:
            public_url(url)
            groups[host].append(entry)
    lanes = [[], []]
    # A host belongs to one serial lane. One second waitFor also observes the
    # preflight's one-second delay between successive requests to that host.
    for host, entries in sorted(groups.items(), key=lambda item: -len(item[1])):
        if len(entries) > 1 and any(approved[e['url']]['delay'] > 1 for e in entries):
            raise ValueError('Deze bron vereist een afzonderlijke langzame crawl')
        lane = min(lanes, key=len); lane.extend(entries)
    total = sum(map(len, lanes))
    if total+len(pilot) > plan['maxPaidRequests'] or len({e['url'] for lane in lanes for e in lane}) != total:
        raise ValueError('Batchselectie overschrijdt de vastgelegde scope')
    state = {'reservedPages': total, 'pilotReservedPages': len(pilot), 'maxPaidRequests': plan['maxPaidRequests'],
             'createdAt': publication.stamp(publication.utcnow()), 'jobs': [], 'blocked': blocked}
    _atomic_json(path, state)
    with SourceArchive(ROOT/'data') as archive:
        for row in blocked:
            archive.finish(row['url'], publication.utcnow(), row['status'], row['reason'])
    for lane in lanes:
        if not lane: continue
        lane.sort(key=lambda e:e['metadata'].get('sourceTimestamp') or e['metadata'].get('sourcePublishedAt') or '', reverse=True)
        job = {'status': 'submission_reserved', 'urls': [e['url'] for e in lane]}
        state['jobs'].append(job); _atomic_json(path, state)
        result = api('POST', '/v2/batch/scrape', {'urls':job['urls'], 'maxConcurrency':1,
            'ignoreInvalidURLs':False, 'formats':['rawHtml','links'], 'onlyMainContent':False,
            'timeout':25000, 'waitFor':1000, 'maxAge':0, 'storeInCache':False,
            'skipTlsVerification':False, 'parsers':[]})
        identity = result.get('id')
        if result.get('success') is not True or not isinstance(identity, str) or not UUID.fullmatch(identity):
            raise ValueError('Firecrawl-batch niet bevestigd; reservering niet automatisch opnieuw gebruiken')
        job.update(id=identity, status='scraping'); _atomic_json(path, state)
        print(json.dumps({'submittedPages':len(lane), 'jobNumber':len(state['jobs']), 'blockedWithoutExtraPaidScrape':len(blocked)}), flush=True)
        if lane is lanes[0] and lanes[1]: time.sleep(31)


def poll(folder):
    path = folder/'batch-jobs.json'; state = read(path)
    output = folder/'provider-responses'; output.mkdir(mode=0o700, exist_ok=True)
    for job in state['jobs']:
        if not job.get('id'): raise ValueError('Batchindiening onzeker; geen dubbele betaalde opdracht verstuurd')
        target = '/v2/batch/scrape/'+job['id']; visited = set()
        for _ in range(100):
            if target in visited: break
            visited.add(target); result = api('GET', target)
            if not isinstance(result.get('data'), list): raise ValueError('Batchdata ontbreekt')
            for page in result['data']:
                metadata = page.get('metadata') or {}; url = metadata.get('sourceURL')
                if url not in job['urls']: raise ValueError('Batch gaf een andere bronidentiteit terug')
                saved = output/(hashlib.sha256(url.encode()).hexdigest()+'.json')
                if not saved.exists(): _atomic_json(saved, page); saved.chmod(0o600)
            job.update(status=result.get('status'), completed=result.get('completed'), total=result.get('total'), creditsUsed=result.get('creditsUsed'))
            _atomic_json(path, state)
            following = result.get('next')
            if not following: break
            target = status_path(following, job['id'])
        print(json.dumps({k:job.get(k) for k in ('status','total','completed','creditsUsed')}), flush=True)
    return state


def process(folder):
    plan = read(folder/'crawl-plan.json'); entries = {e['url']:e for e in plan['entries']}
    results = []; now = publication.utcnow()
    with SourceArchive(ROOT/'data') as archive:
        for saved in sorted((folder/'provider-responses').glob('*.json')):
            page = read(saved); meta = page.get('metadata') or {}; url = meta.get('sourceURL')
            if url not in entries: raise ValueError('Bronantwoord staat niet in de bevroren selectie')
            entry = entries[url]; result = {'url':url}
            try:
                if meta.get('statusCode') != 200 or meta.get('error'):
                    raise ValueError('Bron gaf geen geslaagde artikelpagina (HTTP '+str(meta.get('statusCode'))+')')
                if meta.get('url') and meta['url'].split('#')[0] != url.split('#')[0]:
                    raise ValueError('Bronpagina is omgeleid; bronlink controleren')
                raw = page.get('rawHtml')
                if not isinstance(raw, str) or not raw: raise ValueError('Volledige bron-HTML ontbreekt')
                archive.save_raw(url, raw.encode(), page.get('links') or [], now)
                document = extract_article(raw.encode(), entry['metadata'], now)
                if publication._date(document['publishedAt']) < now-dt.timedelta(days=14):
                    result['status'] = 'outside_window'; archive.finish(url, now, 'outside_window')
                else:
                    document['reader'] = 'firecrawl'
                    result.update(status='collected', revision=archive.save(url, document, now), title=document['title'], publishedAt=document['publishedAt'])
            except (ValueError, TypeError, KeyError) as error:
                status = 'index' if entry['kind'] == 'seed' and page.get('links') else 'needs_extraction'
                result.update(status=status, reason=str(error)[:300])
                archive.finish(url, now, status, result['reason'])
            results.append(result)
    _atomic_json(folder/'processed-results.json', results)
    print(json.dumps({'processedResponses':len(results), 'outcomes':dict(collections.Counter(r['status'] for r in results))}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('submit','poll','process'))
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args(); load_env_file(args.env_file)
    {'submit':submit, 'poll':poll, 'process':process}[args.mode](args.folder)


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, http.client.HTTPException) as error:
        print('Batchbewerking gestopt: '+(str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
