import unittest,sys,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import news,newsroom,housing,community
class NewsroomTests(unittest.TestCase):
 def test_all_articles_use_editorial_body(self):
  for a in news.articles():
   html=news.detail(a)
   self.assertNotIn('Wat betekent dit voor jou?',html)
   self.assertNotIn('Wat speelt er?',html)
   self.assertIn('Bronnen en verantwoording',html)
   self.assertIn('noindex,nofollow',html)
 def test_related_has_relevance_and_no_self(self):
  for a in news.articles():
   for b in newsroom.related_items(a):
    self.assertNotEqual(a['slug'],b['slug'])
    self.assertTrue(a['category']==b['category'] or set(a.get('municipalities',[])).intersection(b.get('municipalities',[])))
 def test_housing_is_local(self):
  self.assertIn('Amsterdamlaan 49',housing.property_cards('woerden'))
  self.assertNotIn('Amsterdamlaan 49',housing.property_cards('baarn'))
  for m in ['']+[x['slug'] for x in news.read('municipalities')]:
   self.assertIn('/wonen',community.tabs(m))
   self.assertIn('Wonen &amp; bouwen',housing.page(m))
 def test_past_deadline_not_open(self):
  self.assertIn('gesloten',housing.deadline_label({'deadline':'2026-03-09'},datetime.date(2026,10,11)))
