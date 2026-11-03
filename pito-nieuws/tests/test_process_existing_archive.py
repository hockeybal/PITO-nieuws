import datetime as dt
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.process_existing_archive import process
from source_archive import SourceArchive


class ExistingArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root/'data'
        self.data.mkdir()
        self.output = self.root/'processed'
        self.now = dt.datetime(2026, 10, 30, tzinfo=dt.timezone.utc)
        self.save('municipalities', [{'slug': 'utrecht', 'name': 'Utrecht'}])
        self.save('sources', [{'id': 'utrecht', 'name': 'Gemeente Utrecht', 'url': 'https://example.org', 'articleHosts': ['example.org']}])

    def save(self, name, value):
        (self.data/(name+'.json')).write_text(json.dumps(value))

    def doc(self, path, **changes):
        return dict(sourceUrl='https://example.org/'+path, sourceTitle='Nieuwsbericht '+path,
                    sourcePublishedAt='2026-04-01', dateEvidence='source_page',
                    sourceParagraphs=['Een bewaarde alinea over de gemeente Utrecht. '*12],
                    readStatus='read', **changes)

    def run_archive(self):
        report = process(self.root, self.output, self.now)
        rows = json.loads((self.output/'records.json').read_text())
        return report, {r['sourceUrl']: r for r in rows}

    def test_all_dates_and_rows_are_kept_and_original_input_untouched(self):
        self.save('source-documents', [self.doc('oud'), self.doc('ander')])
        before = (self.data/'source-documents.json').read_bytes()
        report, rows = self.run_archive()
        self.assertEqual(report['recordsProcessed'], 2)
        self.assertEqual(report['sourceDateRange'], ['2026-04-01', '2026-04-01'])
        self.assertEqual(report['usableSourceTexts'], 2)
        self.assertEqual(report['counts']['duplicate_body_review'], 1)
        self.assertEqual((self.data/'source-documents.json').read_bytes(), before)
        self.assertTrue(all('original_html_missing' in r['issues'] for r in rows.values()))
        self.assertTrue(all(not r['publicationAllowed'] and not r['humanVerified'] for r in rows.values()))

    def test_editorial_exclusion_and_own_articles_are_preserved(self):
        self.save('source-documents', [self.doc('uitgesloten'), self.doc('eigen')])
        self.save('source-decisions', {'https://example.org/uitgesloten/': {'status': 'excluded', 'reason': 'Niet lokaal.'}})
        self.save('articles', [{'slug': 'eigen-tekst', 'sourceUrl': 'https://example.org/eigen/',
                              'title': 'Eigen titel', 'body': 'Eigen tekst.', 'reviewStatus': 'preview'}])
        report, rows = self.run_archive()
        self.assertEqual(rows['https://example.org/uitgesloten']['processingStatus'], 'excluded')
        self.assertEqual(rows['https://example.org/eigen']['processingStatus'], 'existing_own_article')
        self.assertEqual(report['ownArticleVersions'], 1)
        db = sqlite3.connect(self.output/'archive.sqlite3')
        self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT body FROM own_articles').fetchone()[0], 'Eigen tekst.')

    def test_date_conflicts_and_failed_reads_are_not_writing_ready(self):
        row = self.doc('conflict')
        self.save('source-documents', [row, dict(self.doc('incomplete'), readStatus='no_article_body')])
        self.save('inbox', [dict(row, sourcePublishedAt='2026-04-03')])
        _, rows = self.run_archive()
        self.assertEqual(rows['https://example.org/conflict']['processingStatus'], 'date_review')
        self.assertEqual(rows['https://example.org/incomplete']['processingStatus'], 'source_text_missing')

    def test_saved_html_is_recovered_without_a_fourteen_day_window(self):
        raw = ('<html><head><meta property="article:published_time" content="2026-04-01"></head>'
               '<body><article><h1>Ouder gemeentelijk bericht</h1><p>'+('Eerste inhoudelijke bronalinea. '*8)+
               '</p><p>'+('Tweede inhoudelijke bronalinea. '*8)+'</p></article></body></html>').encode()
        with SourceArchive(self.data) as archive:
            archive.enqueue({'sourceUrl': 'https://example.org/oud'}, 'utrecht')
            archive.save_raw('https://example.org/oud', raw, [], self.now)
            archive.finish('https://example.org/oud', self.now, 'outside_window')
        original = (self.data/'newsroom/source-archive.sqlite3').read_bytes()
        report, rows = self.run_archive()
        self.assertEqual(report['recoveredFromSavedHtml'], 1)
        self.assertTrue(rows['https://example.org/oud']['bodyUsable'])
        self.assertEqual(report['sourceDateRange'], ['2026-04-01', '2026-04-01'])
        self.assertEqual((self.data/'newsroom/source-archive.sqlite3').read_bytes(), original)

    def test_invalid_urls_and_untrusted_markup_are_safe(self):
        row = self.doc('veilig')
        row['sourceTitle'] = '<script>alert(1)</script>'
        self.save('source-documents', [row, {'sourceUrl': 'javascript:alert(1)'}])
        report, _ = self.run_archive()
        self.assertEqual(len(report['rejectedRecords']), 1)
        text = (self.output/'bronnenbibliotheek.html').read_text()
        self.assertNotIn('<script>alert(1)</script>', text)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', text)
        self.assertEqual(report['firecrawlRequests'], 0)
        self.assertEqual(report['cmsWrites'], 0)

    def test_structured_events_sharing_a_feed_url_keep_their_identities(self):
        self.save('ndw-inbox', [dict(id='one', sourceUrl='https://example.org/feed.xml', recordType='Closure'),
                                dict(id='two', sourceUrl='https://example.org/feed.xml', recordType='Roadworks')])
        report, _ = self.run_archive()
        self.assertEqual(report['structuredSignalRecords'], 2)
        self.assertEqual(report['structuredSignalCounts'], {'historical_traffic_snapshot': 2})
        self.assertEqual(len(json.loads((self.output/'signal-records.json').read_text())), 2)


if __name__ == '__main__':
    unittest.main()
