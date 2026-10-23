"""Offline checks for the scheduled coordinator and its publication boundary."""

import contextlib
import datetime
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'scripts'))
import news_pipeline


class PipelineRuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        self.source_url = 'https://example.org/bericht'
        self.articles = [{
            'slug': 'bestaand-artikel', 'sourceUrl': self.source_url,
            'reviewStatus': 'approved', 'verifiedAt': '2026-10-15',
            'body': 'De bestaande artikeltekst blijft ongewijzigd.',
        }]
        self.write('articles', self.articles)
        self.write('inbox', [{
            'id': 'rss-one', 'sourceUrl': self.source_url,
            'sourceTitle': 'Werk aan de brug in Woerden',
            'sourcePublishedAt': '2026-10-16',
            'municipalityCandidates': ['woerden'],
            'status': 'approved', 'publicationAllowed': True,
        }])
        self.write('source-documents', [{
            'sourceUrl': self.source_url, 'readStatus': 'read',
            'extractionVersion': 'article-body-v2',
        }])
        patcher = patch.object(news_pipeline, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name, value):
        (self.data / (name + '.json')).write_text(json.dumps(value))

    def read(self, name):
        return json.loads((self.data / (name + '.json')).read_text())

    def invoke(self, *arguments, side_effect=None):
        result = subprocess.CompletedProcess([], 0, stdout='adapter completed', stderr='')
        output = io.StringIO()
        with patch.object(sys, 'argv', ['news_pipeline.py', *arguments]), \
                patch.object(news_pipeline.subprocess, 'run', return_value=result,
                             side_effect=side_effect) as run, \
                contextlib.redirect_stdout(output):
            exit_code = 0
            try:
                news_pipeline.main()
            except SystemExit as error:
                exit_code = error.code
        return exit_code, self.read('pipeline-report'), run

    def test_default_window_rolls_from_requested_end_and_reaches_adapter(self):
        exit_code, report, run = self.invoke('--adapters', 'rss', '--end', '2026-10-16')
        self.assertEqual(exit_code, 0)
        self.assertEqual(report['window'], ['2026-10-09', '2026-10-16'])
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--start') + 1], '2026-10-09')
        self.assertEqual(command[command.index('--end') + 1], '2026-10-16')
        self.assertEqual(report['status'], 'ok')
        self.assertGreaterEqual(report['completedAt'], report['runAt'])

    def test_calendar_boundaries_and_explicit_start(self):
        examples = [
            (['--end', '2027-01-01', '--lookback-days', '1'],
             ['2026-12-31', '2027-01-01']),
            (['--end', '2028-03-01', '--lookback-days', '2'],
             ['2028-02-28', '2028-03-01']),
            (['--end', '2028-03-01', '--lookback-days', '366'],
             ['2027-03-01', '2028-03-01']),
            (['--end', '2026-10-16', '--lookback-days', '14'],
             ['2026-10-02', '2026-10-16']),
            (['--start', '2026-10-16', '--end', '2026-10-16'],
             ['2026-10-16', '2026-10-16']),
        ]
        for arguments, expected in examples:
            with self.subTest(arguments=arguments):
                exit_code, report, _ = self.invoke('--adapters', 'rss', *arguments)
                self.assertEqual(exit_code, 0)
                self.assertEqual(report['window'], expected)

    def test_default_end_uses_amsterdam_date_across_utc_midnight(self):
        real_datetime = datetime.datetime

        class FrozenDateTime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                instant = real_datetime(2026, 12, 31, 23, 30,
                                        tzinfo=datetime.timezone.utc)
                return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

        with patch.object(news_pipeline.datetime, 'datetime', FrozenDateTime):
            exit_code, report, _ = self.invoke('--adapters', 'rss')
        self.assertEqual(exit_code, 0)
        self.assertEqual(report['window'], ['2026-12-25', '2027-01-01'])

    def test_invalid_arguments_reject_before_adapter_or_writes(self):
        examples = [
            ['--lookback-days', '0'], ['--lookback-days', '367'],
            ['--lookback-days', '-1'], ['--lookback-days', '1.5'],
            ['--adapters', 'does-not-exist'],
            ['--start', '2026-10-17', '--end', '2026-10-16'],
            ['--end', '2026-02-30'], ['--start', 'not-a-date'],
        ]
        with patch.object(news_pipeline.subprocess, 'run') as run:
            for arguments in examples:
                with self.subTest(arguments=arguments), \
                        patch.object(sys, 'argv', ['news_pipeline.py', *arguments]), \
                        contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises((SystemExit, ValueError)):
                        news_pipeline.main()
            run.assert_not_called()
        self.assertFalse((self.data / 'pipeline-report.json').exists())
        self.assertFalse((self.data / 'editorial-queue.json').exists())

    def test_adapter_failure_is_reported_nonzero_and_other_adapters_continue(self):
        outcomes = [
            subprocess.CompletedProcess([], 9, stdout='', stderr='upstream unavailable'),
            subprocess.CompletedProcess([], 0, stdout='second adapter completed', stderr=''),
        ]
        exit_code, report, run = self.invoke(
            '--adapters', 'rss,vru', '--end', '2026-10-16', side_effect=outcomes)
        self.assertEqual(exit_code, 1)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(report['status'], 'error')
        self.assertEqual(report['runs'][0]['exitCode'], 9)
        self.assertIn('upstream unavailable', report['runs'][0]['result'])
        self.assertEqual(report['runs'][1]['exitCode'], 0)
        self.assertEqual(report['queueSize'], 1)
        self.assertIn('completedAt', report)

    def test_process_timeout_or_launch_error_persists_failure_report(self):
        for error in (subprocess.TimeoutExpired(['adapter'], 3600),
                      OSError('cannot execute adapter')):
            with self.subTest(error=type(error).__name__):
                exit_code, report, _ = self.invoke(
                    '--adapters', 'rss', '--end', '2026-10-16', side_effect=error)
                self.assertEqual(exit_code, 1)
                self.assertEqual(report['status'], 'error')
                self.assertTrue(report['runs'][0]['error'])
                self.assertIn('completedAt', report)
                self.assertEqual(report['queueSize'], 1)

    def test_queue_only_never_launches_adapter_or_publishes_existing_article(self):
        exit_code, report, run = self.invoke('--queue-only', '--end', '2026-10-16')
        self.assertEqual(exit_code, 0)
        run.assert_not_called()
        self.assertEqual(report['runs'], [])
        self.assertIs(report['autoPublish'], False)
        self.assertEqual(self.read('articles'), self.articles)
        queue = self.read('editorial-queue')
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['linkedArticles'][0]['slug'], 'bestaand-artikel')
        self.assertEqual(queue[0]['processingStatus'], 'article_prepared')
        self.assertEqual(queue[0]['status'], 'signal_only')
        self.assertIs(queue[0]['publicationAllowed'], False)

    def test_report_becomes_visible_only_as_complete_snapshot(self):
        previous = {'status': 'previous complete report'}
        self.write('pipeline-report', previous)
        target = self.data / 'pipeline-report.json'
        real_replace = Path.replace
        report_replacements = []

        def checked_replace(path, destination):
            if Path(destination) == target:
                self.assertEqual(json.loads(target.read_text()), previous)
                pending = json.loads(path.read_text())
                self.assertIn('completedAt', pending)
                self.assertIs(pending['autoPublish'], False)
                report_replacements.append(pending)
            return real_replace(path, destination)

        with patch.object(Path, 'replace', checked_replace):
            _, report, _ = self.invoke('--adapters', 'rss', '--end', '2026-10-16')
        self.assertEqual(report_replacements, [report])

    def test_failed_report_replace_preserves_previous_valid_snapshot(self):
        previous = {'status': 'previous complete report'}
        self.write('pipeline-report', previous)
        target = self.data / 'pipeline-report.json'
        real_replace = Path.replace

        def failing_replace(path, destination):
            if Path(destination) == target:
                raise OSError('replacement failed')
            return real_replace(path, destination)

        with patch.object(Path, 'replace', failing_replace):
            with self.assertRaisesRegex(OSError, 'replacement failed'):
                self.invoke('--adapters', 'rss', '--end', '2026-10-16')
        self.assertEqual(self.read('pipeline-report'), previous)


if __name__ == '__main__':
    unittest.main()
