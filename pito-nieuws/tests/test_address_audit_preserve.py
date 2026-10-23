import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import audit_local_addresses as audit


def previous():
    return [dict(municipality='woerden', name='Woerden', homepage='https://www.woerden.nl/',
                 homepageReachable=True, checkedAt='2026-10-14', manuallyReviewed=True,
                 services=dict(report=dict(url='https://www.woerden.nl/melden', label='Meld het', status='verified',
                                           verification='Handmatig nagekeken',
                                           calendarCandidates=[{'url': 'https://www.woerden.nl/kalender'}]),
                               waste=dict(url='https://www.woerden.nl/afval', status='verified', label='Afval')))]


class AddressAuditTests(unittest.TestCase):
    def test_failed_or_missing_discovery_preserves_all_verified_details(self):
        before = previous()
        failed = dict(municipality='woerden', name='Woerden', homepage='https://www.woerden.nl/',
                      homepageReachable=False, checkedAt='2026-10-16',
                      services=dict(report=dict(url='https://www.woerden.nl/broken', status='fetch_failed'),
                                    waste=dict(status='not_found')))
        self.assertEqual(audit.merge_records(before, [failed]), before)
        self.assertEqual(before, previous())

    def test_success_adds_verified_fields_without_erasing_curated_details(self):
        observation = dict(municipality='woerden', name='Woerden', homepage='https://www.woerden.nl/',
                           homepageReachable=True, checkedAt='2026-10-16',
                           services=dict(report=dict(url='https://www.woerden.nl/melden', label='',
                                                     status='verified', calendarCandidates=[])))
        merged = audit.merge_records(previous(), [observation])[0]
        self.assertTrue(merged['manuallyReviewed'])
        self.assertEqual(merged['services']['report']['label'], 'Meld het')
        self.assertTrue(merged['services']['report']['calendarCandidates'])
        self.assertEqual(merged['services']['report']['verification'], 'Handmatig nagekeken')
        self.assertEqual(merged['services']['report']['checkedAt'], '2026-10-16')
        self.assertEqual(merged['services']['waste'], previous()[0]['services']['waste'])

    def prepare(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root/'data').mkdir()
        (root/'data/local-addresses.json').write_text(json.dumps(previous()))
        (root/'data/municipal-source-discovery.json').write_text(json.dumps([
            dict(municipality='woerden', name='Woerden', homepage='https://www.woerden.nl/')]))
        return root

    def test_default_dry_run_does_not_write_any_files(self):
        root = self.prepare()
        before = {p.name: p.read_bytes() for p in (root/'data').iterdir()}
        with patch.object(audit, 'ROOT', root), patch.object(audit, 'inspect', return_value=previous()[0]), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(audit.main([]), 0)
        self.assertEqual({p.name: p.read_bytes() for p in (root/'data').iterdir()}, before)

    def test_apply_keeps_backup_and_failure_diagnostics_separate(self):
        root = self.prepare()
        original = json.loads((root/'data/local-addresses.json').read_text())
        observation = copy.deepcopy(original[0])
        observation.update(checkedAt='2026-10-16', homepageReachable=False)
        observation['services'] = dict(report=dict(status='fetch_failed'))
        with patch.object(audit, 'ROOT', root), patch.object(audit, 'inspect', return_value=observation), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(audit.main(['--apply']), 1)
        self.assertEqual(json.loads((root/'data/local-addresses.json').read_text()), original)
        self.assertEqual(json.loads((root/'data/local-addresses.json.bak').read_text()), original)
        report = json.loads((root/'data/local-address-audit-report.json').read_text())
        self.assertTrue(report['applied'])
        self.assertFalse(report['observations'][0]['homepageReachable'])
        self.assertEqual(report['observations'][0]['services']['report']['status'], 'fetch_failed')

    def test_report_cannot_overwrite_canonical_data(self):
        root = self.prepare()
        with patch.object(audit, 'ROOT', root), patch('sys.stderr', new_callable=io.StringIO), patch.object(audit, 'inspect') as inspect:
            with self.assertRaises(SystemExit):
                audit.main(['--report', str(root/'data/local-addresses.json')])
            inspect.assert_not_called()

    def test_apply_merges_against_edits_made_while_network_audit_runs(self):
        root = self.prepare()
        path = root/'data/local-addresses.json'
        newer = previous()
        newer[0]['services']['report']['label'] = 'Handmatig bijgewerkt tijdens controle'

        def observation(_):
            path.write_text(json.dumps(newer))
            result = previous()[0]
            result['homepageReachable'] = False
            result['services'] = dict(report=dict(status='fetch_failed'))
            return result

        with patch.object(audit, 'ROOT', root), patch.object(audit, 'inspect', side_effect=observation), patch('sys.stdout', new_callable=io.StringIO):
            audit.main(['--apply'])
        self.assertEqual(json.loads(path.read_text()), newer)
        self.assertEqual(json.loads(path.with_suffix('.json.bak').read_text()), newer)

    def test_atomic_write_failure_preserves_original_file(self):
        root = self.prepare()
        data = root/'data/local-addresses.json'
        original = data.read_bytes()
        with patch.object(audit.os, 'replace', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                audit.atomic_json(data, [])
        self.assertEqual(data.read_bytes(), original)
        self.assertEqual(list(data.parent.glob('*.tmp')), [])

    def test_failed_homepage_body_does_not_generate_verified_candidates(self):
        with patch.object(audit, 'fetch', return_value=(22, '<a href="/contact">Contact</a>')):
            result = audit.inspect(dict(municipality='woerden', name='Woerden', homepage='https://www.woerden.nl/'))
        self.assertFalse(result['homepageReachable'])
        self.assertTrue(all(row['status'] == 'fetch_failed' for row in result['services'].values()))


if __name__ == '__main__':
    unittest.main()
