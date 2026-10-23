import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publication as p

NOW = dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc)


def fixture():
    body = ('De gemeente Utrecht meldt: de bibliotheek organiseert op 20 oktober een openbare boekenmarkt. '
            'Bezoekers kunnen tussen 10 en 16 uur boeken bekijken. De toegang voor bezoekers is gratis. '
            'De boekenmarkt biedt boeken over geschiedenis en natuur aan. Medewerkers zijn aanwezig voor vragen. '
            'Meer achtergrond over de bibliotheek is beschikbaar op de website van de gemeente Utrecht.')
    statements = [
        'De bibliotheek organiseert in Utrecht op 20 oktober een openbare boekenmarkt.',
        'Bezoekers bekijken boeken tussen 10 en 16 uur; toegang voor bezoekers is gratis.',
        'De boekenmarkt biedt boeken over natuur en geschiedenis. Medewerkers zijn aanwezig voor vragen.',
    ]
    spans = [(0, body.index('Bezoekers')), (body.index('Bezoekers'), body.index('De boekenmarkt biedt')),
             (body.index('De boekenmarkt biedt'), body.index('Meer achtergrond'))]
    facts = []
    for index, (statement, (start, end)) in enumerate(zip(statements, spans), 1):
        facts.append({'id': 'f'+str(index), 'statement': statement, 'sourceIds': ['s1'],
                      'supports': [{'sourceId': 's1', 'start': start, 'end': end, 'quote': body[start:end]}]})
    return {
        'title': 'Boekenmarkt in Utrecht op 20 oktober',
        'summary': 'De bibliotheek organiseert een openbare boekenmarkt in Utrecht. Toegang voor bezoekers is gratis.',
        'category': 'Samenleving', 'municipalities': ['utrecht'],
        'event': {'key': 'utrecht:boekenmarkt:bibliotheek:2026-10-20', 'date': '2026-10-20'},
        'publicationScope': 'public_service',
        'sources': [{'id': 's1', 'url': 'https://www.utrecht.nl/boekenmarkt', 'name': 'Gemeente Utrecht',
                     'kind': 'official', 'rightsBasis': 'facts_only',
                     'publishedAt': '2026-10-16T09:00:00+00:00', 'checkedAt': '2026-10-16T11:00:00+00:00',
                     'body': body, 'sha256': hashlib.sha256(body.encode()).hexdigest()}],
        'facts': facts,
        'municipalityEvidence': [{'municipality': 'utrecht', 'sourceId': 's1', 'start': 0, 'end': 26, 'quote': body[:26]}],
        'titleFactIds': ['f1'], 'summaryFactIds': ['f1', 'f2'],
        'paragraphs': [
            {'text': 'In Utrecht organiseert de bibliotheek een openbare boekenmarkt op 20 oktober. Bezoekers hebben tussen 10 en 16 uur toegang tot de boekenmarkt; de toegang is gratis.', 'factIds': ['f1', 'f2']},
            {'text': 'Bij de boekenmarkt zijn boeken over natuur en geschiedenis beschikbaar. Voor vragen zijn medewerkers aanwezig.', 'factIds': ['f3']},
        ],
        'authorship': {'kind': 'automated', 'provider': 'local-test'},
    }


class EvidenceTests(unittest.TestCase):
    def check(self, bundle, **kwargs):
        return p.validate_bundle(bundle, now=NOW, **kwargs)

    def test_document_span_and_article_pass_conservative_checks(self):
        result = self.check(fixture())
        self.assertTrue(result['ok'], result['errors'])
        self.assertFalse(result['semanticTruthCertified'])
        self.assertFalse(result['humanReviewed'])

    def test_verified_flag_without_real_source_is_rejected(self):
        b = fixture()
        b['facts'][0]['verified'] = True
        b['facts'][0].pop('supports')
        b['reviewStatus'] = 'approved'
        b['publicationStatus'] = 'published'
        result = self.check(b)
        self.assertFalse(result['ok'])
        self.assertTrue(any('verified:true' in issue for issue in result['errors']))

    def test_changed_body_digest_and_fabricated_quote_fail(self):
        b = fixture()
        b['sources'][0]['body'] += ' Bijlage.'
        b['facts'][0]['supports'][0]['quote'] = 'Dit is een verzonnen citaat over Utrecht.'
        result = self.check(b)
        self.assertTrue(any('vingerafdruk' in issue for issue in result['errors']))
        self.assertTrue(any('bewijsfragment' in issue for issue in result['errors']))

    def test_future_source_is_not_reported_as_published(self):
        b = fixture()
        b['sources'][0]['publishedAt'] = '2027-01-01'
        self.assertFalse(self.check(b)['ok'])

    def test_future_event_is_allowed_when_source_is_dated(self):
        self.assertTrue(self.check(fixture())['ok'])

    def test_arbitrary_event_metadata_date_does_not_bypass_automatic_date_checks(self):
        b = fixture()
        b['event']['date'] = '2026-11-30'
        result = self.check(b, automated=True, auto_publish_hosts=['www.utrecht.nl'])
        self.assertFalse(result['ok'])
        self.assertTrue(any('gebeurtenisdatum' in issue for issue in result['errors']))

    def test_unstated_event_year_cannot_be_guessed_as_next_year(self):
        b = fixture()
        b['event']['date'] = '2027-10-20'
        self.assertFalse(self.check(b, automated=True, auto_publish_hosts=['www.utrecht.nl'])['ok'])

    def test_invented_numbers_and_municipality_block(self):
        b = fixture()
        b['title'] = 'Boekenmarkt in Utrecht op 21 oktober'
        b['municipalities'].append('baarn')
        result = self.check(b)
        self.assertTrue(any('getal 21' in issue for issue in result['errors']))
        self.assertTrue(any('baarn' in issue for issue in result['errors']))

    def test_contradictory_structured_facts_block(self):
        b = fixture()
        b['facts'][0]['claim'] = {'subject': 'boekenmarkt', 'predicate': 'starttijd', 'value': '10 uur'}
        b['facts'][1]['claim'] = {'subject': 'boekenmarkt', 'predicate': 'starttijd', 'value': '12 uur'}
        self.assertTrue(any('tegenstrijdige' in issue for issue in self.check(b)['errors']))

    def test_source_article_cannot_be_copied_despite_rights_flag(self):
        b = fixture()
        b['paragraphs'][0]['text'] = b['sources'][0]['body']
        b['rightsApproved'] = True
        self.assertTrue(any('overgenomen' in issue for issue in self.check(b)['errors']))

    def test_auto_host_cannot_be_self_approved_by_bundle(self):
        b = fixture()
        b['automaticApproved'] = True
        result = self.check(b, automated=True)
        self.assertTrue(any('geconfigureerde' in issue for issue in result['errors']))

    def test_sensitive_publication_requires_human(self):
        b = fixture()
        b['sensitive'] = True
        result = self.check(b, automated=True, auto_publish_hosts=['www.utrecht.nl'])
        self.assertFalse(result['ok'])
        self.assertTrue(any('gevoelige' in issue for issue in result['errors']))

    def test_writer_cannot_hide_sensitive_source_context_from_automatic_gate(self):
        b = fixture()
        b['sources'][0]['body'] += ' De politie onderzoekt een verdachte; het onderzoek loopt.'
        b['sources'][0]['sha256'] = p.body_digest(b['sources'][0]['body'])
        b['sensitive'] = False
        result = self.check(b, automated=True, auto_publish_hosts=['www.utrecht.nl'])
        self.assertFalse(result['ok'])
        self.assertTrue(any('gevoelige' in issue for issue in result['errors']))

    def test_qualification_in_full_source_cannot_be_omitted_by_selecting_other_quotes(self):
        b = fixture()
        b['sources'][0]['body'] += ' Let op: dit betreft een voorstel voor een activiteit.'
        b['sources'][0]['sha256'] = p.body_digest(b['sources'][0]['body'])
        result = self.check(b, automated=True, auto_publish_hosts=['www.utrecht.nl'])
        self.assertFalse(result['ok'])
        self.assertTrue(any('volledige brontekst' in issue for issue in result['errors']))

    def test_cancellation_cannot_disappear_from_automatic_event_article(self):
        b = fixture()
        b['sources'][0]['body'] += ' Aanvulling: de boekenmarkt is afgelast.'
        b['sources'][0]['sha256'] = p.body_digest(b['sources'][0]['body'])
        result = self.check(b, automated=True, auto_publish_hosts=['www.utrecht.nl'])
        self.assertFalse(result['ok'])
        self.assertTrue(any('afgelast' in issue for issue in result['errors']))

    def test_malformed_generated_fields_return_errors_instead_of_crashing(self):
        for part, key, value in [('paragraphs', 'text', None), ('facts', 'sourceIds', [{}]),
                                 ('municipalityEvidence', 'sourceId', {}), ('sources', 'body', 42)]:
            with self.subTest(part=part, key=key):
                b = fixture()
                b[part][0][key] = value
                self.assertFalse(self.check(b)['ok'])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.store = p.PublicationStore(self.data, now=lambda: NOW, auto_publish_hosts=['www.utrecht.nl'])

    def draft(self):
        return self.store.submit(fixture(), actor='test-writer')['id']

    def approve(self, identifier):
        return self.store.review(identifier, actor='Testredacteur', note='Alle feiten vergeleken met vastgelegde brontekst.',
                                 checks={key: True for key in p.REVIEW_CHECKS})

    def test_new_concepts_and_legacy_json_are_never_bulk_published(self):
        self.draft()
        self.assertEqual(0o600, (self.data/'publication.sqlite3').stat().st_mode & 0o777)
        (self.data/'articles.json').write_text(json.dumps([{'reviewStatus': 'approved', 'publicationStatus': 'published'}]))
        (self.data/'published-articles.json').write_text('[{"title":"fake serialized approval"}]')
        self.assertEqual([], p.read_published(self.data))
        self.assertEqual([], self.store.export_articles())

    def test_publish_review_revise_and_retract_have_durable_history(self):
        identifier = self.draft()
        with self.assertRaises(p.PublicationError):
            self.store.publish(identifier, actor='test')
        self.approve(identifier)
        self.store.publish(identifier, actor='Testredacteur')
        original = p.read_published(self.data)[0]
        self.assertEqual('human', original['approvalKind'])
        self.assertEqual('Testredacteur', original['reviewer'])
        b = fixture()
        b['title'] = 'Bibliotheek in Utrecht organiseert boekenmarkt op 20 oktober'
        self.store._clock = lambda: NOW + dt.timedelta(minutes=10)
        self.store.revise(identifier, b, actor='Testredacteur', reason='Kop verduidelijkt')
        self.assertEqual([], p.read_published(self.data))
        with self.assertRaises(p.PublicationError):
            self.store.publish(identifier, actor='Testredacteur')
        self.approve(identifier)
        self.store.publish(identifier, actor='Testredacteur')
        current = p.read_published(self.data)[0]
        self.assertEqual(original['webPublishedAt'], current['webPublishedAt'])
        self.assertNotEqual(original['updatedAt'], current['updatedAt'])
        self.assertEqual(2, current['revision'])
        self.store.retract(identifier, actor='Testredacteur', reason='Bron heeft het bericht ingetrokken')
        self.assertEqual([], p.read_published(self.data))
        audit = self.store.audit(identifier)
        self.assertEqual(['draft', 'approve', 'publish', 'revise', 'approve', 'publish', 'retract'], [r['action'] for r in audit])
        self.assertIn('Boekenmarkt in Utrecht', json.loads(audit[0]['snapshot']['bundle'])['title'])

    def test_rewritten_event_from_other_source_is_deduplicated(self):
        identifier = self.draft()
        other = fixture()
        other['event']['key'] = 'ander-systeem:andere-identificatie'
        other['sources'][0]['url'] = 'https://bibliotheek.example/nieuws/markt'
        other['title'] = 'Utrecht: bibliotheek organiseert openbare boekenmarkt op 20 oktober'
        with self.assertRaises(p.DuplicateEvent) as ctx:
            self.store.submit(other, actor='andere-writer')
        self.assertEqual(identifier, ctx.exception.article_id)

    def test_failed_audit_rolls_back_status_and_approval(self):
        identifier = self.draft()
        with mock.patch.object(self.store, '_audit', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):
                self.approve(identifier)
        self.assertEqual('draft', self.store.get(identifier)['status'])
        self.assertEqual(1, len(self.store.audit(identifier)))

    def test_failed_export_cannot_keep_retracted_article_public(self):
        identifier = self.draft()
        self.approve(identifier)
        self.store.publish(identifier, actor='Testredacteur')
        with mock.patch('publication.os.replace', side_effect=OSError('export unavailable')):
            result = self.store.retract(identifier, actor='Testredacteur', reason='Niet meer geldig')
        self.assertIn('exportWarning', result)
        self.assertEqual([], p.read_published(self.data))
        self.assertEqual('retracted', self.store.get(identifier)['status'])

    def test_machine_approval_cannot_masquerade_as_human(self):
        identifier = self.draft()
        self.store.review(identifier, actor='publisher-job', note='Geautomatiseerde controle volgens laag-risico beleid', automated=True)
        with self.assertRaises(p.PublicationError):
            self.store.publish(identifier, actor='publisher-job')
        self.store.publish(identifier, actor='publisher-job', automated=True)
        article = p.read_published(self.data)[0]
        self.assertEqual('machine', article['approvalKind'])
        self.assertEqual('', article['reviewer'])
        self.assertFalse(article['humanReviewed'])

    def test_manual_approval_requires_each_explicit_check(self):
        identifier = self.draft()
        with self.assertRaises(p.PublicationError):
            self.store.review(identifier, actor='Testredacteur', note='Akkoord')
        self.assertEqual('draft', self.store.get(identifier)['status'])

    def test_automatic_approval_is_rechecked_at_actual_publication_time(self):
        identifier = self.draft()
        self.store.review(identifier, actor='publisher-job', note='Controle ingeplande publicatie', automated=True)
        self.store._clock = lambda: NOW + dt.timedelta(days=2)
        with self.assertRaises(p.PublicationError):
            self.store.publish(identifier, actor='publisher-job', automated=True)
        self.assertEqual([], p.read_published(self.data))
        self.assertEqual('approved', self.store.get(identifier)['status'])

    def test_concurrent_processes_cannot_create_two_articles_for_same_event(self):
        bundle_path = self.data/'bundle.json'
        bundle_path.write_text(json.dumps(fixture()))
        code = """
import json,sys
from publication import PublicationStore,DuplicateEvent
try:
 PublicationStore(sys.argv[1]).submit(json.load(open(sys.argv[2])),actor='parallel-test')
except DuplicateEvent:
 sys.exit(2)
"""
        command = [sys.executable, '-B', '-c', code, str(self.data), str(bundle_path)]
        processes = [subprocess.Popen(command, cwd=p.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        results = [(process.communicate(timeout=15), process.returncode) for process in processes]
        self.assertEqual([0, 2], sorted(code for _, code in results), results)
        self.assertEqual(1, len(self.store.list()))
        self.assertEqual(1, len(self.store.audit()))


if __name__ == '__main__':
    unittest.main()
