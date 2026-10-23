"""Public WSGI boundary, publication selection and real streaming semantics."""
import copy
import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import production_app


PRODUCTION = {
    'PITO_STANDALONE': '1',
    'PITO_SITE_MODE': 'production',
    'PITO_PUBLIC_URL': 'https://pitonieuws.nl',
}


class ProductionAppTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, PRODUCTION)
        self.environment.start()
        os.environ.pop('PITO_EDITION_DATE', None)
        os.environ.pop('PITO_WEATHER_CACHE', None)
        os.environ.pop('PITO_LOCAL_TEST', None)
        self.addCleanup(self.environment.stop)
        self.application = production_app.create_app()
        self.weather = patch('weather.get', return_value={
            'status': 'unavailable', 'station': 'De Bilt', 'source': 'KNMI',
        })
        self.weather.start()
        self.addCleanup(self.weather.stop)

    def call(self, target='/', method='GET', collect=True, **overrides):
        url = urlsplit(target)
        environ = {
            'REQUEST_METHOD': method, 'HTTP_HOST': 'pitonieuws.nl',
            'PATH_INFO': unquote(url.path), 'RAW_URI': target,
            'QUERY_STRING': url.query, 'REMOTE_ADDR': '127.0.0.1',
            'wsgi.url_scheme': 'https',
        }
        environ.update(overrides)
        result = {}

        def start_response(status, headers):
            result['status'] = int(status.split()[0])
            result['headers'] = dict(headers)

        body = self.application(environ, start_response)
        if collect:
            try:
                result['body'] = b''.join(body)
            finally:
                if hasattr(body, 'close'):
                    body.close()
        else:
            result['body'] = body
        return result

    def temporary_assets(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        static = root / 'static'
        static.mkdir()
        replacement = patch.object(production_app, 'STATIC', static)
        replacement.start()
        self.addCleanup(replacement.stop)
        return root, static

    def test_startup_requires_production_origin_and_standalone(self):
        for key, value in (
            ('PITO_SITE_MODE', 'preview'), ('PITO_PUBLIC_URL', 'http://pitonieuws.nl'),
            ('PITO_PUBLIC_URL', 'https://pitonieuws.nl.evil.test'),
            ('PITO_PUBLIC_URL', 'https://pitonieuws.nl@evil.test'),
            ('PITO_PUBLIC_URL', 'https://pitonieuws.nl/prefix'),
            ('PITO_STANDALONE', '0'), ('PITO_EDITION_DATE', '2026-10-10'),
        ):
            with self.subTest(key=key, value=value), patch.dict(os.environ, {key: value}):
                with self.assertRaises(RuntimeError):
                    production_app.create_app()

    def test_standalone_factory_does_not_read_machine_specific_base_file(self):
        script = '''from pathlib import Path
from unittest.mock import patch
original = Path.read_text
def read_text(path, *args, **kwargs):
    if path.name == 'base.json':
        raise AssertionError('standalone runtime read a machine-specific preview path')
    return original(path, *args, **kwargs)
with patch.object(Path, 'read_text', read_text):
    import production_app
    assert callable(production_app.create_app())
'''
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=production_app.ROOT,
                                env=dict(os.environ), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_policy_change_fails_closed(self):
        with patch.dict(os.environ, {'PITO_SITE_MODE': 'preview'}):
            self.assertEqual(self.call('/nieuws/utrecht')['status'], 503)

    def test_hosts_and_forwarded_host_cannot_override_origin(self):
        for host in ('evil.test', 'localhost:4200', 'pitonieuws.nl.evil.test', ''):
            with self.subTest(host=host):
                response = self.call('/robots.txt', HTTP_HOST=host, HTTP_X_FORWARDED_HOST='pitonieuws.nl')
                self.assertEqual(response['status'], 421)
        self.assertEqual(self.call('/robots.txt', HTTP_HOST='PITONIEUWS.NL:443')['status'], 200)

    def test_https_redirect_trusts_only_loopback_proxy(self):
        response = self.call('/nieuws/utrecht?pagina=2', **{'wsgi.url_scheme': 'http'})
        self.assertEqual(response['status'], 308)
        self.assertEqual(response['headers']['Location'], 'https://pitonieuws.nl/nieuws/utrecht?pagina=2')
        response = self.call('/robots.txt', HTTP_X_FORWARDED_PROTO='https', **{'wsgi.url_scheme': 'http'})
        self.assertEqual(response['status'], 200)
        response = self.call('/robots.txt', HTTP_X_FORWARDED_PROTO='https', REMOTE_ADDR='192.0.2.1', **{'wsgi.url_scheme': 'http'})
        self.assertEqual(response['status'], 308)

    def test_local_test_mode_requires_explicit_flag_host_and_loopback_client(self):
        self.assertEqual(self.call('/robots.txt', HTTP_HOST='127.0.0.1:4201')['status'], 421)
        with patch.dict(os.environ, {'PITO_LOCAL_TEST': '1'}):
            self.application = production_app.create_app()
            response = self.call('/robots.txt', HTTP_HOST='127.0.0.1:4201', **{'wsgi.url_scheme': 'http'})
            self.assertEqual(response['status'], 200)
            self.assertEqual(response['headers']['X-Robots-Tag'], 'noindex, nofollow')
            response = self.call('/robots.txt', HTTP_HOST='127.0.0.1:4201', REMOTE_ADDR='192.0.2.1')
            self.assertEqual(response['status'], 421)
            self.assertEqual(self.call('/robots.txt', HTTP_HOST='evil.test')['status'], 421)
            self.assertEqual(self.call('/robots.txt', HTTP_HOST='localhost:4202')['status'], 421)

    def test_public_requests_cannot_run_preview_writes(self):
        with patch('community.submit') as submit, patch('server.save') as save:
            for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'TRACE'):
                with self.subTest(method=method):
                    response = self.call('/api/community/submit', method)
                    self.assertEqual(response['status'], 405)
                    self.assertEqual(response['headers']['Allow'], 'GET, HEAD')
            submit.assert_not_called()
            save.assert_not_called()

    def test_private_and_diagnostic_routes_are_not_public(self):
        for path in (
            '/nieuws/redactie', '/nieuws/redactie/signalen', '/nieuws/%72edactie',
            '/nieuws/onderzoek', '/nieuws/beeldbibliotheek', '/nieuws/seo-controle',
            '/nieuws/bronberichten', '/nieuws/aanvoerstatus', '/api/news',
            '/api/media-library', '/api', '/data/articles.json', '/server.py',
            '/.env', '/news-static/source-audit/index.html',
            '/news-static/source-audit/clublogos.css', '/news-static/local-audit/01.png',
            '/news-static/header.html', '/news-static/hero-audit-1.html',
        ):
            with self.subTest(path=path):
                self.assertIn(self.call(path)['status'], (400, 404))

    def test_encoded_paths_cannot_reach_private_or_parent_files(self):
        for path in (
            '/news-static/../data/articles.json', '/news-static/%2e%2e/server.py',
            '/news-static/%252e%252e/server.py', '/nieuws/%2572edactie',
            '/news-static%2fsource-audit/index.html', '/news-static/%5cserver.py',
            '/nieuws//redactie', '/news-static/bad%00.css', '/news-static/bad%.css',
            '/nieuws/utrecht%0d%0aInjected:yes',
        ):
            with self.subTest(path=path):
                self.assertEqual(self.call(path)['status'], 400)
        # A real WSGI server already decoded PATH_INFO when raw URI is absent.
        response = self.call('/robots.txt', RAW_URI='', PATH_INFO='/nieuws/%72edactie')
        self.assertEqual(response['status'], 400)

    def test_filters_and_municipal_route_reuse_established_renderer(self):
        with patch('news.home', return_value='Gemeente met filters') as home:
            response = self.call('/nieuws/utrecht/woerden?q=bibliotheek&maand=2026-10&pagina=2')
        self.assertEqual(response['status'], 200)
        self.assertEqual(response['body'], b'Gemeente met filters')
        self.assertEqual(home.call_args.args[0], 'woerden')
        self.assertEqual(home.call_args.args[1], 'bibliotheek')
        self.assertEqual(home.call_args.args[4], '2026-10')
        self.assertEqual(home.call_args.args[6], '2')
        self.assertEqual(response['headers']['X-Robots-Tag'], 'noindex, follow')

    def test_public_feed_cannot_publish_sqlite_records_even_with_approved_flags(self):
        import news
        original_read = news.read
        example = copy.deepcopy(original_read('articles')[0])
        now = datetime.datetime.now(datetime.timezone.utc)
        articles = []
        variants = (
            ('Alleen deze titel is gepubliceerd', 'approved', 'published', now - datetime.timedelta(minutes=5)),
            ('Concepttitel hoort nooit openbaar', 'preview', 'draft', now - datetime.timedelta(minutes=5)),
            ('Ingetrokken titel hoort nooit openbaar', 'approved', 'withdrawn', now - datetime.timedelta(minutes=5)),
            ('Toekomstige titel hoort nooit openbaar', 'approved', 'published', now + datetime.timedelta(days=1)),
        )
        for i, (title, review, publication, stamp) in enumerate(variants):
            article = dict(example, title=title, slug=f'wsgi-fixture-{i}', reviewStatus=review,
                           publicationStatus=publication, webPublishedAt=stamp.isoformat(),
                           sourcePublishedAt=now.date().isoformat(), verifiedAt=now.date().isoformat())
            articles.append(article)
        # SQLite is only private audit history. Even formerly released rows
        # cannot publish to a public route without an actual CMS snapshot.
        with patch('news.read', side_effect=lambda name: [] if name == 'articles' else original_read(name)), \
                patch('publication.read_published', return_value=articles) as legacy_reader, \
                patch.dict(os.environ, {'PITO_STRAPI_URL': '', 'PITO_NEWS_READ_TOKEN': ''}):
            response = self.call('/nieuws/feed.xml')
            legacy_reader.assert_not_called()
        self.assertEqual(response['status'], 200)
        for title, *_ in variants:
            self.assertNotIn(title.encode(), response['body'])

    def test_head_has_get_headers_without_body(self):
        get = self.call('/robots.txt')
        head = self.call('/robots.txt', 'HEAD')
        self.assertEqual(head['status'], get['status'])
        self.assertEqual(head['headers'], get['headers'])
        self.assertEqual(head['body'], b'')
        self.assertIn('Sitemap: https://pitonieuws.nl/', get['body'].decode())
        self.assertIn("frame-ancestors 'none'", head['headers']['Content-Security-Policy'])

    def test_read_only_weather_and_portable_assets_remain_public(self):
        response = self.call('/api/weather')
        self.assertEqual(response['status'], 200)
        self.assertIn(b'"html"', response['body'])
        for path in ('/style.css', '/news-static/pito-icon-180.png',
                     '/preview-assets/c9440ef71f7605f9968e.webp',
                     '/build/assets/poppins-latin-400-normal-cpxAROuN.woff2'):
            with self.subTest(path=path):
                response = self.call(path)
                self.assertEqual(response['status'], 200)
                self.assertTrue(response['body'])
                self.assertIn('max-age=', response['headers']['Cache-Control'])

    def test_static_assets_stream_and_support_range_and_head(self):
        _, static = self.temporary_assets()
        content = bytes(range(256)) * 8192
        (static / 'film.mp4').write_bytes(content)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Must stream static files')):
            response = self.call('/news-static/film.mp4', collect=False)
            self.assertIsInstance(response['body'], production_app.FileChunks)
            chunks = list(response['body'])
        self.assertEqual(response['status'], 200)
        self.assertEqual(b''.join(chunks), content)
        self.assertLessEqual(max(map(len, chunks)), production_app.CHUNK_SIZE)
        self.assertTrue(response['body'].stream.closed)
        partial = self.call('/news-static/film.mp4', HTTP_RANGE='bytes=100-199')
        self.assertEqual(partial['status'], 206)
        self.assertEqual(partial['body'], content[100:200])
        self.assertEqual(partial['headers']['Content-Range'], f'bytes 100-199/{len(content)}')
        self.assertEqual(self.call('/news-static/film.mp4', HTTP_RANGE='bytes=-17')['body'], content[-17:])
        head = self.call('/news-static/film.mp4', 'HEAD', HTTP_RANGE='bytes=100-199')
        self.assertEqual(head['status'], 206)
        self.assertEqual(head['headers']['Content-Length'], '100')
        self.assertEqual(head['body'], b'')
        for value in ('bytes=0-1,4-5', 'bytes=-0', f'bytes={len(content)}-', 'bytes=30-10'):
            with self.subTest(value=value):
                self.assertEqual(self.call('/news-static/film.mp4', HTTP_RANGE=value)['status'], 416)

    def test_static_validators_if_range_and_abort_close(self):
        _, static = self.temporary_assets()
        (static / 'asset.css').write_bytes(b'body { color: blue; }')
        get = self.call('/news-static/asset.css')
        etag = get['headers']['ETag']
        for headers in ({'HTTP_IF_NONE_MATCH': etag}, {'HTTP_IF_NONE_MATCH': 'W/' + etag},
                        {'HTTP_IF_MODIFIED_SINCE': get['headers']['Last-Modified']}):
            with self.subTest(headers=headers):
                response = self.call('/news-static/asset.css', **headers)
                self.assertEqual(response['status'], 304)
                self.assertEqual(response['body'], b'')
        response = self.call('/news-static/asset.css', HTTP_RANGE='bytes=0-3', HTTP_IF_RANGE='"old-version"')
        self.assertEqual(response['status'], 200)
        self.assertEqual(response['body'], get['body'])
        response = self.call('/news-static/asset.css', collect=False)
        response['body'].close()
        self.assertTrue(response['body'].stream.closed)

    def test_wsgi_file_wrapper_is_used_only_for_complete_files(self):
        _, static = self.temporary_assets()
        content = b'content for a native WSGI file wrapper'
        (static / 'asset.css').write_bytes(content)
        calls = []

        def wrapper(stream, chunk_size):
            calls.append(chunk_size)
            return production_app.FileChunks(stream, len(content))

        response = self.call('/news-static/asset.css', **{'wsgi.file_wrapper': wrapper})
        self.assertEqual(response['body'], content)
        self.assertEqual(calls, [production_app.CHUNK_SIZE])
        response = self.call('/news-static/asset.css', HTTP_RANGE='bytes=0-2', **{'wsgi.file_wrapper': wrapper})
        self.assertEqual(response['body'], content[:3])
        self.assertEqual(calls, [production_app.CHUNK_SIZE])

    def test_static_symlinks_cannot_escape_root_and_json_is_explicit(self):
        root, static = self.temporary_assets()
        (root / 'private.css').write_text('secret')
        (static / 'leak.css').symlink_to(root / 'private.css')
        (static / 'internal.json').write_text('{"private":true}')
        (static / 'utrecht-boundaries.json').write_text('{"type":"FeatureCollection"}')
        self.assertEqual(self.call('/news-static/leak.css')['status'], 404)
        self.assertEqual(self.call('/news-static/internal.json')['status'], 404)
        self.assertEqual(self.call('/news-static/utrecht-boundaries.json')['status'], 200)


if __name__ == '__main__':
    unittest.main()
