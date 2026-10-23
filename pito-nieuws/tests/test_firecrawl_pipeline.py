"""Provider failures, source management and draft-only pipeline behavior."""
from copy import deepcopy
import datetime as dt
import json
from pathlib import Path
import socket
import sys
import tempfile
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from firecrawl_client import FirecrawlClient, FirecrawlError, public_url
import newsroom_worker as w
import publication
from source_registry import SourceRegistryClient, import_record
from source_pipeline import SourcePipeline
from runtime_config import load_env_file
from test_newsroom_worker import Writer, html_fixture
from test_publication import NOW


def source(**changes):
    row = {'sourceKey': 'utrecht', 'name': 'Gemeente Utrecht', 'url': 'https://www.utrecht.nl/nieuws/',
           'feed': 'https://www.utrecht.nl/feed', 'kind': 'Gemeente', 'active': True,
           'reader': 'firecrawl', 'discovery': 'rss', 'articleHosts': ['www.utrecht.nl'],
           'municipality': 'utrecht', 'coverageCandidates': ['utrecht'], 'articlePathPrefix': '/nieuws/', 'maxLinks': 5}
    row.update(changes)
    return row


def registry(rows):
    return SourceRegistryClient('https://cms.example', 'source-token', transport=lambda *args: {
        'data': deepcopy(rows), 'meta': {'complete': True, 'schemaVersion': 1, 'total': len(rows)}})


class FakeFirecrawl:
    def __init__(self, **options):
        self.calls = []
        def transport(token, body):
            self.calls.append(body)
            result = {'success': True, 'data': {'metadata': {'statusCode': 200, 'sourceURL': body['url']}}}
            if body['formats'] == ['links']:
                result['data']['links'] = ['https://evil.example/nieuws/vals', 'https://www.utrecht.nl/contact',
                                          'https://www.utrecht.nl/nieuws/boekenmarkt']
            else:
                result['data']['rawHtml'] = html_fixture().decode()
            return result
        self.client = FirecrawlClient('private-test-token', transport=transport, validate_url=lambda u: u, **options)


class FirecrawlTests(unittest.TestCase):
    def test_v2_reader_requests_fresh_html_with_tls_and_without_image_parsing(self):
        fake = FakeFirecrawl()
        raw = fake.client.article_html('https://www.utrecht.nl/nieuws/boekenmarkt')
        self.assertIn(b'<article>', raw)
        body = fake.calls[0]
        self.assertEqual(['rawHtml'], body['formats'])
        self.assertFalse(body['skipTlsVerification'])
        self.assertFalse(body['storeInCache'])
        self.assertEqual(0, body['maxAge'])
        self.assertEqual([], body['parsers'])
        self.assertNotIn('private-test-token', json.dumps(body))

    def test_cache_and_per_execution_budget_prevent_duplicate_paid_requests(self):
        fake = FakeFirecrawl(max_requests=1)
        url = 'https://www.utrecht.nl/nieuws/boekenmarkt'
        self.assertEqual(fake.client.article_html(url), fake.client.article_html(url))
        self.assertEqual(1, fake.client.requests)
        with self.assertRaises(FirecrawlError):
            fake.client.links(url)
        self.assertEqual(1, len(fake.calls))

    def test_wrong_source_redirect_error_and_incomplete_results_are_rejected(self):
        url = 'https://www.utrecht.nl/nieuws/boekenmarkt'
        good = {'success': True, 'data': {'rawHtml': html_fixture().decode(), 'metadata': {'sourceURL': url, 'statusCode': 200}}}
        bad = []
        value = deepcopy(good); value['success'] = False; bad.append(value)
        value = deepcopy(good); value['data']['metadata']['sourceURL'] = 'https://evil.example'; bad.append(value)
        value = deepcopy(good); value['data']['metadata']['url'] = 'https://www.utrecht.nl/login'; bad.append(value)
        value = deepcopy(good); value['data']['metadata']['statusCode'] = 403; bad.append(value)
        value = deepcopy(good); value['data']['metadata']['error'] = 'provider body PRIVATE'; bad.append(value)
        value = deepcopy(good); del value['data']['rawHtml']; bad.append(value)
        bad += [None, {'success': True}]
        for result in bad:
            with self.subTest(result=result):
                client = FirecrawlClient('secret', transport=lambda *args: result, validate_url=lambda u: u)
                with self.assertRaises(FirecrawlError) as error:
                    client.article_html(url)
                self.assertNotIn('PRIVATE', str(error.exception))

    def test_arbitrary_transport_exception_is_redacted(self):
        def fail(*args): raise RuntimeError('PRIVATE TOKEN')
        client = FirecrawlClient('secret', transport=fail, validate_url=lambda u: u)
        with self.assertRaises(FirecrawlError) as error:
            client.article_html('https://www.utrecht.nl/test')
        self.assertNotIn('PRIVATE', str(error.exception))

    def test_private_dns_or_any_mixed_private_answer_is_rejected_before_provider_call(self):
        for addresses in (['127.0.0.1'], ['169.254.169.254'], ['93.184.216.34', '10.0.0.1']):
            answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (a, 443)) for a in addresses]
            with patch('socket.getaddrinfo', return_value=answers), self.assertRaises(FirecrawlError):
                public_url('https://example.org/news')

    def test_missing_configuration_never_makes_a_request(self):
        for env in ({}, {'FIRECRAWL_API_KEY': 'with whitespace'}, {'FIRECRAWL_API_KEY': 'key', 'PITO_FIRECRAWL_MAX_REQUESTS': '10000'}):
            with self.assertRaises(FirecrawlError): FirecrawlClient.from_environment(env)

    def test_user_disabled_crawl_refuses_even_a_configured_key(self):
        with self.assertRaisesRegex(FirecrawlError,'uitgeschakeld'):
            FirecrawlClient.from_environment({'PITO_FIRECRAWL_ENABLED':'0','FIRECRAWL_API_KEY':'test-key'})


class RegistryTests(unittest.TestCase):
    def test_catalog_migration_preserves_all_source_ids_and_does_not_activate_manual_leads(self):
        rows = json.loads((w.ROOT/'data/sources.json').read_text())
        converted = [import_record(s) for s in rows]
        self.assertEqual(len(rows), len(converted))
        self.assertEqual({s['id'] for s in rows}, {s['sourceKey'] for s in converted})
        self.assertTrue(all(s['reader'] == 'firecrawl' for s in converted))
        self.assertTrue(all(s['active'] == bool(s.get('feed')) for s in converted))

    def test_incomplete_duplicate_invalid_and_unknown_municipality_registries_fail(self):
        cases = [([source()], {'complete': False}), ([source()], {'total': 2}), ([source()], {'pagination': {}}),
                 ([source(), source()], {}), ([source(coverageCandidates=['amsterdam'])], {}),
                 ([source(articleHosts=['evil.example'])], {})]
        for rows, changes in cases:
            client = SourceRegistryClient('https://cms.example', 'key', transport=lambda *args: {
                'data': rows, 'meta': {'complete': True, 'schemaVersion': 1, 'total': len(rows), **changes}})
            with self.subTest(changes=changes), self.assertRaises(ValueError): client.sources()


class SecretFileTests(unittest.TestCase):
    def test_private_file_loads_literals_without_shell_expansion(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            file = Path(directory)/'.env.local'
            file.write_text('FIRECRAWL_API_KEY=literal$HOME\nPITO_WRITER_MODEL="test-model"\n')
            file.chmod(0o600)
            load_env_file(file)
            self.assertEqual('literal$HOME', os.environ['FIRECRAWL_API_KEY'])
            self.assertEqual('test-model', os.environ['PITO_WRITER_MODEL'])

    def test_shared_file_or_unrelated_environment_override_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory)/'.env.local'; file.write_text('PATH=/bad\n'); file.chmod(0o600)
            with self.assertRaises(ValueError): load_env_file(file)
            file.write_text('FIRECRAWL_API_KEY=key\n'); file.chmod(0o644)
            with self.assertRaises(ValueError): load_env_file(file)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.fake = FakeFirecrawl()
        self.writer = Writer()
        self.fetches = []
        self.clock = NOW
        self.robots = b'User-agent: *\nAllow: /\n'

    def fetch(self, url, **kwargs):
        self.fetches.append(url)
        if url.endswith('/robots.txt'): return self.robots
        if url.endswith('/feed'):
            return b'<rss><channel><item><title>Boekenmarkt in Utrecht</title><link>https://www.utrecht.nl/nieuws/boekenmarkt</link><pubDate>Fri, 16 Oct 2026 09:00:00 +0000</pubDate></item></channel></rss>'
        raise AssertionError('An article must be fetched by Firecrawl')

    def pipeline(self, rows=None, **kwargs):
        return SourcePipeline(self.data, environment={}, registry=registry([source()] if rows is None else rows),
                              writer=self.writer, fetcher=self.fetch, firecrawl=self.fake.client, now=lambda: self.clock, **kwargs)

    def test_rss_to_firecrawl_to_evidence_backed_private_draft(self):
        result = self.pipeline().run()
        self.assertEqual('ok', result['status'], result)
        self.assertEqual({'drafted': 1}, result['worker']['statuses'])
        self.assertEqual(1, self.fake.client.requests)
        draft = publication.PublicationStore(self.data).list()[0]
        self.assertEqual('draft', draft['status'])
        self.assertEqual([], publication.read_published(self.data))
        self.assertEqual('https://www.utrecht.nl/nieuws/boekenmarkt', draft['bundle']['sources'][0]['url'])
        second = self.pipeline().run()
        self.assertEqual([], second['worker']['items'])
        self.assertEqual(1, len(self.writer.calls))
        self.assertEqual(1, self.fake.client.requests)
        self.assertEqual(1, len(json.loads((self.data/'cms-source-inbox.json').read_text())))

    def test_inactive_manual_and_removed_sources_cannot_reach_providers(self):
        self.pipeline(rows=[source(active=False), source(sourceKey='manual', discovery='manual')]).run()
        self.assertEqual([], self.fetches)
        self.assertEqual(0, self.fake.client.requests)
        self.assertEqual([], self.writer.calls)

    def test_registry_failure_does_not_fall_back_to_local_catalog(self):
        (self.data/'sources.json').write_text(json.dumps([source()]))
        pipeline = self.pipeline()
        with patch.object(pipeline.registry, 'sources', side_effect=ValueError('incomplete')):
            with self.assertRaises(ValueError): pipeline.run()
        self.assertEqual([], self.fetches)
        self.assertFalse((self.data/'cms-source-inbox.json').exists())

    def test_disabling_previously_processed_source_removes_old_inbox_candidates(self):
        self.pipeline().run()
        self.clock += dt.timedelta(days=1)
        result = self.pipeline(rows=[source(active=False)]).run()
        self.assertEqual('ok', result['status'])
        self.assertEqual(0, result['worker']['availableCandidates'])
        self.assertEqual(1, len(self.writer.calls))

    def test_explicit_source_filter_is_checked_against_cms_before_any_source_call(self):
        with self.assertRaises(w.WorkerError): self.pipeline().run(source_ids=['missing'])
        self.assertEqual([], self.fetches)
        result = self.pipeline().run(source_ids=['utrecht'])
        self.assertEqual({'drafted': 1}, result['worker']['statuses'])

    def test_page_discovery_filters_hosts_and_paths_then_defers_until_crawl_delay(self):
        rows = [source(discovery='page')]
        result = self.pipeline(rows).run()
        self.assertEqual(1, result['sources'][0]['added'])
        self.assertEqual([], self.writer.calls)
        inbox = json.loads((self.data/'cms-source-inbox.json').read_text())
        self.assertEqual(1, len(inbox))
        self.assertIsNone(inbox[0]['sourcePublishedAt'])
        self.clock += dt.timedelta(minutes=2)
        result = self.pipeline(rows).run()
        self.assertEqual({'drafted': 1}, result['worker']['statuses'], result)
        self.assertEqual('scheduled', result['sources'][0]['status'])
        self.assertEqual(2, self.fake.client.requests)

    def test_robot_exclusion_stops_firecrawl_and_writer(self):
        self.robots = b'User-agent: *\nDisallow: /\n'
        result = self.pipeline().run()
        self.assertEqual('error', result['status'])
        self.assertEqual({'source_blocked': 1}, result['worker']['statuses'])
        self.assertEqual(0, self.fake.client.requests)
        self.assertEqual([], self.writer.calls)

    def test_missing_writer_does_not_spend_firecrawl_requests(self):
        self.writer = None
        result = self.pipeline().run()
        self.assertEqual({'awaiting_writer': 1}, result['worker']['statuses'])
        self.assertEqual(0, self.fake.client.requests)

    def test_collect_only_uses_firecrawl_but_never_creates_articles(self):
        result = self.pipeline().run(collect_only=True)
        self.assertEqual({'source_collected': 1}, result['worker']['statuses'])
        self.assertEqual([], self.writer.calls)
        self.assertEqual([], publication.PublicationStore(self.data).list())

    def test_missing_firecrawl_key_does_not_fall_back_to_direct_scraping(self):
        pipeline = self.pipeline(); pipeline.firecrawl = None
        result = pipeline.run()
        self.assertEqual({'source_blocked': 1}, result['worker']['statuses'])
        self.assertTrue(all(url.endswith(('/feed', '/robots.txt')) for url in self.fetches))
        self.assertEqual([], self.writer.calls)


if __name__ == '__main__': unittest.main()
