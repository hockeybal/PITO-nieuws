import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import news,promotions
class NavigationTests(unittest.TestCase):
 def test_local_article_navigation_and_rail(self):
  a=next(x for x in news.articles() if x['municipalities']==['vijfheerenlanden'])
  nav,rail=promotions.article_navigation(a)
  self.assertIn('/agenda/utrecht/vijfheerenlanden/vandaag',nav)
  self.assertIn('/nieuws/utrecht/vijfheerenlanden',nav)
  self.assertNotIn('/artikel/'+a['slug']+'"',rail)
  self.assertIn('Meer uit Vijfheerenlanden',rail)
 def test_municipality_assets_all_available_with_provenance(self):
  images=news.read('municipality-images')
  self.assertEqual(set(images),{m['slug'] for m in news.read('municipalities')})
  for m in images.values():
   self.assertTrue((news.ROOT/'static/images'/m['file']).is_file())
   self.assertFalse(m['file'].startswith('cloud-'))
   if m['kind']=='commons-photo':
    self.assertTrue(m['sourceUrl'].startswith('https://commons.wikimedia.org/'))
    self.assertTrue(m['licenseUrl'].startswith('https://'))
    self.assertTrue(m['author'])
 def test_ads_are_labeled_and_bounded(self):
  for page in [news.home(),news.detail(news.articles()[0])]:
   self.assertLessEqual(page.count('aria-label="Advertentie van PITO"'),2)
   self.assertIn('ADVERTENTIE · PITO',page)
