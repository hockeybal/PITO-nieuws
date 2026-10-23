import contextlib
import datetime as dt
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import newsroom_worker as w
import publication
from test_publication import fixture, NOW


def html_fixture(date='2026-10-16T09:00:00+00:00'):
    body = fixture()['sources'][0]['body']
    return ('<!doctype html><html><head><meta property="article:published_time" content="'+date+'"></head>'
            '<body><header><nav>Nieuws in Amsterdam</nav></header><main><article><header><h1>Boekenmarkt in Utrecht</h1></header>'
            '<p>'+body[:body.index('De boekenmarkt biedt')]+'</p><p>'+body[body.index('De boekenmarkt biedt'):]+'</p>'
            '<aside><p>Privacygevoelige aanbevelingen uit de zijbalk niet in het artikel.</p></aside></article></main>'
            '<footer><p>Footer en persoonsgegevens niet meenemen.</p></footer></body></html>').encode()


def writer_output():
    b = fixture()
    return {'decision': 'draft', 'reason': '', 'title': b['title'], 'summary': b['summary'],
            'category': b['category'], 'municipalities': b['municipalities'], 'eventDate': b['event']['date'],
            'eventKey': 'boekenmarkt-bibliotheek', 'publicationScope': 'public_service', 'sensitive': False,
            'titleFactIds': b['titleFactIds'], 'summaryFactIds': b['summaryFactIds'],
            'facts': [dict(id=f['id'], statement=f['statement'], quotes=[s['quote'] for s in f['supports']],
                           claim={'subject': 'boekenmarkt', 'predicate': 'feit '+f['id'], 'value': f['statement']}) for f in b['facts']],
            'paragraphs': b['paragraphs'],
            'municipalityEvidence': [{'municipality': 'utrecht', 'quote': b['municipalityEvidence'][0]['quote']}]}


class Writer:
    model = 'configured-test-model'

    def __init__(self, output=None):
        self.calls = []
        self.output = output

    def __call__(self, document):
        self.calls.append(document)
        return writer_output() if self.output is None else self.output


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.row = {'id': 'inbox-test', 'sourceId': 'utrecht', 'sourceTitle': 'Boekenmarkt in Utrecht',
                    'sourceUrl': 'https://www.utrecht.nl/boekenmarkt', 'sourceTimestamp': '2026-10-16T09:00:00+00:00',
                    'sourcePublishedAt': '2026-10-16', 'fingerprint': 'original-feed-fingerprint'}
        (self.data/'inbox.json').write_text(json.dumps([self.row]))
        (self.data/'sources.json').write_text(json.dumps([{'id': 'utrecht', 'name': 'Gemeente Utrecht',
                                                         'kind': 'Gemeente', 'url': 'https://www.utrecht.nl/',
                                                         'articleHosts': ['www.utrecht.nl']}]))
        self.requests = []
        self.raw = html_fixture()
        self.robots = b'User-agent: *\nAllow: /\nCrawl-delay: 1\n'

    def fetch(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.robots if url.endswith('/robots.txt') else self.raw

    def worker(self, writer=None, env=None, now=None):
        return w.NewsroomWorker(self.data, writer=writer, fetcher=self.fetch, now=lambda: now or NOW, environment=env or {})

    def test_missing_writer_is_honest_and_performs_no_network(self):
        report = self.worker().run()
        self.assertEqual({'awaiting_writer': 1}, report['statuses'])
        self.assertEqual(0, report['writerRequests'])
        self.assertEqual([], self.requests)
        self.assertEqual([], publication.read_published(self.data))
        self.assertEqual([], publication.PublicationStore(self.data).list())

    def test_collect_only_reads_real_source_without_writer_or_publication(self):
        writer = Writer()
        report = self.worker(writer).run(collect_only=True)
        self.assertEqual({'source_collected': 1}, report['statuses'], report)
        self.assertEqual('collect', report['mode'])
        self.assertEqual(0, report['writerRequests'])
        self.assertEqual([], writer.calls)
        files = list((self.data/'newsroom/documents').glob('*.json'))
        self.assertEqual(1, len(files))
        document = json.loads(files[0].read_text())
        self.assertEqual(publication.body_digest(document['body']), document['sha256'])
        self.assertEqual([], publication.PublicationStore(self.data).list())
        self.assertEqual([], publication.read_published(self.data))

    def test_collected_source_can_later_be_written(self):
        self.worker().run(collect_only=True)
        report = self.worker(Writer(), now=NOW+dt.timedelta(seconds=2)).run()
        self.assertEqual({'drafted': 1}, report['statuses'], report)

    def test_collect_and_publish_flags_are_incompatible(self):
        with self.assertRaises(w.WorkerError):
            self.worker(Writer(), env={'PITO_AUTO_PUBLISH_HOSTS': 'www.utrecht.nl'}).run(publish=True, collect_only=True)

    def test_shadow_creates_traceable_draft_from_real_extracted_body(self):
        writer = Writer()
        report = self.worker(writer).run()
        self.assertEqual({'drafted': 1}, report['statuses'], report)
        self.assertEqual('shadow', report['mode'])
        self.assertEqual(1, len(writer.calls))
        draft = publication.PublicationStore(self.data).list()[0]
        source = draft['bundle']['sources'][0]
        self.assertEqual(publication.body_digest(source['body']), source['sha256'])
        self.assertNotIn('zijbalk', source['body'])
        self.assertNotIn('persoonsgegevens', source['body'])
        for fact in draft['bundle']['facts']:
            for support in fact['supports']:
                self.assertEqual(support['quote'], source['body'][support['start']:support['end']])
        self.assertEqual([], publication.read_published(self.data))
        self.assertTrue((self.data/'newsroom/state.json').exists())
        self.assertEqual(0o600, (self.data/'newsroom/state.json').stat().st_mode & 0o777)
        self.assertTrue(all(options['max_redirects'] == 0 for _, options in self.requests))

    def test_identical_run_does_not_consume_provider_again(self):
        writer = Writer()
        worker = self.worker(writer)
        worker.run()
        report = worker.run()
        self.assertEqual([], report['items'])
        self.assertEqual(1, len(writer.calls))
        self.assertEqual(2, len(self.requests))

    def test_day_later_rechecks_source_without_rewriting_unchanged_body(self):
        writer = Writer()
        self.worker(writer).run()
        report = self.worker(writer, now=NOW+dt.timedelta(days=1, minutes=1)).run()
        self.assertEqual({'duplicate': 1}, report['statuses'])
        self.assertEqual(1, len(writer.calls))

    def test_robots_disallow_prevents_article_fetch_and_writer(self):
        self.robots = b'User-agent: *\nDisallow: /\n'
        writer = Writer()
        report = self.worker(writer).run()
        self.assertEqual({'source_blocked': 1}, report['statuses'])
        self.assertEqual(1, len(self.requests))
        self.assertEqual([], writer.calls)

    def test_unknown_item_host_is_not_trusted_from_inbox_flags(self):
        self.row.update(sourceUrl='https://evil.example/news', kind='official', publicationAllowed=True)
        (self.data/'inbox.json').write_text(json.dumps([self.row]))
        writer = Writer()
        report = self.worker(writer).run()
        self.assertEqual({'source_blocked': 1}, report['statuses'])
        self.assertEqual([], self.requests)
        self.assertEqual([], writer.calls)

    def test_forged_model_source_and_approval_are_ignored(self):
        output = writer_output()
        output.update(sources=[{'url': 'https://evil.example', 'sha256': 'forged'}], reviewedBy='fake human', approved=True)
        report = self.worker(Writer(output)).run()
        self.assertEqual({'drafted': 1}, report['statuses'])
        saved = publication.PublicationStore(self.data).list()[0]
        self.assertEqual('https://www.utrecht.nl/boekenmarkt', saved['bundle']['sources'][0]['url'])
        self.assertEqual('draft', saved['status'])
        self.assertIsNone(saved['approved_by'])

    def test_fabricated_model_quote_cannot_enter_publication_store(self):
        output = writer_output()
        output['facts'][0]['quotes'] = ['Dit citaat staat helemaal niet in de bron.']
        report = self.worker(Writer(output)).run()
        self.assertEqual({'needs_review': 1}, report['statuses'])
        self.assertEqual([], publication.PublicationStore(self.data).list())
        self.assertEqual([], publication.read_published(self.data))

    def test_publish_requires_explicit_separate_host_configuration(self):
        with self.assertRaises(w.WorkerError):
            self.worker(Writer()).run(publish=True)
        self.assertEqual([], self.requests)

    def test_configured_low_risk_worker_cannot_bypass_cms_publication(self):
        writer = Writer()
        with self.assertRaisesRegex(w.WorkerError, 'uitsluitend.*Strapi'):
            self.worker(writer, env={'PITO_AUTO_PUBLISH_HOSTS': 'www.utrecht.nl'}).run(publish=True)
        self.assertEqual([], writer.calls)
        self.assertEqual([], publication.read_published(self.data))

    def test_writer_request_for_human_review_is_never_automatically_approved(self):
        output = writer_output()
        output['decision'] = 'needs_review'
        output['reason'] = 'Feitelijke context moet door een redacteur worden vergeleken'
        output['sensitive'] = False
        report = self.worker(Writer(output), env={'PITO_AUTO_PUBLISH_HOSTS': 'www.utrecht.nl'}).run()
        self.assertEqual({'needs_review': 1}, report['statuses'], report)
        self.assertEqual([], publication.read_published(self.data))
        store = publication.PublicationStore(self.data)
        self.assertEqual('draft', store.list()[0]['status'])
        self.assertEqual(['draft'], [entry['action'] for entry in store.audit()])

    def test_shadow_draft_cannot_be_published_by_old_worker_option(self):
        self.worker(Writer()).run()
        with self.assertRaises(w.WorkerError):
            self.worker(Writer(), env={'PITO_AUTO_PUBLISH_HOSTS': 'www.utrecht.nl'}).run(publish=True)
        self.assertEqual([], publication.read_published(self.data))
        self.assertEqual('draft', publication.PublicationStore(self.data).list()[0]['status'])

    def test_changed_source_is_a_private_revision_proposal(self):
        self.worker(Writer()).run()
        original = publication.PublicationStore(self.data).list()[0]
        self.raw = html_fixture().replace(b'Meer achtergrond', b'Aanvullende achtergrond')
        self.row['fingerprint'] = 'changed-feed-fingerprint'
        (self.data/'inbox.json').write_text(json.dumps([self.row]))
        report = self.worker(Writer(), now=NOW+dt.timedelta(minutes=5)).run()
        self.assertEqual({'revision_pending': 1}, report['statuses'], report)
        current = publication.PublicationStore(self.data).get(original['id'])
        self.assertEqual(original['bundle'], current['bundle'])
        self.assertEqual([], publication.read_published(self.data))

    def test_outbox_delivers_existing_draft_without_writer_and_keeps_audit_link(self):
        self.worker(Writer()).run()
        client = mock.Mock()
        client.submit.return_value = {'documentId': 'cms-document-1', 'created': True, 'status': 'draft'}
        with mock.patch.object(w.strapi_news.DraftClient, 'from_environment', return_value=client):
            report = self.worker().run()
            repeated = self.worker().run()
        self.assertEqual(1, report['draftSync']['synced'])
        self.assertEqual(0, report['writerRequests'])
        self.assertEqual(0, repeated['draftSync']['attempted'])
        self.assertEqual(1, client.submit.call_count)
        links = json.loads((self.data/'newsroom/strapi-links.json').read_text())
        self.assertEqual('cms-document-1', links['records'][0]['documentId'])
        self.assertEqual(0o600, (self.data/'newsroom/strapi-links.json').stat().st_mode & 0o777)
        self.assertEqual([], publication.read_published(self.data))

    def test_collect_only_never_uploads_existing_outbox_drafts(self):
        self.worker(Writer()).run()
        client = mock.Mock()
        with mock.patch.object(w.strapi_news.DraftClient, 'from_environment', return_value=client):
            report = self.worker(now=NOW+dt.timedelta(seconds=2)).run(collect_only=True)
        client.submit.assert_not_called()
        self.assertEqual(0, report['draftSync']['attempted'])
        self.assertEqual(1, report['draftSync']['pending'])
        self.assertEqual(0, report['writerRequests'])

    def test_ambiguous_timeout_retries_same_key_and_preserves_human_cms_edit(self):
        requests = []
        document = {'title': None}
        def transport(base, endpoint, token, method, body):
            requests.append(body)
            if len(requests) == 1:
                document['title'] = body['data']['title']
                raise w.strapi_news.StrapiNewsError('Onbekende uitkomst na timeout')
            return {'data': {'documentId': 'same-document', 'created': False, 'status': 'draft'}}
        client = w.strapi_news.DraftClient('https://cms.example.test', 'draft-test-token', transport)
        writer = Writer()
        with mock.patch.object(w.strapi_news.DraftClient, 'from_environment', return_value=client):
            first = self.worker(writer).run()
            document['title'] = 'Menselijke wijziging in Strapi'
            second = self.worker(writer).run()
        self.assertEqual(1, first['draftSync']['errors'])
        self.assertEqual(1, second['draftSync']['synced'])
        self.assertEqual(1, len(writer.calls))
        self.assertEqual(requests[0]['data']['externalKey'], requests[1]['data']['externalKey'])
        self.assertEqual('Menselijke wijziging in Strapi', document['title'])
        for key in ('reviewStatus', 'verifiedAt', 'reviewNote', 'author', 'publishedAt', 'status'):
            self.assertNotIn(key, requests[0]['data'])
        self.assertNotIn('body', requests[0]['data']['privateEvidence'])
        self.assertEqual('writer', requests[0]['data']['origin'])
        self.assertEqual([], publication.read_published(self.data))

    def test_provider_exception_never_leaks_credentials_to_status(self):
        def failed_writer(_):
            raise RuntimeError('sk-secret-test-key-in-exception')
        report = self.worker(failed_writer).run()
        self.assertEqual({'processing_error': 1}, report['statuses'])
        self.assertNotIn('sk-secret', json.dumps(report))
        self.assertNotIn('sk-secret', (self.data/'newsroom/state.json').read_text())

    def test_process_lock_prevents_second_worker(self):
        worker = self.worker(Writer())
        with (self.data/'newsroom/worker.lock').open('a') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(w.WorkerError):
                worker.run()
        self.assertEqual([], self.requests)

    def test_corrupt_state_is_preserved_and_never_overwritten(self):
        worker = self.worker(Writer())
        state_path = self.data/'newsroom/state.json'
        state_path.write_text('{"version":999,"items":{}}')
        original = state_path.read_bytes()
        with self.assertRaises(w.WorkerError):
            worker.run()
        self.assertEqual(original, state_path.read_bytes())

    def test_provider_budget_is_bounded_before_network(self):
        with self.assertRaises(w.WorkerError):
            self.worker(Writer()).run(limit=4)
        self.assertEqual([], self.requests)

    def test_at_most_three_provider_calls_for_a_larger_backlog(self):
        sources, inbox = [], []
        for index in range(4):
            host = 'source-'+str(index)+'.example'
            sources.append({'id': 's'+str(index), 'kind': 'Gemeente', 'name': 'Gemeente Utrecht', 'url': 'https://'+host})
            inbox.append(dict(self.row, sourceId='s'+str(index), sourceUrl='https://'+host+'/boekenmarkt'))
        (self.data/'sources.json').write_text(json.dumps(sources))
        (self.data/'inbox.json').write_text(json.dumps(inbox))
        writer = Writer()
        report = self.worker(writer).run()
        self.assertEqual(3, report['writerRequests'])
        self.assertEqual(3, len(writer.calls))
        self.assertEqual(4, report['availableCandidates'])

    def test_real_cli_missing_provider_path_has_no_network_or_fake_articles(self):
        # The runtime host clock may differ from the user's conversation date.
        actual = publication.utcnow().isoformat()
        self.row.update(sourceTimestamp=actual, sourcePublishedAt=actual[:10])
        (self.data/'inbox.json').write_text(json.dumps([self.row]))
        env = os.environ.copy()
        for name in ('OPENAI_API_KEY', 'PITO_WRITER_API_KEY', 'PITO_WRITER_MODEL'):
            env.pop(name, None)
        process = subprocess.run([sys.executable, '-B', str(w.ROOT/'scripts/run_newsroom.py'), '--data-dir', str(self.data)],
                                 env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, process.returncode, process.stderr)
        report = json.loads(process.stdout)
        self.assertFalse(report['writerConfigured'])
        self.assertEqual({'awaiting_writer': 1}, report['statuses'])
        self.assertEqual([], publication.read_published(self.data))


class ExtractionTests(unittest.TestCase):
    def test_extracts_jsonld_date_and_article_body(self):
        raw = html_fixture().replace(b'<meta property="article:published_time" content="2026-10-16T09:00:00+00:00">',
              b'<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-10-16"}</script>')
        result = w.extract_article(raw, {}, NOW)
        self.assertEqual('2026-10-16', result['publishedAt'])
        self.assertEqual('source_page', result['dateEvidence'])
        self.assertTrue(result['body'].startswith('Boekenmarkt in Utrecht'))

    def test_article_index_and_feed_headline_are_not_body_evidence(self):
        for raw in [b'<html><main><h1>Nieuws</h1><p>Alleen een kop.</p></main></html>',
                    html_fixture().replace(b'</article>', b'</article><article><p>Nog een bericht op deze indexpagina.</p></article>')]:
            with self.assertRaises(w.WorkerError):
                w.extract_article(raw, {'sourcePublishedAt': '2026-10-16'}, NOW)

    def test_missing_or_future_or_conflicting_source_dates_block(self):
        raw_no_date = html_fixture().replace(b'<meta property="article:published_time" content="2026-10-16T09:00:00+00:00">', b'')
        with self.assertRaises(ValueError):
            w.extract_article(raw_no_date, {}, NOW)
        with self.assertRaises(w.WorkerError):
            w.extract_article(html_fixture('2027-01-01'), {}, NOW)
        conflict = html_fixture().replace(b'</head>', b'<meta property="article:published_time" content="2026-10-15"></head>')
        with self.assertRaises(w.WorkerError):
            w.extract_article(conflict, {}, NOW)


class SourceTemplateTests(unittest.TestCase):
    def test_single_post_section_excludes_other_page_sections(self):
        raw = html_fixture().replace(b'<main><article>', b'<section class="single-post-section"><div>')
        raw = raw.replace(b'</article></main>', b'</div></section><section><p>Andere pagina-inhoud mag niet in het bronbericht staan.</p></section>')
        doc = w.extract_article(raw, {}, NOW)
        self.assertIn('Boekenmarkt', doc['body'])
        self.assertNotIn('Andere pagina-inhoud', doc['body'])

    def test_component_text_is_scoped_and_related_cards_are_excluded(self):
        raw = '''<html><h1>Stroomstoring in Hoogland</h1>
        <div __component="api.api-text"><div>Dit is geen artikeltekst.</div></div>
        <div class="article-content">
          <div __component="api.api-text"><div class="text">In Hoogland zitten ongeveer 1200 huishoudens zonder stroom. Monteurs van de netbeheerder zijn onderweg om de oorzaak van de storing te onderzoeken.</div></div>
          <div __component="api.api-text"><div class="text">Het is nog niet bekend wanneer de storing is opgelost. De netbeheerder werkt aan herstel en informeert de getroffen huishoudens over de voortgang van het werk.</div></div>
        </div><article class="news-list-item"><p>Onverwant aanbevolen nieuws hoort hier niet bij.</p></article></html>'''.encode()
        doc = w.extract_article(raw, {'sourcePublishedAt': '2026-10-16'}, NOW)
        self.assertIn('1200 huishoudens', doc['body'])
        self.assertNotIn('geen artikeltekst', doc['body'])
        self.assertNotIn('Onverwant', doc['body'])

    def test_wordpress_post_content_does_not_include_recommendation_articles(self):
        raw = html_fixture().replace(b'<article>', b'<div class="elementor-widget-theme-post-content">').replace(b'</article>', b'</div><article class="elementor-post" role="listitem"><p>Dit is een aanbevolen artikel dat niet tot het hoofdbericht behoort.</p></article>')
        doc = w.extract_article(raw, {'sourcePublishedAt': '2026-10-16'}, NOW)
        self.assertNotIn('aanbevolen artikel', doc['body'])


class ProviderTests(unittest.TestCase):
    def test_both_explicit_key_and_model_are_required(self):
        self.assertIsNone(w.OpenAIWriter.from_environment({}))
        self.assertIsNone(w.OpenAIWriter.from_environment({'OPENAI_API_KEY': 'sk-test'}))
        self.assertIsNone(w.OpenAIWriter.from_environment({'PITO_WRITER_MODEL': 'model-test'}))
        self.assertEqual('model-test', w.OpenAIWriter.from_environment({'PITO_WRITER_API_KEY': 'sk-test', 'PITO_WRITER_MODEL': 'model-test'}).model)

    def test_fixed_endpoint_structured_response_and_no_storage(self):
        payload = {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(writer_output())}]}]}
        connection = mock.Mock()
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = json.dumps(payload).encode()
        with mock.patch('newsroom_worker.http.client.HTTPSConnection', return_value=connection) as factory:
            result = w.OpenAIWriter('sk-test-key', 'configured-model')({'source': {'body': 'Untrusted source text'}})
        self.assertEqual('draft', result['decision'])
        self.assertEqual('api.openai.com', factory.call_args.args[0])
        args, kwargs = connection.request.call_args
        self.assertEqual(('POST', '/v1/responses'), args[:2])
        request = json.loads(kwargs['body'])
        self.assertFalse(request['store'])
        self.assertEqual('json_schema', request['text']['format']['type'])
        self.assertTrue(request['text']['format']['strict'])
        self.assertLessEqual(request['max_output_tokens'], 4500)
        self.assertNotIn('sk-test-key', json.dumps(request))
        connection.close.assert_called_once()

    def test_redirect_error_refusal_and_incomplete_are_never_articles(self):
        for status, payload in [(302, {}), (401, {}), (200, {'status': 'incomplete', 'output': []}),
                                (200, {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'cannot'}]}]})]:
            with self.subTest(status=status, payload=payload):
                connection = mock.Mock()
                connection.getresponse.return_value.status = status
                connection.getresponse.return_value.read.return_value = json.dumps(payload).encode()
                with mock.patch('newsroom_worker.http.client.HTTPSConnection', return_value=connection):
                    with self.assertRaises(w.WorkerError):
                        w.OpenAIWriter('sk-test-key', 'configured-model')({})


if __name__ == '__main__':
    unittest.main()
