"""CMS adapter/cache contracts and the actual public WSGI renderers.

These tests use controlled clocks and an authenticated local HTTP contract
server. The separate Strapi harness proves the real CMS, including D&P.
"""
from copy import deepcopy
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import news
import strapi_news as cms


NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def article(**changes):
    stamp = (NOW-dt.timedelta(minutes=1)).isoformat()
    result = {'id': 'cms-document-1', 'documentId': 'cms-document-1', 'slug': 'lokale-cms-test',
              'title': 'AFZONDERLIJKE LOKALE CMS TEST', 'summary': 'Dit is gecontroleerde testinhoud voor Utrecht.',
              'body': 'Eerste eigen testalinea.\n\nTweede eigen testalinea.', 'category': 'Samenleving',
              'municipalities': ['utrecht'], 'provinceWide': False, 'sourceUrl': 'https://www.utrecht.nl/test',
              'sourceName': 'Gemeente Utrecht', 'sourcePublishedAt': NOW.date().isoformat(),
              'eventDate': NOW.date().isoformat(), 'verifiedAt': stamp, 'reviewStatus': 'approved',
              'reviewer': 'PRIVATE REVIEWER', 'reviewNote': 'PRIVATE REVIEW NOTE', 'rights': 'PRIVATE RIGHTS DOSSIER',
              'privateEvidence': {'body': 'PRIVATE FULL SOURCE BODY'}, 'author': 'Lokale testredactie',
              'firstPublishedAt': stamp, 'lastPublishedAt': stamp, 'publishedAt': stamp, 'updatedAt': stamp}
    result.update(changes)
    return result


def payload(articles=None, redirects=None, now=NOW):
    articles = [article()] if articles is None else articles
    redirects = redirects or []
    return {'data': {'articles': articles, 'redirects': redirects}, 'meta': {
        'schemaVersion': 1, 'complete': True, 'generatedAt': now.isoformat(), 'revision': 'a'*64,
        'total': len(articles), 'articleCount': len(articles), 'redirectCount': len(redirects)}}


class ControlledClock:
    def __init__(self): self.elapsed = 0
    def monotonic(self): return self.elapsed
    def wall(self): return NOW+dt.timedelta(seconds=self.elapsed)
    def advance(self, seconds): self.elapsed += seconds


class SnapshotTests(unittest.TestCase):
    def reader(self, fetch):
        self.clock = ControlledClock()
        return cms.SnapshotReader(fetch, self.clock.monotonic, self.clock.wall)

    def test_private_fields_never_enter_public_mapping(self):
        public = cms.validate_snapshot(payload(), NOW).articles[0]
        text = json.dumps(public)
        for secret in ('PRIVATE REVIEWER', 'PRIVATE REVIEW NOTE', 'PRIVATE RIGHTS DOSSIER', 'PRIVATE FULL SOURCE BODY'):
            self.assertNotIn(secret, text)
        self.assertEqual(public['webPublishedAt'], public['firstPublishedAt'])
        self.assertEqual(public['id'], public['documentId'])

    def test_only_whole_complete_unpaginated_snapshots_activate(self):
        bad = []
        row = payload(); row['meta']['complete'] = False; bad.append(row)
        row = payload(); del row['meta']['articleCount']; bad.append(row)
        row = payload(); row['meta']['total'] = 2; bad.append(row)
        row = payload(); row['meta']['pagination'] = {'page': 1, 'pageCount': 2}; bad.append(row)
        row = payload(); row['data']['articles'].append(article(documentId='second-document', slug='second-test', body=None)); row['meta'].update(total=2, articleCount=2); bad.append(row)
        for invalid in bad:
            with self.subTest(invalid=invalid):
                with self.assertRaises(cms.StrapiNewsError): cms.validate_snapshot(invalid, NOW)

    def test_drafts_unapproved_duplicates_and_wrong_municipality_fail_closed(self):
        for rows in ([article(publishedAt=None)], [article(reviewStatus='needs_review')],
                     [article(), article(slug='duplicate-document')],
                     [article(), article(documentId='different-document')],
                     [article(municipalities=['provincie-utrecht'])], [article(municipalities=[])]):
            with self.subTest(rows=rows):
                with self.assertRaises(cms.StrapiNewsError): cms.validate_snapshot(payload(rows), NOW)
        self.assertTrue(cms.validate_snapshot(payload([article(municipalities=[], provinceWide=True)]), NOW))

    def test_rich_text_is_plain_text_and_escaped_by_renderer(self):
        a = cms.validate_snapshot(payload([article(body='<script>secret()</script>')]), NOW).articles[0]
        self.assertIn('&lt;script&gt;', news.newsroom.article_body(a))
        self.assertNotIn('<script>', news.newsroom.article_body(a))
        with self.assertRaises(cms.StrapiNewsError): cms.validate_snapshot(payload([article(body=[{'type': 'paragraph'}])]), NOW)

    def test_unknown_image_rights_do_not_expose_photo(self):
        image = {'url': 'https://example.org/photo.jpg', 'alt': 'Testfoto', 'credit': 'Testfotograaf', 'web_usage_approved': False}
        self.assertNotIn('image', cms.validate_snapshot(payload([article(image=image)]), NOW).articles[0])
        image['web_usage_approved'] = True
        a = cms.validate_snapshot(payload([article(image=image)]), NOW).articles[0]
        self.assertIn('Testfotograaf', news.artwork(a, True))
        self.assertIn('https://example.org/photo.jpg', news.artwork(a))

    def test_cache_refreshes_within_60_seconds_without_events(self):
        calls = []
        def fetch():
            calls.append(self.clock.elapsed)
            return payload([article(title='Correctie' if calls[-1] else 'Oorspronkelijk')], now=self.clock.wall())
        reader = self.reader(fetch)
        self.assertEqual(reader.read().articles[0]['title'], 'Oorspronkelijk')
        self.clock.advance(44)
        self.assertEqual(reader.read().articles[0]['title'], 'Oorspronkelijk')
        self.clock.advance(1)
        self.assertEqual(reader.read().articles[0]['title'], 'Correctie')
        self.assertEqual(calls, [0, 45])

    def test_partial_response_keeps_last_complete_snapshot_then_expires_at_5m(self):
        current = [payload()]
        reader = self.reader(lambda: current[0])
        self.assertEqual(len(reader.read().articles), 1)
        current[0] = payload([]); current[0]['meta']['complete'] = False
        self.clock.advance(45)
        self.assertEqual(reader.read().status, 'stale')
        self.assertEqual(len(reader.read().articles), 1)
        self.clock.advance(254)
        self.assertEqual(len(reader.read().articles), 1)
        self.clock.advance(1)
        self.assertEqual(reader.read().status, 'unavailable')
        self.assertEqual(reader.read().articles, ())
        self.assertEqual(reader.read().redirects, ())

    def test_old_server_snapshot_cannot_restart_5m_budget(self):
        old = payload(now=NOW-dt.timedelta(seconds=290))
        reader = self.reader(lambda: old)
        self.assertEqual(len(reader.read().articles), 1)
        self.clock.advance(10)
        self.assertEqual(reader.read().articles, ())

    def test_complete_empty_response_withdraws_everything_immediately(self):
        current = [payload(redirects=[{'from': 'oude-slug', 'to': 'lokale-cms-test', 'documentId': 'cms-document-1'}])]
        reader = self.reader(lambda: current[0])
        self.assertTrue(reader.read().redirects)
        current[0] = payload([], now=self.clock.wall())
        self.assertEqual(reader.read(force=True).articles, ())
        self.assertEqual(reader.read().redirects, ())
        # A process restart reads the current CMS; no persisted article revival.
        restarted = cms.SnapshotReader(lambda: current[0], self.clock.monotonic, self.clock.wall)
        self.assertEqual(restarted.read().articles, ())

    def test_redirects_only_point_directly_to_current_published_document(self):
        valid = {'from': 'oude-slug', 'to': 'lokale-cms-test', 'documentId': 'cms-document-1'}
        self.assertEqual(cms.validate_snapshot(payload(redirects=[valid]), NOW).redirects, (('oude-slug', 'lokale-cms-test'),))
        for change in ({'from': 'lokale-cms-test'}, {'to': 'deleted-slug'}, {'documentId': 'wrong-document'}):
            with self.assertRaises(cms.StrapiNewsError):
                cms.validate_snapshot(payload(redirects=[dict(valid, **change)]), NOW)
        with self.assertRaises(cms.StrapiNewsError): cms.validate_snapshot(payload(redirects=[valid, valid]), NOW)

    def test_consumers_cannot_mutate_active_snapshot(self):
        reader = self.reader(lambda: payload())
        first = reader.read()
        first.articles[0]['title'] = 'Mutated renderer'
        self.assertNotEqual(reader.read().articles[0]['title'], 'Mutated renderer')

    def test_no_network_configuration_and_no_sqlite_fallback_on_public_site(self):
        with patch.dict(os.environ, {'PITO_SITE_MODE': 'production', 'PITO_PUBLIC_URL': 'https://pitonieuws.nl'}, clear=True), patch('publication.read_published', side_effect=AssertionError('SQLite must not be read')):
            self.assertEqual(news.articles(), [])
            self.assertEqual(cms.snapshot().status, 'not_configured')
            self.assertIn('Nieuws tijdelijk niet beschikbaar', news.layout('Nieuws', '<p>Overzicht</p>'))
        with patch.dict(os.environ, {'PITO_PUBLIC_PREVIEW': '1'}, clear=True):
            self.assertEqual(news.articles(), [])

    def test_own_reporting_and_missing_source_date_keep_honest_labels(self):
        own = article(sourceBased=False, sourceUrl='', sourcePublishedAt=None,
                      sourceName='Eigen verslaggeving PITO', dateNote='Eigen verslaggeving; geen externe bronpublicatiedatum.')
        mapped = cms.validate_snapshot(payload([own]), NOW).articles[0]
        self.assertEqual(mapped['sourcePublishedAt'], '')
        self.assertEqual(cms.validate_snapshot(payload([dict(own, dateNote='')]), NOW).articles[0]['sourcePublishedAt'], '')
        self.assertEqual(news.article_date(mapped), mapped['firstPublishedAt'][:10])
        self.assertTrue(news.ranking.is_recent(mapped))
        with patch('weather.get', return_value={'status': 'unavailable'}):
            html = news.detail(mapped)
        self.assertIn('Eigen verslaggeving PITO', html)
        self.assertNotIn('Bronpublicatie Niet vermeld', html)
        self.assertIn('geen externe bronpublicatiedatum', html)
        undated_source = article(sourcePublishedAt=None, dateNote='De gemeentelijke bronpagina vermeldt geen publicatiedatum.')
        self.assertEqual(cms.validate_snapshot(payload([undated_source]), NOW).articles[0]['sourcePublishedAt'], '')
        with self.assertRaises(cms.StrapiNewsError):
            cms.validate_snapshot(payload([article(sourcePublishedAt=None, dateNote='')]), NOW)

    def test_automatic_authorship_does_not_replace_real_human_review(self):
        mapped = cms.validate_snapshot(payload([article(author='PITO automatische conceptaanvoer',
            authorType='automatic', humanReviewed=True)]), NOW).articles[0]
        self.assertEqual(mapped['authorship']['kind'], 'automated')
        self.assertTrue(mapped['humanReviewed'])
        self.assertNotIn('reviewer', mapped)
        with self.assertRaises(cms.StrapiNewsError):
            cms.validate_snapshot(payload([article(humanReviewed=False)]), NOW)

    def test_amsterdam_calendar_date_at_midnight_and_month_boundary(self):
        self.assertEqual(news.date('2026-10-15T22:30:00Z'), '16-10-2026')
        self.assertEqual(news.date('2026-09-30T22:30:00Z'), '01-10-2026')
        self.assertEqual(news.date('2026-10-15'), '15-10-2026')
        own = {'sourcePublishedAt': '', 'webPublishedAt': '2026-09-30T22:30:00Z'}
        self.assertEqual(news.article_date(own), '2026-10-01')
        source = article(sourcePublishedAt='2026-10-15T22:30:00Z')
        self.assertEqual(cms.validate_snapshot(payload([source]), NOW).articles[0]['sourcePublishedAt'], '2026-10-16')

    def test_one_http_request_remains_on_one_coherent_snapshot(self):
        clock = ControlledClock()
        current = [payload()]
        reader = cms.SnapshotReader(lambda: current[0], clock.monotonic, clock.wall)
        env = {'PITO_STRAPI_URL': 'https://cms.example.org', 'PITO_NEWS_READ_TOKEN': 'test-read'}
        with patch.dict(os.environ, env, clear=True), patch.object(cms, '_reader', reader), patch.object(cms, '_reader_key', ('https://cms.example.org', 'test-read', None)):
            with cms.request_scope():
                self.assertEqual(cms.get()[0][0]['title'], 'AFZONDERLIJKE LOKALE CMS TEST')
                clock.advance(45)
                current[0] = payload([], now=clock.wall())
                self.assertEqual(len(cms.get()[0]), 1)
            with cms.request_scope():
                self.assertEqual(cms.get()[0], [])

    def test_http_requires_https_and_local_test_is_explicit(self):
        env = {'PITO_STRAPI_URL': 'http://127.0.0.1:1337', 'PITO_NEWS_READ_TOKEN': 'read-secret'}
        with self.assertRaises(cms.StrapiNewsError): cms._configuration(env, 'PITO_NEWS_READ_TOKEN')
        env['PITO_LOCAL_TEST'] = '1'
        self.assertEqual(cms._configuration(env, 'PITO_NEWS_READ_TOKEN')[0], env['PITO_STRAPI_URL'])
        env['PITO_STRAPI_URL'] = 'https://user:password@example.org'
        with self.assertRaises(cms.StrapiNewsError): cms._configuration(env, 'PITO_NEWS_READ_TOKEN')


class PublicFlowsTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'PITO_STANDALONE': '1', 'PITO_SITE_MODE': 'production',
            'PITO_PUBLIC_URL': 'https://pitonieuws.nl', 'PITO_STRAPI_URL': 'https://cms.example.org',
            'PITO_NEWS_READ_TOKEN': 'local-test-read-token'}, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)
        cms._reader = None; cms._reader_key = None
        self.clock = ControlledClock()
        self.current = payload()
        self.reader = cms.SnapshotReader(lambda: deepcopy(self.current), self.clock.monotonic, self.clock.wall)
        self.request = patch.object(cms, 'snapshot', side_effect=lambda force=False: self.reader.read(force))
        self.request.start(); self.addCleanup(self.request.stop)
        self.weather = patch('weather.get', return_value={'status': 'unavailable'}); self.weather.start(); self.addCleanup(self.weather.stop)
        import production_app
        self.app = production_app.create_app()

    def call(self, target):
        u = urlsplit(target); result = {}
        def start(status, headers): result.update(status=int(status.split()[0]), headers=dict(headers))
        result['body'] = b''.join(self.app({'REQUEST_METHOD': 'GET', 'HTTP_HOST': 'pitonieuws.nl',
            'PATH_INFO': u.path, 'RAW_URI': target, 'QUERY_STRING': u.query, 'REMOTE_ADDR': '127.0.0.1', 'wsgi.url_scheme': 'https'}, start)).decode()
        return result

    def test_publish_correct_slug_redirect_and_withdraw_all_public_surfaces(self):
        routes = ['/nieuws/utrecht', '/nieuws/utrecht/utrecht', news.seo.topic_path('utrecht', 'Samenleving'),
                  '/nieuws/utrecht?q=AFZONDERLIJKE', '/nieuws/feed.xml', '/nieuws/sitemap.xml', '/nieuws/news-sitemap.xml']
        # Routes that display articles all use the central adapter. The two
        # sitemap formats contain identity URLs rather than all headline text.
        for route in routes:
            result = self.call(route)
            self.assertEqual(result['status'], 200, route)
            self.assertIn('lokale-cms-test', result['body'], route)
            self.assertNotIn('PRIVATE FULL SOURCE BODY', result['body'])
        self.assertNotIn('AFZONDERLIJKE LOKALE CMS TEST', self.call('/nieuws/utrecht/zeist')['body'])
        original_date = self.current['data']['articles'][0]['firstPublishedAt']
        self.clock.advance(45)
        self.current = payload([article(title='GECORRIGEERDE CMS TEST', body='Gecorrigeerde eigen artikelbody.',
            lastPublishedAt=self.clock.wall().isoformat())], now=self.clock.wall())
        detail = self.call('/nieuws/utrecht/artikel/lokale-cms-test')
        self.assertIn('Gecorrigeerde eigen artikelbody.', detail['body'])
        self.assertIn(original_date, detail['body'])
        self.clock.advance(45)
        self.current = payload([article(slug='bewust-nieuwe-slug')], [{'from': 'lokale-cms-test', 'to': 'bewust-nieuwe-slug', 'documentId': 'cms-document-1'}], self.clock.wall())
        redirect = self.call('/nieuws/utrecht/artikel/lokale-cms-test')
        self.assertEqual(redirect['status'], 301)
        self.assertEqual(redirect['headers']['Location'], '/nieuws/utrecht/artikel/bewust-nieuwe-slug')
        self.clock.advance(45)
        self.current = payload([], now=self.clock.wall())
        for route in routes+['/nieuws/utrecht/artikel/bewust-nieuwe-slug', '/nieuws/utrecht/artikel/lokale-cms-test']:
            result = self.call(route)
            self.assertNotIn('AFZONDERLIJKE LOKALE CMS TEST', result['body'], route)
            self.assertNotIn('Gecorrigeerde eigen artikelbody.', result['body'], route)
            if '/artikel/' not in route:self.assertNotIn('/artikel/bewust-nieuwe-slug', result['body'], route)
        self.assertEqual(self.call('/nieuws/utrecht/artikel/bewust-nieuwe-slug')['status'], 404)
        self.assertEqual(self.call('/api/news')['status'], 404)


class TransportTests(unittest.TestCase):
    def test_authenticated_local_contract_server_and_redirect_block(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path, self.headers.get('Authorization')))
                if self.path == '/redirect':
                    self.send_response(302); self.send_header('Location', '/api/pito-news/snapshot'); self.end_headers(); return
                raw = json.dumps(payload()).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(raw)
            def log_message(self, *args): pass
        try:
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        except PermissionError:
            if os.environ.get('PITO_REQUIRE_LOOPBACK_TESTS') == '1': raise
            self.skipTest('Sandbox blokkeert loopback; herhaal met PITO_REQUIRE_LOOPBACK_TESTS=1 en loopbacktoegang')
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            base = 'http://127.0.0.1:'+str(server.server_port)
            result = cms.request_json(base, '/api/pito-news/snapshot', 'separate-read-token')
            self.assertEqual(len(cms.validate_snapshot(result, NOW).articles), 1)
            self.assertEqual(calls[0], ('/api/pito-news/snapshot', 'Bearer separate-read-token'))
            with self.assertRaises(cms.StrapiNewsError): cms.request_json(base, '/redirect', 'separate-read-token')
            self.assertEqual(len(calls), 2)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
