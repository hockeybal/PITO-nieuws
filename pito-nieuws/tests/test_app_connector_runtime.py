import copy
import io
import json
import os
import unittest
import urllib.request
from unittest.mock import Mock, patch

import app_content
import seo


def fixture(**updates):
    event = dict(id='event-1', title='Bestaande activiteit', municipality='woerden',
                 status='published', show_on_web=True, url='https://pito.app/activities/1',
                 occurrences=[dict(id='occurrence-1', date='2026-10-17', times_text='14.00',
                                   startDate='2026-10-17T14:00:00+02:00',
                                   endDate='2026-10-17T16:00:00+02:00')])
    event.update(updates)
    return {'contractVersion': 1, 'data': {'activities': [event]}}


class Response(io.BytesIO):
    def __init__(self, body, content_type='application/json', status=200):
        super().__init__(body)
        self.status = status
        self.headers = {'Content-Type': content_type}


class AppConnectorRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'PITO_SITE_MODE': 'production',
                              'PITO_PUBLIC_PREVIEW': '0',
                              'PITO_APP_CONTENT_URL': 'https://cms.example.test/shared',
                              'PITO_APP_CONTENT_TOKEN': 'private-secret'}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cache = patch.object(app_content, 'CACHE', dict(at=0, items=[], status='not_configured', config=''))
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def response(self, payload=None, **kwargs):
        return Response(json.dumps(payload if payload is not None else fixture()).encode(), **kwargs)

    def test_production_without_endpoint_never_falls_back_to_snapshot(self):
        with patch.dict(os.environ, {'PITO_APP_CONTENT_URL': ''}), patch.object(app_content, 'local_preview') as preview:
            self.assertEqual(app_content.get(), ([], 'not_configured'))
            preview.assert_not_called()

    def test_preview_keeps_explicit_local_snapshot_and_production_direct_reader_is_empty(self):
        with patch.dict(os.environ, {'PITO_APP_CONTENT_URL': '', 'PITO_SITE_MODE': 'preview'}), patch.object(app_content, 'local_preview', return_value=[{'id': 'local'}]):
            self.assertEqual(app_content.get(), ([{'id': 'local'}], 'local_preview'))
        self.assertEqual(app_content.local_preview(), [])

    def test_public_preview_without_endpoint_never_serves_snapshot(self):
        with patch.dict(os.environ, {'PITO_SITE_MODE': 'preview', 'PITO_PUBLIC_PREVIEW': '1',
                                    'PITO_APP_CONTENT_URL': ''}), patch.object(app_content, 'local_preview') as preview:
            self.assertEqual(app_content.get(), ([], 'not_configured'))
            preview.assert_not_called()
        with patch.dict(os.environ, {'PITO_SITE_MODE': 'preview', 'PITO_PUBLIC_PREVIEW': '1'}):
            self.assertEqual(app_content.local_preview(), [])

    def test_https_read_uses_server_token_and_cache_isolated_by_configuration(self):
        opener = Mock()
        opener.open.side_effect = [self.response(), self.response(fixture(title='Updated')),
                                   self.response(fixture(id='event-2'))]
        with patch.object(app_content.urllib.request, 'build_opener', return_value=opener):
            items, status = app_content.get()
            self.assertEqual(status, 'connected')
            self.assertEqual(items[0]['title'], 'Bestaande activiteit')
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer private-secret')
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 5)
            self.assertEqual(app_content.get(), (items, 'connected'))
            self.assertEqual(opener.open.call_count, 1)
            with patch.dict(os.environ, {'PITO_APP_CONTENT_TOKEN': 'changed-secret'}):
                self.assertEqual(app_content.get()[0][0]['title'], 'Updated')
            with patch.dict(os.environ, {'PITO_APP_CONTENT_URL': 'https://other.example.test/shared'}):
                self.assertEqual(app_content.get()[0][0]['id'], 'event-2')
        diagnostics = json.dumps(app_content.diagnostics())
        self.assertNotIn('secret', diagnostics)
        self.assertNotIn('example.test', diagnostics)

    def test_failed_refresh_discards_successful_cache_and_suppresses_sensitive_error(self):
        opener = Mock()
        opener.open.side_effect = [self.response(), OSError('private-secret https://cms.example.test/shared')]
        with patch.object(app_content.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(app_content.get()[1], 'connected')
            app_content.CACHE['at'] = 0
            self.assertEqual(app_content.get(), ([], 'unavailable'))
            self.assertEqual(app_content.diagnostics()['itemCount'], 0)
            self.assertEqual(app_content.diagnostics()['error'], 'refresh_failed')
            self.assertNotIn('secret', json.dumps(app_content.diagnostics()))
            self.assertIsNotNone(app_content.diagnostics()['lastSuccessAt'])

    def test_empty_complete_snapshot_withdraws_previous_events(self):
        opener = Mock()
        opener.open.side_effect = [self.response(), self.response({'activities': []})]
        with patch.object(app_content.urllib.request, 'build_opener', return_value=opener):
            self.assertTrue(app_content.get()[0])
            app_content.CACHE['at'] = 0
            self.assertEqual(app_content.get(), ([], 'connected'))

    def test_bad_endpoint_or_header_is_rejected_before_open(self):
        for url in ['http://cms.example.test/shared', 'http://localhost/shared',
                    'https://user:pass@cms.example.test/shared', 'file:///tmp/test',
                    'https://cms.example.test/shared#fragment']:
            with self.subTest(url=url), patch.dict(os.environ, {'PITO_APP_CONTENT_URL': url}), patch.object(app_content.urllib.request, 'build_opener') as build:
                self.assertEqual(app_content.get(), ([], 'unavailable'))
                build.assert_not_called()
        with patch.dict(os.environ, {'PITO_APP_CONTENT_TOKEN': 'private\nsecret'}), patch.object(app_content.urllib.request, 'build_opener') as build:
            self.assertEqual(app_content.get(), ([], 'unavailable'))
            build.assert_not_called()

    def test_redirects_cannot_forward_token(self):
        with self.assertRaises(ValueError):
            app_content._NoRedirect().redirect_request(
                urllib.request.Request('https://cms.example.test', headers={'Authorization': 'Bearer secret'}),
                None, 302, 'redirect', {}, 'https://other.example.test')

    def test_invalid_or_oversize_response_fails_closed(self):
        responses = [Response(b'{}'), Response(b'not-json'),
                     Response(b'{}', 'text/html'), Response(b'{}', status=206),
                     Response(b' ' * (app_content.MAX_RESPONSE_BYTES + 1))]
        for response in responses:
            with self.subTest(response=response), patch.object(app_content.urllib.request, 'build_opener') as build:
                app_content.CACHE['at'] = 0
                build.return_value.open.return_value = response
                self.assertEqual(app_content.get(), ([], 'unavailable'))

    def test_publication_flags_identity_and_cancellation(self):
        row = fixture()['data']['activities'][0]
        for updates in [dict(status='draft'), dict(show_on_web=False), dict(show_on_web='true')]:
            self.assertEqual(app_content.normalize(fixture(**updates), '2026-10-16', strict=True), [])
        no_identity = copy.deepcopy(row)
        del no_identity['occurrences'][0]['id']
        self.assertEqual(app_content.normalize({'activities': [no_identity]}, '2026-10-16', strict=True), [])
        self.assertEqual(len(app_content.normalize({'activities': [no_identity]}, '2026-10-16')), 1)
        first = app_content.normalize({'activities': [row]}, '2026-10-16', strict=True)[0]
        updated = copy.deepcopy(row)
        updated['title'] = 'Gewijzigde titel'
        updated['occurrences'][0].update(date='2026-10-18', startDate='2026-10-18T14:00:00+02:00',
                                         endDate='2026-10-18T16:00:00+02:00', cancelled=True)
        rows = app_content.normalize({'activities': [row, updated]}, '2026-10-16', strict=True)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['cancelled'])
        self.assertEqual(seo.activity_path(first), seo.activity_path(rows[0]))
        self.assertFalse(rows[0]['agendaHighlight'])
        self.assertTrue(app_content.normalize({'activities': [updated, row]}, '2026-10-16', strict=True)[0]['cancelled'])

    def test_invalid_dates_and_non_boolean_cancellation_are_not_live_events(self):
        for occurrence in [dict(id='x', date='2026-99-01'), dict(id='x', date=None),
                           dict(id='x', date='2026-10-17', cancelled='false'),
                           dict(id='x', date='2026-10-17', startDate='2026-10-17T12:00:00'),
                           dict(id='x', date='2026-10-17', startDate='2026-10-18T12:00:00+02:00')]:
            self.assertEqual(app_content.normalize(fixture(occurrences=[occurrence]), '2026-10-16', strict=True), [])
        self.assertEqual(app_content.normalize(fixture(cancelled=True), '2026-10-16', strict=True)[0]['cancelled'], True)

    def test_paginated_or_incomplete_payload_cannot_withdraw_unseen_events(self):
        for payload in [dict(activities=[], complete=False),
                        dict(activities=[], meta={'pagination': {'pageCount': 2}}),
                        dict(activities=[], contractVersion=True)]:
            with self.assertRaises(ValueError):
                app_content.normalize(payload, '2026-10-16', strict=True)


if __name__ == '__main__':
    unittest.main()
