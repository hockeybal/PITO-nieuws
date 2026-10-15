import unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_base_archive import build
class BaseArchiveTests(unittest.TestCase):
 def test_window_deduplication_and_unknown_dates(self):
  data={'municipalities':[{'slug':'woerden','name':'Woerden'}],'articles':[{'slug':'a','sourceUrl':'https://x/a','sourcePublishedAt':'2026-08-02','municipalities':['woerden']},{'slug':'old','sourcePublishedAt':'2026-06-01'}],'municipal-archive-inbox':[{'sourceUrl':'https://x/a','sourcePublishedAt':'2026-08-02','municipality':'woerden'}],'inbox':[{'sourceUrl':'https://x/a','sourcePublishedAt':'2026-08-02'},{'sourceUrl':'https://x/unknown'}]}
  with patch('prepare_base_archive.read',side_effect=lambda n:data.get(n,[])):
   articles,leads,cities=build('2026-07-13','2026-10-13')
  self.assertEqual(len(articles),1);self.assertEqual(len(leads),2)
  self.assertEqual(leads[0]['linkedArticles'],['a']);self.assertEqual(cities[0]['articles'],1)
  self.assertIsNone(leads[1]['sourcePublishedAt']);self.assertFalse(leads[1]['publicationAllowed'])
 def test_conflicting_dates_do_not_invent_date(self):
  data={'municipalities':[],'inbox':[{'sourceUrl':'https://x/a','sourcePublishedAt':'2026-08-01'}],'regional-archive-inbox':[{'sourceUrl':'https://x/a','sourcePublishedAt':'2026-09-01'}]}
  with patch('prepare_base_archive.read',side_effect=lambda n:data.get(n,[])):
   _,leads,_=build('2026-07-13','2026-10-13')
  self.assertEqual(leads[0]['dateStatus'],'missing_or_conflicting')
