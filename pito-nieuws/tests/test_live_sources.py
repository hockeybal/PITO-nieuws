"""Public RSS headline boundary, geography, freshness and read-through rendering."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import live_sources

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


class LiveSourceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data = Path(self.folder.name)
        self.patcher = patch.object(live_sources, 'DATA', self.data)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.write('municipalities', [{'slug': 'utrecht', 'name': 'Utrecht'},
                                      {'slug': 'zeist', 'name': 'Zeist'},
                                      {'slug': 'utrechtse-heuvelrug', 'name': 'Utrechtse Heuvelrug'}])
        self.sources = [{'id': 'regional', 'name': 'Regionaal Utrecht', 'feed': 'https://example.org/feed',
                         'articleHosts': ['example.org'], 'coverageCandidates': ['utrecht', 'zeist']},
                        {'id': 'local', 'name': 'Gemeente Zeist', 'municipality': 'zeist',
                         'feed': 'https://zeist.example.org/feed', 'articleHosts': ['zeist.example.org']}]
        self.write('sources', self.sources)

    def write(self, name, data):
        (self.data / (name + '.json')).write_text(json.dumps(data))

    def item(self, **updates):
        result = {'sourceTitle': 'Een actuele bronkop', 'sourceUrl': 'https://example.org/bericht',
                  'sourcePublishedAt': '2026-10-16', 'sourceTimestamp': '2026-10-16T11:00:00+00:00',
                  'sourceId': 'regional', 'status': 'needs_review', 'municipalities': []}
        result.update(updates)
        return result

    def test_publication_time_not_ingestion_time_controls_window_and_future(self):
        values = [self.item(), self.item(sourceUrl='https://example.org/oud', sourceTimestamp='2026-10-02T11:59:59+00:00'),
                  self.item(sourceUrl='https://example.org/toekomst', sourceTimestamp='2026-10-16T12:00:01+00:00'),
                  self.item(sourceUrl='https://example.org/geen-datum', sourceTimestamp='', sourcePublishedAt=''),
                  self.item(sourceUrl='https://example.org/geen-zone', sourceTimestamp='2026-10-16T11:00:00')]
        for item in values:
            item['lastSeenAt'] = NOW.isoformat()
        self.write('inbox', values)
        self.assertEqual([x['url'] for x in live_sources.items(now=NOW)], ['https://example.org/bericht'])

    def test_timezones_are_compared_as_instants_and_displayed_in_dutch_time(self):
        self.write('inbox', [self.item(sourceTimestamp='2026-10-16T15:00:00+03:00'),
                             self.item(sourceUrl='https://example.org/future', sourceTimestamp='2026-10-16T13:01:00+01:00')])
        rows = live_sources.items(now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn('16-10-2026 14:00', live_sources._list(rows))
        self.assertIn('2026-10-16T14:00:00+02:00', live_sources._list(rows))

    def test_date_only_source_preserves_date_without_inventing_a_time(self):
        self.write('inbox', [self.item(sourceTimestamp='', sourcePublishedAt='2026-10-15')])
        rows = live_sources.items(now=NOW)
        self.assertEqual(len(rows), 1)
        html = live_sources._list(rows)
        self.assertIn('datetime="2026-10-15"', html)
        self.assertNotIn('00:00', html)

    def test_unsafe_links_empty_titles_and_non_feed_imports_are_rejected(self):
        links = ['javascript:alert(1)', '//example.org/a', 'http://example.org/a',
                 'https://user:secret@example.org/a', 'https://127.0.0.1/a',
                 'https://localhost/a', 'https://wrong.example.org/a', 'https://example.org/\\bad']
        rows = [self.item(sourceUrl=url) for url in links]
        rows += [self.item(sourceTitle=' \n '), self.item(sourceId='unknown'), self.item(sourceId=['bad'])]
        self.write('inbox', rows)
        self.assertEqual(live_sources.items(now=NOW), [])

    def test_tracking_and_fragment_variants_are_one_canonical_source_link(self):
        self.write('inbox', [self.item(sourceUrl='https://example.org/bericht?utm_source=x#part'),
                             self.item(sourceUrl='https://example.org/bericht?fbclid=abc'), self.item()])
        rows = live_sources.items(now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], 'https://example.org/bericht')

    def test_general_utrecht_source_and_coverage_candidates_do_not_mean_city(self):
        self.write('inbox', [self.item(sourceTitle='Provincie Utrecht begint nieuwe campagne',
                                      municipalityCandidates=['utrecht'], sourceMunicipalities=['utrecht'])])
        self.assertEqual(len(live_sources.items(now=NOW)), 1)
        self.assertEqual(live_sources.items('utrecht', now=NOW), [])
        self.assertEqual(live_sources.items('zeist', now=NOW), [])

    def test_local_source_contract_and_explicit_title_markers_select_places(self):
        self.write('inbox', [self.item(sourceTitle='Nieuw plan voor de wijk', sourceId='local', sourceUrl='https://zeist.example.org/nieuws'),
                             self.item(sourceTitle='Utrecht - Nieuwe plannen voor station', sourceUrl='https://example.org/city'),
                             self.item(sourceTitle='Nieuw wandelpad in Utrechtse Heuvelrug', sourceUrl='https://example.org/heuvelrug')])
        self.assertEqual([x['sourceName'] for x in live_sources.items('zeist', now=NOW)], ['Gemeente Zeist'])
        self.assertEqual([x['url'] for x in live_sources.items('utrecht', now=NOW)], ['https://example.org/city'])
        self.assertEqual([x['url'] for x in live_sources.items('utrechtse-heuvelrug', now=NOW)], ['https://example.org/heuvelrug'])

    def test_confirmed_geography_used_but_unconfirmed_assignments_ignored(self):
        self.write('inbox', [self.item(municipalities=['zeist'], geographyStatus='confirmed'),
                             self.item(sourceUrl='https://example.org/guess', municipalities=['zeist'])])
        self.assertEqual([x['url'] for x in live_sources.items('zeist', now=NOW)], ['https://example.org/bericht'])

    def test_rendering_escapes_headlines_and_does_not_import_body_or_images(self):
        self.write('inbox', [self.item(sourceTitle='<img src=x onerror=alert(1)> & bericht', body='PRIVATE BODY',
                                      imageCandidates=[{'url': 'https://example.org/copyright.jpg'}])])
        html = live_sources._list(live_sources.items(now=NOW))
        self.assertIn('&lt;img', html)
        self.assertNotIn('<img', html)
        self.assertNotIn('PRIVATE BODY', html)
        self.assertNotIn('copyright.jpg', html)
        self.assertIn('rel="noopener noreferrer external"', html)

    def test_national_feed_requires_confirmed_regional_relevance(self):
        self.sources.append({'id': 'ns-live', 'name': 'NS nieuws', 'feed': 'https://nieuws.ns.nl/feed/nl',
                             'articleHosts': ['nieuws.ns.nl']})
        self.write('sources', self.sources)
        self.write('inbox', [self.item(sourceId='ns-live', sourceTitle='Nieuwe dienstregeling voor Nederland', sourceUrl='https://nieuws.ns.nl/landelijk'),
                             self.item(sourceId='ns-live', sourceTitle='Werkzaamheden bij Utrecht Centraal', sourceUrl='https://nieuws.ns.nl/utrecht'),
                             self.item(sourceId='ns-live', sourceTitle='Geen treinen in Zeist', sourceUrl='https://nieuws.ns.nl/zeist')])
        self.assertEqual({x['url'] for x in live_sources.items(now=NOW)},
                         {'https://nieuws.ns.nl/utrecht', 'https://nieuws.ns.nl/zeist'})
        self.assertEqual(live_sources.items('utrecht', now=NOW), [])

    def test_provincial_source_scope_keeps_headlines_without_city_assignment(self):
        self.sources.append({'id': 'vru', 'name': 'Veiligheidsregio Utrecht', 'provinceWide': True,
                             'feed': 'https://vru.example.org/feed', 'articleHosts': ['vru.example.org']})
        self.write('sources', self.sources)
        self.write('inbox', [self.item(sourceId='vru', sourceTitle='Nieuwe brandweerwagens', sourceUrl='https://vru.example.org/bericht')])
        self.assertEqual(len(live_sources.items(now=NOW)), 1)
        self.assertEqual(live_sources.items('utrecht', now=NOW), [])

    def test_partial_failure_retains_previous_success_without_claiming_all_feeds_work(self):
        self.write('intake-report', {'runAt': '2026-10-16T11:50:00+00:00', 'sources': [
            {'source': 'regional', 'status': 'ok', 'finishedAt': '2026-10-16T11:51:00+00:00'},
            {'source': 'local', 'status': 'error', 'lastSuccessAt': '2026-10-16T10:00:00+00:00'}]})
        status = live_sources.feed_status(now=NOW)
        self.assertEqual((status['configured'], status['ok'], status['errors']), (2, 1, 1))
        self.assertFalse(status['stale'])
        self.assertTrue(status['degraded'])
        self.assertIn('1 van 2', live_sources._summary(status))
        self.assertIn('1 met een fout', live_sources._summary(status))
        self.assertEqual(status['lastSuccessAt'].hour, 11)
        local = next(row for row in status['sources'] if row['id'] == 'local')
        self.assertEqual(local['lastSuccessAt'].hour, 10)

    def test_reachable_undated_or_old_feed_is_not_reported_as_recent(self):
        self.write('intake-report', {'runAt': '2026-10-16T11:50:00+00:00', 'sources': [
            {'source': 'regional', 'status': 'ok', 'freshnessStatus': 'undated'},
            {'source': 'local', 'status': 'ok', 'newestReceived': '2026-09-01'}]})
        status = live_sources.feed_status(now=NOW)
        self.assertEqual(status['ok'], 2)
        self.assertEqual(status['recent'], 0)
        self.assertFalse(status['degraded'])
        self.assertEqual(status['sources'][0]['freshnessStatus'], 'undated')
        self.assertEqual(status['sources'][1]['freshnessStatus'], 'outside_window')

    def test_status_table_explains_failures_and_warnings_with_html_escaping(self):
        import news
        self.write('intake-report', {'runAt': '2026-10-16T11:50:00+00:00', 'sources': [
            {'source': 'regional', 'status': 'error', 'error': 'HTTP 403 <script>alert(1)</script>'},
            {'source': 'local', 'status': 'ok', 'freshnessStatus': 'undated',
             'warning': 'Publicatiedatum ontbreekt & wordt overgeslagen'}]})
        with patch.object(live_sources, '_now', return_value=NOW), patch.object(news, 'layout', side_effect=lambda title, body, *args: body):
            html = live_sources.status_page()
        self.assertIn('HTTP 403 &lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Publicatiedatum ontbreekt &amp; wordt overgeslagen', html)

    def test_old_or_missing_reports_never_claim_live_success(self):
        self.write('intake-report', {'runAt': '2026-10-15T11:00:00+00:00', 'sources': [{'source': 'regional', 'status': 'ok'}]})
        status = live_sources.feed_status(now=NOW)
        self.assertTrue(status['stale'])
        self.assertEqual(status['unknown'], 1)
        self.assertIn('meer dan twee uur', live_sources._summary(status))
        self.write('intake-report', {'runAt': '2026-10-17T11:00:00+00:00', 'sources': None})
        status = live_sources.feed_status(now=NOW)
        self.assertIsNone(status['runAt'])
        self.assertIsNone(status['lastSuccessAt'])

    def test_reads_new_data_each_request_and_missing_files_fail_closed(self):
        self.assertEqual(live_sources.items(now=NOW), [])
        self.write('inbox', [self.item()])
        self.assertEqual(len(live_sources.items(now=NOW)), 1)
        (self.data / 'inbox.json').write_text('{truncated')
        self.assertEqual(live_sources.items(now=NOW), [])
        status = live_sources.feed_status(now=NOW)
        self.assertEqual(status['unknown'], 2)


if __name__ == '__main__':
    unittest.main()
