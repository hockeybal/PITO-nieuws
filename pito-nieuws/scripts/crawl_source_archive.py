"""Collect source articles first, without any Grok/OpenAI requests or publication."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive_crawler import ArchiveCrawler
from runtime_config import load_env_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parents[1]/'data')
    parser.add_argument('--discover-only', action='store_true', help='Nieuwsfeeds lezen en crawlwachtrij maken; geen betaald Firecrawl-verzoek')
    parser.add_argument('--collect-only', action='store_true', help='Bestaande wachtrij vervolgen; bronnen niet opnieuw ontdekken')
    parser.add_argument('--all-sources', action='store_true', help='Ook de handmatige/inactieve bronverwijzingen onderzoeken; CMS-instellingen blijven gelijk')
    parser.add_argument('--source', action='append')
    args = parser.parse_args()
    if args.discover_only and args.collect_only: parser.error('Kies één crawlmodus')
    load_env_file(args.env_file)
    report = ArchiveCrawler(args.data_dir).run(not args.collect_only, not args.discover_only, args.source, args.all_sources)
    print(json.dumps({k: report[k] for k in ('runAt','status','sourcesSelected','windowDays','newLinks','firecrawlRequests','remaining','writerRequests','published')} |
                     {'queue': report['archive']['queue'], 'documents': report['archive']['documents']}, ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError):
        print('Crawl niet uitgevoerd; controleer Strapi, instellingen en het privé-crawlrapport.', file=sys.stderr)
        sys.exit(1)
