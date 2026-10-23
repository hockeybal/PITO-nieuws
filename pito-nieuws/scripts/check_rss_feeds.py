"""Bounded live diagnostic for configured RSS endpoints; writes no news items."""
import collections
import concurrent.futures
import datetime
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from intake import parse_feed
from source_security import fetch_public_https, parse_xml

ROOT = Path(__file__).resolve().parents[1]


def main():
    sources = [s for s in json.loads((ROOT / 'data/sources.json').read_text()) if s.get('feed')]
    today = datetime.datetime.now(ZoneInfo('Europe/Amsterdam')).date()
    start = (today - datetime.timedelta(days=14)).isoformat()
    gates = collections.defaultdict(lambda: threading.Semaphore(2))
    for source in sources:
        gates[urlsplit(source['feed']).hostname]
    def check(source):
        result = {'id': source['id'], 'name': source['name'], 'feed': source['feed']}
        try:
            with gates[urlsplit(source['feed']).hostname]:
                raw = fetch_public_https(source['feed'], max_bytes=2_000_000, timeout=25,
                                         user_agent='PITO-feed-intake/1.0')
            tree = parse_xml(raw, 2_000_000)
            root = tree.tag.split('}')[-1].lower()
            if root not in ('rss', 'feed', 'rdf'):
                raise ValueError('Geen RSS/Atom-document')
            entries = [e for e in tree.iter() if e.tag.split('}')[-1] in ('item', 'entry')]
            items, skipped = parse_feed(raw, source, start, today.isoformat())
            result.update(status='ok', entries=len(entries), recentItems=len(items), skipped=skipped)
        except Exception as error:
            result.update(status='error', error=str(error)[:300])
        return result
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        tasks = [pool.submit(check, source) for source in sources]
        for task in concurrent.futures.as_completed(tasks):
            results.append(task.result())
            if len(results) % 20 == 0:
                print('Gecontroleerd:', len(results), '/', len(sources), flush=True)
    report = {'checkedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'window': [start, today.isoformat()], 'sources': sorted(results, key=lambda r: r['id'])}
    target = ROOT / 'data/rss-activation-probe.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    temporary.replace(target)
    print('Resultaat:', dict(collections.Counter(r['status'] for r in results)), flush=True)
    print('Recente bronberichten:', sum(r.get('recentItems', 0) for r in results), flush=True)
    for result in results:
        if result['status'] != 'ok':
            print(result['name'], result['error'], flush=True)


if __name__ == '__main__':
    main()
