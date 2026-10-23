"""Grok writes concepts from saved source evidence; no Firecrawl or feed requests."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsroom_worker import NewsroomWorker
from runtime_config import load_env_file
from source_registry import SourceRegistryClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parents[1]/'data')
    parser.add_argument('--limit', type=int, choices=(1,2,3), default=1)
    parser.add_argument('--source', action='append')
    args = parser.parse_args(); load_env_file(args.env_file)
    env = dict(os.environ, PITO_DOCUMENT_SOURCE='archive')
    sources = SourceRegistryClient.from_environment(env).sources()
    if args.source and set(args.source)-{s['id'] for s in sources}: raise ValueError('Onbekende bron')
    sources = [s for s in sources if s['active'] and (not args.source or s['id'] in args.source)]
    report = NewsroomWorker(args.data_dir, environment=env, sources=sources).run(limit=args.limit)
    print(json.dumps({k:report[k] for k in ('mode','writerConfigured','writerRequests','statuses','firecrawlRequests','draftSync','published')},ensure_ascii=False))
    return 1 if report['draftSync']['errors'] or any(report['statuses'].get(s) for s in ('processing_error','writer_error','source_blocked')) else 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError,ValueError):
        print('Artikelverwerking niet gestart; controleer de Grok-instellingen en het bronarchief.',file=sys.stderr);sys.exit(1)
