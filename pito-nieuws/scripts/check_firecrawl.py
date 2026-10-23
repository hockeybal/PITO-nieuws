"""One real source + Firecrawl request, isolated evidence store, no model/publication."""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import newsroom_worker as worker
from firecrawl_client import FirecrawlClient
from runtime_config import load_env_file
from scripts.intake import parse_feed
from scripts.source_security import fetch_public_https


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--source', default='amersfoort-live')
    parser.add_argument('--url', help='Een specifieke artikelpagina binnen de gekozen bron')
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    sources = json.loads((worker.ROOT/'data/sources.json').read_text())
    source = next(row for row in sources if row['id'] == args.source)
    source = dict(source, reader='firecrawl')
    now = dt.datetime.now(dt.timezone.utc)
    if args.url:
        row = {'sourceId': source['id'], 'sourceUrl': args.url}
    else:
        raw = fetch_public_https(source['feed'], max_bytes=2_000_000, timeout=20, max_redirects=0, user_agent=worker.USER_AGENT)
        rows, _ = parse_feed(raw, source, (now-dt.timedelta(days=14)).date().isoformat(), now.date().isoformat())
        if not rows:
            raise ValueError('Geen recent bronbericht; geef een expliciete artikel-URL op')
        row = sorted(rows, key=lambda item: item['sourcePublishedAt'], reverse=True)[0]
    data = Path(tempfile.mkdtemp(prefix='pito-firecrawl-live-'))
    client = FirecrawlClient.from_environment()
    client.max_requests = 1
    reader = worker.NewsroomWorker(data, environment={}, sources=[source], firecrawl=client)
    worker._resolve_source(row, reader.sources)
    document, delay = reader._fetch_document(row, now, {})
    worker._atomic_json(data/'newsroom/real-source.json', dict(document, sourceUrl=row['sourceUrl']))
    result = {'checkedAt': now.isoformat(), 'status': 'ok', 'sourceId': source['id'], 'sourceUrl': row['sourceUrl'],
              'title': document['title'], 'sourcePublishedAt': document['publishedAt'], 'dateEvidence': document['dateEvidence'],
              'bodyCharacters': len(document['body']), 'sha256': document['sha256'], 'firecrawlRequests': client.requests,
              'realFirecrawl': True, 'writerRequests': 0, 'published': 0, 'privateEvidence': str(data/'newsroom/real-source.json')}
    worker._atomic_json(worker.ROOT/'reports/firecrawl-live.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, StopIteration) as error:
        # These errors originate in the validated source/Firecrawl readers;
        # never reflect arbitrary network or provider response bodies.
        print('Firecrawl-broncontrole niet voltooid: '+(str(error) if isinstance(error, worker.WorkerError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
