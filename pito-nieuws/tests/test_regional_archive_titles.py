import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_archive_intake import extract
class RegionalArchiveTitles(unittest.TestCase):
 def test_local_publisher_span_headline_is_discovered(self):
  html=b'<a class="main-feed-item" href="/lokaal/verkeer/12345/brug"><span id="feed-title">Brug wordt volgende week onderzocht</span><p>Deze alinea hoort niet in de opgeslagen titel.</p></a>'
  config={'origin':'https://example.test','article':r'^/lokaal/','local':True,'regionalRun':True}
  items,pages=extract(html,'https://example.test/',config)
  self.assertEqual(len(items),1)
  self.assertEqual(items[0]['sourceTitle'],'Brug wordt volgende week onderzocht')
  self.assertEqual(items[0]['dateEvidence'],'missing')
  self.assertEqual(pages,[])
 def test_external_article_is_not_followed(self):
  config={'origin':'https://example.test','article':r'^/lokaal/','local':True,'regionalRun':True}
  items,_=extract(b'<a href="https://other.test/lokaal/story"><span id="feed-title">Een artikel op een andere website</span></a>','https://example.test/',config)
  self.assertEqual(items,[])
if __name__=='__main__':unittest.main()
