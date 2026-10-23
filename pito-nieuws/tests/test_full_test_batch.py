import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import full_test_batch as batch


class BatchBoundaryTests(unittest.TestCase):
    def test_polling_cannot_send_credentials_to_another_domain_or_job(self):
        identity = '11111111-1111-1111-1111-111111111111'
        good = 'https://api.firecrawl.dev/v2/batch/scrape/'+identity+'?skip=100'
        self.assertEqual('/v2/batch/scrape/'+identity+'?skip=100', batch.status_path(good, identity))
        for value in ('https://evil.example/v2/batch/scrape/'+identity,
                      'http://api.firecrawl.dev/v2/batch/scrape/'+identity,
                      'https://api.firecrawl.dev.evil.example/v2/batch/scrape/'+identity,
                      'https://api.firecrawl.dev/v2/batch/scrape/22222222-2222-2222-2222-222222222222',
                      '//evil.example/v2/batch/scrape/'+identity):
            with self.subTest(value=value), self.assertRaises(ValueError):
                batch.status_path(value, identity)

    def plan(self, folder, maximum):
        entries = [{'url':'https://www.utrecht.nl/nieuws/'+str(i), 'metadata':{'sourcePublishedAt':'2026-10-21'}} for i in range(2)]
        (folder/'crawl-plan.json').write_text(json.dumps({'entries':entries,'maxPaidRequests':maximum}))
        (folder/'preflight.json').write_text(json.dumps({'items':[dict(e,allowed=True,delay=1) for e in entries]}))

    def test_reservation_prevents_a_second_paid_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); (folder/'batch-jobs.json').write_text('{}')
            with patch.object(batch,'api') as api, self.assertRaises(ValueError): batch.submit(folder)
            api.assert_not_called()

    def test_frozen_total_is_checked_before_contacting_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); self.plan(folder,1)
            with patch.object(batch,'public_url'), patch.object(batch,'api') as api, self.assertRaises(ValueError): batch.submit(folder)
            api.assert_not_called()
            self.assertFalse((folder/'batch-jobs.json').exists())


if __name__=='__main__': unittest.main()
