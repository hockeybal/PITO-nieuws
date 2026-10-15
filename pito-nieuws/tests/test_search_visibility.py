import unittest,sys,os,datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import search_visibility as v,seo,news,municipality_overview

class SearchVisibilityTests(unittest.TestCase):
 def test_requires_explicit_production_and_canonical_host(self):
  for config,expected in [({},False),({'PITO_SITE_MODE':'production'},False),({'PITO_SITE_MODE':'production','PITO_PUBLIC_URL':'http://pitonieuws.nl'},False),({'PITO_SITE_MODE':'production','PITO_PUBLIC_URL':'https://pitonieuws.nl'},True)]:
   with patch.dict(os.environ,config,clear=True):self.assertEqual(v.production(),expected)
 def test_publication_is_not_inferred_from_source_or_future_date(self):
  a=dict(reviewStatus='approved',publicationStatus='published',webPublishedAt='2026-01-01T10:00:00+01:00')
  self.assertTrue(v.published(a))
  for overrides in ({'reviewStatus':'preview'},{'webPublishedAt':'invalid'},{'webPublishedAt':'2026-01-01'},{'webPublishedAt':'2099-01-01T10:00:00+01:00'},{'publicationStatus':'draft'}):self.assertFalse(v.published(dict(a,**overrides)))
 def test_canonical_keeps_location_and_page_not_tracking(self):
  self.assertEqual(v.canonical_path('/nieuws/nuttige-adressen?utm_source=x&gemeente=woerden'),'/nieuws/nuttige-adressen?gemeente=woerden')
  self.assertEqual(v.canonical_path('/nieuws/utrecht?pagina=2&sortering=latest'),'/nieuws/utrecht?pagina=2')
 def test_shared_index_and_sitemap_policy(self):
  with patch.object(v,'production',return_value=True),patch.object(v,'catalogue',return_value={'/nieuws/utrecht/woerden'}):
   self.assertTrue(v.robots_meta('/nieuws/utrecht/woerden').startswith('index,'))
   for p in ['/nieuws/redactie','/nieuws/utrecht/woerden?q=politie','/nieuws/utrecht/woerden?pagina=2']:self.assertTrue(v.robots_meta(p).startswith('noindex,'))
   self.assertIn('/nieuws/utrecht/woerden',seo.sitemap())
 def test_production_excludes_drafts_from_article_collection(self):
  with patch.object(v,'production',return_value=True):self.assertTrue(all(v.published(a) for a in news.articles()))
 def test_all_municipalities_linked_without_javascript(self):
  html=municipality_overview.render()
  for m in news.read('municipalities'):self.assertIn('href="'+news.BASE+'/'+m['slug']+'"',html)
 def test_robots_preview_and_production(self):
  with patch.object(v,'production',return_value=False):self.assertIn('Disallow: /\n',v.robots_txt())
  with patch.object(v,'production',return_value=True):
   self.assertIn('Sitemap:',v.robots_txt());self.assertNotIn('Disallow: /\n',v.robots_txt())
if __name__=='__main__':unittest.main()
