"""Run bounded source-to-article processing. Default: unpublished concepts only."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsroom_worker import NewsroomWorker, WorkerError
from runtime_config import load_env_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default=str(Path(__file__).resolve().parents[1]/'data'))
    parser.add_argument('--limit', type=int, default=3, help='Maximaal drie writerverzoeken per uitvoering')
    parser.add_argument('--publish', action='store_true', help='Vervallen: de worker levert alleen Strapi-concepten; publiceren gebeurt in het CMS')
    parser.add_argument('--collect-only', action='store_true', help='Alleen echte bronpagina’s uitlezen; geen writer of API-sleutel nodig')
    parser.add_argument('--retry', action='store_true', help='Herbeoordeel ook eerder verwerkte items; geen automatische revisies')
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    report = NewsroomWorker(args.data_dir).run(limit=args.limit, publish=args.publish, retry=args.retry, collect_only=args.collect_only)
    # Only operational counters go to the journal, never source bodies/provider output.
    print(json.dumps({k: report[k] for k in ('runAt', 'mode', 'writerConfigured', 'writerRequests', 'availableCandidates', 'statuses', 'published', 'remainingCandidates', 'strapiConfigured', 'draftSync')}, ensure_ascii=False))
    return 1 if report['statuses'].get('processing_error') or report['draftSync']['errors'] else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (WorkerError, OSError, ValueError):
        print('Redactionele verwerking niet uitgevoerd; controleer de lokale configuratie en private statusbestanden.', file=sys.stderr)
        sys.exit(1)
