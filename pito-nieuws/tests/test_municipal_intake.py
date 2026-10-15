import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from bs4 import BeautifulSoup
from municipal_archive_intake import listing_date
class MunicipalDates(unittest.TestCase):
 def soup(self,s):return BeautifulSoup(s,'html.parser')
 def test_event_date_in_teaser_is_not_publication_date(self):
  self.assertIsNone(listing_date(self.soup('<div class="news-list-content"><h2>Weg dicht</h2><p>Vanaf 1 oktober 2026 sluiten wij de weg.</p></div>')))
 def test_explicit_archive_date_wins_over_event_date(self):
  self.assertEqual(listing_date(self.soup('<li><span class="objectinfo">28 september 2026</span><p>Werk start 12 oktober 2026</p></li>')),'2026-09-28')
 def test_machine_timestamp(self):
  self.assertEqual(listing_date(self.soup('<time datetime="2026-08-02T12:00:00+02:00">Vandaag</time>')),'2026-08-02')
