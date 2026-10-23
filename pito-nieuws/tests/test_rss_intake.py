"""Offline tests for scheduled RSS intake, independent of upstream availability."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import intake


def feed(title='Nieuws', link='https://example.org/article'):
    return (f'<rss><channel><item><title>{title}</title><link>{link}</link>'
            '<pubDate>Fri, 16 Oct 2026 08:00:00 +0200</pubDate>'
            '</item></channel></rss>').encode()


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'data').mkdir()
        self.sources = [
            {'id': 'a', 'name': 'Bron A', 'feed': 'https://example.org/a',
             'articleHosts': ['example.org'], 'municipality': 'woerden'},
            {'id': 'b', 'feed': 'https://example.org/b', 'articleHosts': ['example.org'],
             'coverageCandidates': ['utrecht']},
            {'id': 'c', 'feed': 'https://example.org/broken'},
            {'id': 'manual', 'url': 'https://example.org/manual'},
        ]
        (self.root / 'data/sources.json').write_text(json.dumps(self.sources))
        (self.root / 'data/inbox.json').write_text('[]')

    def run_intake(self, fetch, workers=2):
        with patch.object(intake, 'ROOT', self.root), patch.object(intake, 'fetch_public_https', side_effect=fetch), contextlib.redirect_stdout(io.StringIO()):
            return intake.run('2026-10-10', '2026-10-16', workers=workers)

    def test_bounded_parallel_fetch_errors_and_deterministic_merging(self):
        rendezvous = threading.Barrier(2)
        lock = threading.Lock()
        active = 0
        maximum = 0

        def fetch(url, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                self.assertEqual(kwargs['max_bytes'], 2_000_000)
                self.assertEqual(kwargs['timeout'], 25)
                if url.endswith('/broken'):
                    raise ValueError('Upstream unavailable')
                rendezvous.wait(timeout=3)
                return feed()
            finally:
                with lock:
                    active -= 1

        report = self.run_intake(fetch)
        self.assertEqual(maximum, 2)
        self.assertEqual((report['configured'], report['succeeded'], report['failed']), (3, 2, 1))
        self.assertEqual([row['source'] for row in report['sources']], ['a', 'b', 'c'])
        self.assertEqual(report['added'], 1)
        self.assertIn('Upstream unavailable', report['sources'][2]['error'])
        self.assertEqual(report['sources'][0]['municipality'], 'woerden')
        self.assertEqual(report['sources'][1]['coverageCandidates'], ['utrecht'])
        self.assertTrue(all(row['finishedAt'] >= row['startedAt'] for row in report['sources']))
        inbox = json.loads((self.root / 'data/inbox.json').read_text())
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['sourceId'], 'a')
        self.assertEqual(inbox[0]['sourceIds'], ['a', 'b'])
        self.assertEqual(inbox[0]['municipalityCandidates'], ['utrecht', 'woerden'])
        self.assertEqual(inbox[0]['municipalities'], [])
        self.assertEqual(inbox[0]['status'], 'needs_review')
        self.assertEqual(json.loads((self.root / 'data/intake-report.json').read_text()), report)
        self.assertEqual(list((self.root / 'data').glob('*.tmp')), [])

    def test_failed_sources_preserve_inbox_and_changed_headlines_keep_revision(self):
        old = intake.parse_feed(feed('Oud nieuws'), self.sources[0], '2026-10-10', '2026-10-16')[0][0]
        old.update(firstSeenAt='yesterday', lastSeenAt='yesterday', status='reviewed',
                   editorNote='Keep this decision', municipalities=['woerden'])
        (self.root / 'data/inbox.json').write_text(json.dumps([old]))
        (self.root / 'data/intake-report.json').write_text(json.dumps({
            'sources': [{'source': 'b', 'status': 'error', 'lastSuccessAt': '2026-10-15T10:00:00Z'}]}))

        def fetch(url, **kwargs):
            if url.endswith('/a'):
                return feed('Nieuw nieuws')
            raise ValueError('unavailable')

        report = self.run_intake(fetch)
        self.assertEqual(report['added'], 0)
        row = json.loads((self.root / 'data/inbox.json').read_text())[0]
        self.assertEqual(row['sourceTitle'], 'Nieuw nieuws')
        self.assertEqual(row['revisions'][0]['sourceTitle'], 'Oud nieuws')
        self.assertEqual(row['firstSeenAt'], 'yesterday')
        self.assertEqual(row['editorNote'], 'Keep this decision')
        self.assertEqual(row['municipalities'], ['woerden'])
        self.assertEqual(row['status'], 'needs_review')
        self.assertEqual(report['sources'][1]['lastSuccessAt'], '2026-10-15T10:00:00Z')

    def test_per_host_limit_allows_other_hosts_to_progress(self):
        self.sources = [
            {'id': key, 'feed': 'https://example.org/' + key}
            for key in ('a', 'b', 'c')
        ] + [{'id': 'd', 'feed': 'https://other.example/d'}]
        (self.root / 'data/sources.json').write_text(json.dumps(self.sources))
        rendezvous = threading.Barrier(3)
        lock = threading.Lock()
        active = {}
        maximum = {}

        def fetch(url, **kwargs):
            host = intake.urlsplit(url).hostname
            with lock:
                active[host] = active.get(host, 0) + 1
                maximum[host] = max(maximum.get(host, 0), active[host])
            try:
                if not url.endswith('/c'):
                    rendezvous.wait(timeout=3)
                return feed()
            finally:
                with lock:
                    active[host] -= 1

        report = self.run_intake(fetch, workers=4)
        self.assertEqual(report['succeeded'], 4)
        self.assertEqual(maximum['example.org'], 2)
        self.assertEqual(maximum['other.example'], 1)

    def test_atomic_failure_keeps_previous_valid_file(self):
        target = self.root / 'data/inbox.json'
        target.write_text('[{"old": true}]')
        with patch.object(intake.json, 'dump', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                intake._atomic_json(target, [{'new': True}])
        self.assertEqual(json.loads(target.read_text()), [{'old': True}])
        self.assertEqual(list((self.root / 'data').glob('*.tmp')), [])

    def test_rss_one_atom_and_false_html_feed(self):
        raw = b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"><item><title>RSS 1</title><link>https://example.org/rss1</link><dc:date>2026-10-16T08:00:00Z</dc:date></item></rdf:RDF>'
        rows, skipped = intake.parse_feed(raw, self.sources[0], '2026-10-10', '2026-10-16')
        self.assertEqual(rows[0]['sourceTitle'], 'RSS 1')
        self.assertEqual(skipped, 0)
        raw = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom</title><link href="https://example.org/atom"/><updated>2026-10-16T08:00:00Z</updated><content>Never copy this body</content></entry></feed>'
        rows, skipped = intake.parse_feed(raw, self.sources[0], '2026-10-10', '2026-10-16')
        self.assertEqual(rows[0]['sourceUrl'], 'https://example.org/atom')
        self.assertTrue(rows[0]['sourceTimezoneKnown'])
        self.assertNotIn('Never copy', json.dumps(rows))
        without_offset = raw.replace(b'2026-10-16T08:00:00Z', b'2026-10-16T08:00:00')
        rows, _ = intake.parse_feed(without_offset, self.sources[0], '2026-10-10', '2026-10-16')
        self.assertFalse(rows[0]['sourceTimezoneKnown'])
        self.assertEqual(rows[0]['sourceTimestamp'], '2026-10-16T08:00:00')
        date_only = raw.replace(b'2026-10-16T08:00:00Z', b'2026-10-16')
        rows, _ = intake.parse_feed(date_only, self.sources[0], '2026-10-10', '2026-10-16')
        self.assertFalse(rows[0]['sourceTimezoneKnown'])
        self.assertEqual(rows[0]['sourceTimestamp'], '2026-10-16')
        with self.assertRaisesRegex(ValueError, 'geen RSS'):
            intake.parse_feed(b'<html><body>Login</body></html>', self.sources[0], '2026-10-10', '2026-10-16')

    def test_cli_defaults_to_rolling_fortnight(self):
        with patch.object(sys, 'argv', ['intake.py', '--end', '2026-10-16']), patch.object(intake, 'run', return_value={'configured': 3, 'succeeded': 2}) as run:
            intake.main()
        run.assert_called_once_with('2026-10-02', '2026-10-16', intake.DEFAULT_WORKERS)

    def test_cli_total_outage_returns_failure_after_saving_report(self):
        with patch.object(sys, 'argv', ['intake.py', '--end', '2026-10-16']), patch.object(intake, 'ROOT', self.root), patch.object(intake, 'fetch_public_https', side_effect=ValueError('outage')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(intake.main(), 1)
        report = json.loads((self.root / 'data/intake-report.json').read_text())
        self.assertEqual((report['succeeded'], report['failed']), (0, 3))
        self.assertEqual(json.loads((self.root / 'data/inbox.json').read_text()), [])

    def test_empty_undated_and_old_feeds_are_reported_distinctly(self):
        def fetch(url, **kwargs):
            if url.endswith('/a'):
                return b'<rss><channel/></rss>'
            if url.endswith('/b'):
                return feed().replace(b'<pubDate>Fri, 16 Oct 2026 08:00:00 +0200</pubDate>', b'')
            return feed().replace(b'16 Oct 2026', b'16 Sep 2026')

        report = self.run_intake(fetch)
        self.assertEqual(report['succeeded'], 3)
        self.assertEqual([row['freshnessStatus'] for row in report['sources']], ['empty', 'undated', 'outside_window'])
        self.assertEqual(report['sources'][0]['feedEntries'], 0)
        self.assertEqual(report['sources'][1]['skippedMissingDate'], 1)
        self.assertEqual(report['sources'][2]['skippedOutsideWindow'], 1)
        self.assertTrue(all(row['warning'] for row in report['sources']))

    def test_worker_bounds_and_invalid_dates_reject_before_network(self):
        with patch.object(intake, 'fetch_public_https') as fetch:
            for workers in (0, 13, True, 2.5):
                with self.subTest(workers=workers), self.assertRaises(ValueError):
                    intake.run('2026-10-10', '2026-10-16', workers=workers)
            with self.assertRaises(ValueError):
                intake.run('2026-10-16', '2026-10-10')
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
