"""Read sources from Strapi and send bounded, unpublished article concepts back."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_pipeline import SourcePipeline
from runtime_config import load_env_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parents[1]/'data')
    parser.add_argument('--limit', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--retry', action='store_true')
    parser.add_argument('--env-file', type=Path, help='Privé-instellingenbestand (rechten 600)')
    parser.add_argument('--source', action='append', help='Alleen deze CMS-broncode verwerken; herhaal voor meerdere bronnen')
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    report = SourcePipeline(args.data_dir).run(args.limit, args.collect_only, args.retry, args.source)
    # Operational counters only, no provider text, tokens, or source bodies.
    print(json.dumps({k: report[k] for k in ('runAt', 'status', 'sourceCount', 'activeSources', 'firecrawlRequests', 'autoPublish')} |
                     {'draftSync': report['worker']['draftSync'], 'statuses': report['worker']['statuses']}, ensure_ascii=False))
    return 1 if report['status'] == 'error' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError):
        print('Bronnenverwerking niet gestart: controleer Strapi-bronnenregister en instellingen. Geen lokale terugval gebruikt.', file=sys.stderr)
        sys.exit(1)
