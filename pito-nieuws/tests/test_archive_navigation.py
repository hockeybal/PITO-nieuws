import unittest,sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import news,archive_navigation as archive,media_library
class ArchiveTests(unittest.TestCase):
 def test_earlier_is_local_and_not_current(self):
  for m in news.read('municipalities'):
   for a in archive.earlier(m['slug']):
    self.assertIn(m['slug'],a['municipalities']);self.assertFalse(news.ranking.is_recent(a))
 def test_all_archive_articles_reachable_on_pages(self):
  expected={a['slug'] for a in news.articles() if '2026-07-11'<=a['sourcePublishedAt']<=news.seo.today().isoformat()}
  seen=set()
  for page in range(1,(len(expected)+11)//12+1):
   html=news.home(period='archive',sort='latest',page=str(page))
   seen.update(a for a in expected if '/artikel/'+a in html)
  self.assertEqual(expected,seen)
 def test_home_exposes_archive_and_topic_history(self):
  html=news.home('woerden')
  self.assertIn('Alle nieuwsberichten',html);self.assertIn('rubriek-politiek',html)
  self.assertIn('Filters &amp; archief',html) if 'Filters &amp; archief' in html else self.assertIn('Filters & archief',html)
 def test_combined_current_and_archive_images_do_not_repeat(self):
  html=news.home('woerden')
  photos=re.findall(r'<img src="(/news-static/images/[^"]+)"',html)
  self.assertEqual(len(photos),len(set(photos)))
 def test_related_excludes_current_article(self):
  a=news.articles()[0];html=archive.related(a)
  self.assertNotIn('/artikel/'+a['slug']+'"',html)
  self.assertIn('Dit onderwerp in de hele provincie',html)
