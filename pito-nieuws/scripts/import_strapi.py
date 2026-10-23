"""Explicit legacy draft import into the new CMS; default is a local dry run.

Apply requires --slug for each reviewed legacy item. Existing CMS documents
are returned untouched by the server's idempotent draft ingress.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from strapi_news import DraftClient, StrapiNewsError

FIELDS = ('slug', 'title', 'summary', 'body', 'category', 'municipalities', 'sourceUrl',
          'sourceName', 'sourcePublishedAt', 'eventDate', 'dateNote', 'rights', 'sensitive',
          'impact', 'imageTopics', 'additionalSources', 'ranking')


def payload(article):
    data = {key: article[key] for key in FIELDS if article.get(key) is not None}
    identity = hashlib.sha256((article['sourceUrl']+'\n'+article['slug']).encode()).hexdigest()
    data.update(externalKey='legacy-preview:'+identity, eventKey=article.get('eventKey') or 'legacy:'+identity,
                origin='import', provinceWide=article.get('provinceWide', False), sourceBased=True,
                evidenceReference='legacy-preview:'+identity,
                privateEvidence={'legacySlug': article['slug'], 'requiresEditorialReview': True})
    return {'data': data}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--approved-only', action='store_true', help='Legacy-selectie; verleent geen CMS-goedkeuring')
    parser.add_argument('--slug', action='append', default=[], help='Expliciete oude slug; herhaal voor meerdere concepten')
    args = parser.parse_args(argv)
    records = [row for row in json.loads((ROOT/'data/articles.json').read_text())
               if row['reviewStatus'] in (['approved'] if args.approved_only else ['preview', 'approved'])
               and (not args.slug or row['slug'] in args.slug)]
    if args.slug and set(args.slug) != {row['slug'] for row in records}:
        parser.error('Niet alle opgegeven slugs zijn gevonden in de toegestane selectie')
    plan = [{'slug': row['slug'], 'method': 'idempotent draft only', 'endpoint': '/api/pito-news/drafts',
             'payload': payload(row)} for row in records]
    if not args.apply:
        (ROOT/'strapi/import-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2))
        print(str(len(plan))+' concepten voorbereid; geen netwerkverzoeken.')
        return 0
    if not args.slug:
        parser.error('--apply vereist expliciete --slug selectie; oude previews worden niet blind geïmporteerd')
    client = DraftClient.from_environment()
    if client is None:
        parser.error('Stel PITO_STRAPI_URL en PITO_NEWS_DRAFT_TOKEN server-side in')
    for item in plan:
        result = client.submit_data(item['payload']['data'])
        print(item['slug']+(': concept aangemaakt' if result['created'] else ': bestaand CMS-document behouden'))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except StrapiNewsError:
        print('Conceptaanvoer niet bevestigd; dezelfde expliciete selectie kan veilig opnieuw worden aangeboden.', file=sys.stderr)
        sys.exit(1)
