"""Private evidence/history CLI. Does not publish anything to the public website.

Public publication and withdrawal must be performed in Strapi. These local
commands remain for audit history and migration; SQLite is never a web source.

Examples:
  python3 scripts/publish_news.py validate evidence.json
  python3 scripts/publish_news.py submit evidence.json --actor writer
  python3 scripts/publish_news.py review ID --actor 'Naam redacteur' --note 'Bronnen vergeleken' --confirm-human-checks
  python3 scripts/publish_news.py publish ID --actor 'Naam redacteur'
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publication import PublicationStore, PublicationError, REVIEW_CHECKS, validate_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default=str(Path(__file__).resolve().parents[1]/'data'))
    parser.add_argument('--auto-host', action='append', default=[], help='Exacte primaire host toestaan (geen wildcard)')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('validate', 'submit', 'review', 'publish', 'revise', 'retract', 'list', 'audit', 'export'):
        p = sub.add_parser(command)
        if command not in ('list', 'audit', 'export'):
            p.add_argument('target', help='Bewijsbestand voor validate/submit, anders artikel-ID')
        if command in ('submit', 'review', 'publish', 'revise', 'retract'):
            p.add_argument('--actor', required=True)
        if command in ('review', 'revise', 'retract'):
            p.add_argument('--note', required=True)
        if command in ('validate', 'review', 'publish'):
            p.add_argument('--automated', action='store_true')
        if command == 'review':
            p.add_argument('--reject', action='store_true')
            p.add_argument('--confirm-human-checks', action='store_true', help='Bevestig persoonlijke inhoudscontrole op zes punten')
        if command == 'revise':
            p.add_argument('--bundle', required=True)
        if command == 'audit':
            p.add_argument('--id')
    args = parser.parse_args(argv)
    def bundle(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))
    if args.command == 'validate':
        result = validate_bundle(bundle(args.target), automated=args.automated, auto_publish_hosts=args.auto_host)
    else:
        store = PublicationStore(args.data_dir, auto_publish_hosts=args.auto_host)
        if args.command == 'submit':
            result = store.submit(bundle(args.target), actor=args.actor)
        elif args.command == 'review':
            result = store.review(args.target, actor=args.actor, decision='reject' if args.reject else 'approve', note=args.note,
                                  automated=args.automated, checks={k: args.confirm_human_checks for k in REVIEW_CHECKS})
        elif args.command == 'publish':
            result = store.publish(args.target, actor=args.actor, automated=args.automated)
        elif args.command == 'revise':
            result = store.revise(args.target, bundle(args.bundle), actor=args.actor, reason=args.note)
        elif args.command == 'retract':
            result = store.retract(args.target, actor=args.actor, reason=args.note)
        elif args.command == 'list':
            result = store.list()
        elif args.command == 'audit':
            result = store.audit(args.id)
        else:
            result = store.export_articles()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if isinstance(result, dict) and result.get('ok') is False else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (PublicationError, OSError, json.JSONDecodeError) as error:
        print('Publicatie niet uitgevoerd: ' + str(error), file=sys.stderr)
        sys.exit(1)
