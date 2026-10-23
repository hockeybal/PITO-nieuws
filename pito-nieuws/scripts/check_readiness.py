"""Read-only readiness report. No endpoint, credential or source body is printed."""
import argparse
import collections
import datetime as dt
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publication
import strapi_news


def read(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def report(data_dir, probe_app=False, probe_news=False):
    data = Path(data_dir)
    legacy = read(data / 'articles.json', [])
    sources = read(data / 'sources.json', [])
    intake = read(data / 'intake-report.json', {})
    worker = read(data / 'newsroom/report.json', {})
    try:
        released = publication.read_published(data)
        database_status = 'ok' if (data / 'publication.sqlite3').exists() else 'not_created'
    except Exception:
        released, database_status = [], 'unavailable'
    writer = bool((os.environ.get('PITO_WRITER_API_KEY') or os.environ.get('OPENAI_API_KEY'))
                  and os.environ.get('PITO_WRITER_MODEL'))
    cms_status = 'not_tested' if strapi_news.configured() else 'not_configured'
    public_articles = []
    if probe_news:
        snapshot = strapi_news.snapshot(force=True)
        cms_status, public_articles = snapshot.status, snapshot.articles
    app = bool(os.environ.get('PITO_APP_CONTENT_URL'))
    app_status = 'not_tested' if app else 'not_configured'
    if probe_app:
        import app_content
        _, app_status = app_content.get()
    allowed = len([v for v in os.environ.get('PITO_AUTO_PUBLISH_HOSTS', '').split(',') if v.strip()])
    statuses = collections.Counter(row.get('status', 'unknown') for row in intake.get('sources', []))
    recent = False
    try:
        stamp = dt.datetime.fromisoformat(intake['runAt'].replace('Z', '+00:00'))
        recent = stamp.tzinfo is not None and dt.timedelta(0) <= dt.datetime.now(dt.timezone.utc)-stamp < dt.timedelta(hours=1)
    except (KeyError, TypeError, ValueError):
        pass
    return {
        'checkedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
        'rss': {'configured': len({s['feed'] for s in sources if s.get('feed')}),
                'lastRunAt': intake.get('runAt'), 'recentRun': recent,
                'lastRunStatuses': dict(statuses)},
        'publications': {'source': 'strapi', 'status': cms_status, 'published': len(public_articles),
                         'privateLegacy': {'database': database_status, 'releases': len(released)},
                         'legacyPreviewOrDraft': sum(a.get('reviewStatus') != 'approved' for a in legacy)},
        'writer': {'configured': writer, 'autoPublishEnabled': False,
                   'draftIngressConfigured': bool(os.environ.get('PITO_STRAPI_URL') and os.environ.get('PITO_NEWS_DRAFT_TOKEN')),
                   'draftSync': worker.get('draftSync'), 'autoPublishHostCount': allowed,
                   'lastRunAt': worker.get('runAt'), 'statuses': worker.get('statuses', {})},
        'app': {'endpointConfigured': app, 'status': app_status, 'connectionTest': 'scripts/check_app_connection.py'},
        'ready': {'publicNews': cms_status == 'connected' and bool(public_articles),
                  'automaticNews': False,
                  'appConnection': app_status=='connected'},
        'notes': ['Configured credentials are not proof of a working external connection.',
                  'Publisher identity, privacy processing and image permissions need factual confirmation.',
                  'Only complete approved/published Strapi snapshots supply public news; local SQLite releases are private history.',
                  'The worker only supplies concepts; automatic publication is disabled.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parents[1]/'data')
    parser.add_argument('--probe-app', action='store_true', help='Test ook de geconfigureerde externe appverbinding')
    parser.add_argument('--probe-news', action='store_true', help='Test de geconfigureerde Strapi-nieuwssnapshot')
    args = parser.parse_args()
    result = report(args.data_dir, args.probe_app, args.probe_news)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ready']['publicNews'] and (not args.probe_app or result['ready']['appConnection']) else 2


if __name__ == '__main__':
    sys.exit(main())
