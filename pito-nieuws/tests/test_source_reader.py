import sys,unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import read_source_documents as reader
class ReaderTests(unittest.TestCase):
 def extract(self,html,url='https://example.org/news'):
  with patch.object(reader,'fetch',return_value=(BeautifulSoup(html,'html.parser'),'fixture.html')):
   return reader.one({'sourceUrl':url,'sourcePublishedAt':'2026-10-13'})
 def test_elementor_ignores_unrelated_main(self):
  r=self.extract('<h1>Nieuws</h1><main><p>'+('Onjuiste teaser. '*20)+'</p></main><div class="elementor-widget-theme-post-content"><p>'+('Echte artikeltekst. '*20)+'</p></div>')
  self.assertEqual(r['readStatus'],'read');self.assertNotIn('Onjuiste',str(r['sourceParagraphs']))
 def test_rtv_divs_are_read(self):
  r=self.extract('<h1>Nieuws</h1><div class="api-text"><div class="text">'+('Broninhoud. '*25)+'</div></div>','https://www.rtvutrecht.nl/nieuws/1/test')
  self.assertEqual(r['readStatus'],'read');self.assertFalse(r['humanVerified'])
 def test_headline_alone_not_read(self):
  self.assertEqual(self.extract('<h1>Alleen een kop</h1>')['readStatus'],'no_article_body')
 def test_og_title_without_h1(self):
  r=self.extract('<meta property="og:title" content="Clubnieuws"><article><p>'+('Clubverslag. '*25)+'</p></article>')
  self.assertEqual(r['pageTitle'],'Clubnieuws');self.assertEqual(r['readStatus'],'read')
 def test_visible_publication_dates_override_feed_date(self):
  for url,cls,stamp,expected in [('https://www.leusden.nl/test','news-single-date','07 oktober 2026','2026-10-07'),('https://www.omroepzout.nl/test','elementor-post-info__item--type-custom','11 oktober  2026 om 10:57','2026-10-11')]:
   r=self.extract('<h1>Nieuws</h1><div class="'+cls+'">'+stamp+'</div><article><p>'+('Activiteit op 24 december 2026. '*10)+'</p></article>',url)
   self.assertEqual(r['sourcePublishedAt'],expected)
 def test_main_content_wins_over_maintenance_article(self):
  r=self.extract('<article id="calamity"><p>'+('Onderhoud aan de website. '*10)+'</p></article><div role="main"><h1>Scholen krijgen prioriteit</h1><p>'+('Gemeentelijk besluit over scholen. '*10)+'</p></div>','https://www.derondevenen.nl/nieuws/test')
  self.assertNotIn('Onderhoud',str(r['sourceParagraphs']));self.assertIn('Gemeentelijk',str(r['sourceParagraphs']))
if __name__=='__main__':unittest.main()
