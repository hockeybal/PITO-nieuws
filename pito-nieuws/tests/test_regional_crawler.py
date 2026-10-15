import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_archive_intake import extract,SOURCES
class CrawlerTests(unittest.TestCase):
 def test_external_links_and_missing_dates_are_not_fabricated(self):
  html=b'<article><a href="/nieuws/nieuws/1/een-lokaal-verhaal">Een lokaal nieuwsverhaal</a></article><a href="https://other.test/nieuws/x">Een vreemd nieuwsverhaal</a><a href="/search?page=2" rel="next">Volgende</a>'
  rows,pages=extract(html,'https://www.woerdensecourant.nl/',SOURCES[0])
  self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['sourcePublishedAt']);self.assertEqual(pages,['https://www.woerdensecourant.nl/search?page=2'])
 def test_multi_region_requires_local_evidence(self):
  html=b'<article><a href="/nieuws/test">Nieuws uit Gouda over verkeer</a></article><article><a href="/nieuws/local">Nieuws uit Harmelen over verkeer</a></article>'
  rows,_=extract(html,'https://rtvmiddenholland.nl/',SOURCES[2]);self.assertEqual(len(rows),1);self.assertIn('Harmelen',rows[0]['sourceTitle'])

 def test_image_is_candidate_not_permission(self):
  html=b'<article><a href="/nieuws/nieuws/1/een-lokaal-verhaal"><h2>Een lokaal nieuwsverhaal</h2><img src="/foto.jpg"></a></article>'
  rows,_=extract(html,'https://www.woerdensecourant.nl/',SOURCES[0])
  image=rows[0]['imageCandidates'][0]
  self.assertFalse(image['publicationAllowed']);self.assertEqual(image['rightsStatus'],'unknown')
 def test_regional_navigation_is_not_an_article(self):
  config=dict(SOURCES[0],regionalRun=True,article=r'^/.+')
  rows,_=extract(b'<a href="/archive">Bekijk de vorige edities</a><article><a href="/nieuws/bericht"><h2>Nieuws over een lokale weg</h2></a></article>','https://www.woerdensecourant.nl/',config)
  self.assertEqual(len(rows),1)
