"""Offline regressions for externally supplied source links and XML encodings."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import discover_sources
import discover_councils
import municipal_source_inventory
import build_source_gap_audit
import intake
import koop_intake
import ndw_intake
import audit_media_sources


class SourceLinkBoundaryTests(unittest.TestCase):
    def test_fresh_discovery_does_not_store_executable_council_link(self):
        html = b'''<title>Gemeente</title>
        <a href="javascript:/*gemeenteraad*/alert(1)">Raad</a>
        <a href="data:text/html,raadsinformatie">Portaal</a>
        <a href="/gemeenteraad">Echte raad</a>
        <link type="application/rss+xml" href="javascript:alert(1)">'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'work').mkdir()
            with patch.object(discover_sources, 'ROOT', root), patch.object(
                discover_sources, 'fetch_public_https',
                return_value=(html, 'https://www.woerden.nl/'),
            ):
                row = discover_sources.one({'slug': 'woerden', 'name': 'Woerden'})
        self.assertEqual(row['councilLinks'], ['https://www.woerden.nl/gemeenteraad'])
        self.assertEqual(row['feeds'], [])

    def test_failed_legacy_candidate_cannot_remain_clickable(self):
        row = {'councilLinks': ['javascript:/*gemeenteraad*/alert(1)'],
               'councilCheckedUrl': 'javascript:alert(1)',
               'councilFinalUrl': 'data:text/html,bestuur',
               'councilPortals': ['file:///gemeenteraad.html']}
        with patch.object(discover_councils, 'fetch_public_https') as fetch:
            result = discover_councils.one(row)
        fetch.assert_not_called()
        self.assertNotIn('councilCheckedUrl', result)
        self.assertNotIn('councilFinalUrl', result)
        self.assertEqual(result['councilPortals'], [])

    def test_council_html_filters_executable_links_after_safe_fetch(self):
        row = {'councilLinks': ['https://example.org/gemeenteraad']}
        html = b'<a href="javascript:/*raadsagenda*/alert(1)">Agenda</a><a href="/raadsagenda">Raadsagenda</a>'
        with patch.object(discover_councils, 'fetch_public_https',
                          return_value=(html, 'https://example.org/raad/')):
            result = discover_councils.one(row)
        self.assertEqual(result['councilPortals'], ['https://example.org/raadsagenda'])
        self.assertEqual(result['councilFinalUrl'], 'https://example.org/raad/')

    def test_inventory_rejects_old_unsafe_fallback_before_report_rendering(self):
        row = {'municipality': 'woerden', 'name': 'Woerden',
               'homepage': 'https://www.woerden.nl/',
               'councilCheckedUrl': 'javascript:/*gemeenteraad*/alert(1)',
               'councilStatus': 'needs_manual_check', 'councilPortals': []}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'work').mkdir()
            (root / 'work/source-home-woerden.html').write_text('<a href="/gemeenteraad">Gemeenteraad</a>')
            records = {'articles': [], 'sources': [], 'municipal-archive-report': {},
                       'municipal-source-discovery': [row]}
            with patch.object(municipal_source_inventory, 'ROOT', root), patch.object(
                municipal_source_inventory, 'read', side_effect=lambda name, default=None: records.get(name, default)
            ), contextlib.redirect_stdout(io.StringIO()):
                municipal_source_inventory.build()
            sources = json.loads((root / 'data/municipal-source-inventory.json').read_text())[0]['sources']
        self.assertTrue(sources)
        self.assertFalse(any(s['url'].startswith('javascript:') for s in sources))
        self.assertIn('https://www.woerden.nl/gemeenteraad', {s['url'] for s in sources})
        links = ''.join(build_source_gap_audit.link(s['url'], s['name']) for s in sources)
        self.assertNotIn('javascript:', links)

    def test_report_sink_rejects_poisoned_existing_data_and_keeps_safe_links(self):
        for url in ['javascript:/*gemeenteraad*/alert(1)', 'data:text/html,<script>x</script>',
                    'file:///etc/passwd', '//evil.test/gemeenteraad', 'https://user:secret@example.org/']:
            self.assertEqual(build_source_gap_audit.link(url, 'Raad <controle>'), 'Raad &lt;controle&gt;')
        self.assertEqual(build_source_gap_audit.link('https://example.org/?a=1&b=2', 'Raad'),
                         '<a href="https://example.org/?a=1&amp;b=2">Raad</a>')
        self.assertIn('href="bronnen.csv"', build_source_gap_audit.link('bronnen.csv', 'Download'))


class XmlEntryPointTests(unittest.TestCase):
    def test_utf16_dtd_rejected_at_each_intake_entrypoint(self):
        raw = '''<?xml version="1.0" encoding="UTF-16"?>
        <!DOCTYPE rss [<!ENTITY x "entity text">]><rss>&x;</rss>'''.encode('utf-16')
        parsers = [lambda: intake.parse_feed(raw, {}, '2026-01-01', '2026-12-31'),
                   lambda: koop_intake.parse(raw, {'name': 'Woerden'}, '2026-01-01', '2026-12-31'),
                   lambda: ndw_intake.parse(raw)]
        for parse in parsers:
            with self.subTest(parse=parse), self.assertRaises(ValueError):
                parse()

    def test_media_audit_does_not_accept_encoding_bypassed_entity_feed(self):
        raw = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE rss [<!ENTITY x "hello">]><rss><item>&x;</item></rss>'.encode('utf-16')
        row = {'url': 'https://example.org/', 'knownFeed': 'https://example.org/rss'}
        with patch.object(audit_media_sources, 'fetch', side_effect=[b'<title>Source</title>', raw]):
            result = audit_media_sources.audit(row)
        self.assertNotIn('items', result['feedChecks'][0])
        self.assertNotEqual(result['feedChecks'][0]['status'], 'XML-feed bereikbaar')


if __name__ == '__main__':
    unittest.main()
