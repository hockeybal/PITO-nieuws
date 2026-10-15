import unittest,json,re,sys,datetime,gzip
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import news,seo,dossiers,coverage
from scripts.ndw_intake import parse,decode
class ProfessionalTests(unittest.TestCase):
 def test_clean_topic_canonical_and_single_h1(self):
  for m in ['','woerden','utrechtse-heuvelrug']:
   for category in news.CATEGORIES:
    path=seo.topic_path(m,category);html=news.home(m,category=category,period='archive',sort='latest',route_path=path)
    self.assertEqual(len(re.findall(r'<h1(?:\s|>)',html)),1)
    self.assertIn('rel="canonical" href="'+seo.origin()+path+'"',html)
 def test_home_legacy_pagination_canonicalizes_to_overview(self):
  html=news.home(page='2');self.assertIn('rel="canonical" href="'+seo.origin()+news.BASE+'"',html)
  self.assertNotIn('archive-pages',html)
 def test_schema_and_social_image_follow_article(self):
  html=news.detail(news.articles()[0]);raw=re.search(r'<script type="application/ld\+json">(.*?)</script>',html).group(1);data=json.loads(raw)
  graph=data['@graph'];article=next(n for n in graph if n['@type']=='NewsArticle')
  self.assertEqual(article['publisher']['@id'],seo.origin()+'/#newsroom');self.assertIn('twitter:card',html)
  self.assertEqual(len([n for n in graph if n['@type']=='WebPage']),1)
  self.assertNotIn('datePublished',article)
 def test_empty_topic_does_not_invent_articles(self):
  html=news.home('lopik',category='Veiligheid',period='archive',sort='latest',route_path=seo.topic_path('lopik','Veiligheid'))
  self.assertIn('noindex,nofollow',html)
 def test_coverage_does_not_claim_full_archive(self):
  html=coverage.page();self.assertIn('nog onvolledig',html);self.assertIn('Directe raad nodig',html)
 def test_dossiers_are_existing_stories(self):
  known={a['slug'] for a in news.articles()}
  for key in dossiers.DOSSIERS:
   self.assertTrue({a['slug'] for a in dossiers.items(key)}<=known)

class DatexTests(unittest.TestCase):
 now=datetime.datetime(2026,10,10,15,30,tzinfo=datetime.timezone.utc)
 def xml(self,status='real',start='2026-10-10T12:00:00Z',end='2026-10-11T12:00:00Z',coords='52.1 5.1 52.11 5.11',published='2026-10-10T15:29:00.000760797Z'):
  return f'<d xmlns="http://datex2.eu/schema/3/messageContainer"><publicationTime>{published}</publicationTime><situation><informationStatus>{status}</informationStatus><confidentiality>noRestriction</confidentiality><situationRecord id="a"><overallStartTime>{start}</overallStartTime><overallEndTime>{end}</overallEndTime><posList>{coords}</posList></situationRecord></situation></d>'.encode()
 def test_real_candidate_stays_unpublished(self):
  rows,_=parse(self.xml(),self.now);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'needs_review');self.assertEqual(rows[0]['municipalities'],[])
 def test_test_expired_and_outside_records_are_excluded(self):
  for xml in [self.xml(status='test'),self.xml(end='2026-10-10T12:30:00Z'),self.xml(coords='53.2 6.6')]:self.assertEqual(parse(xml,self.now)[0],[])
 def test_stale_and_future_snapshots_are_rejected(self):
  for t in ['2026-10-10T10:00:00Z','2026-10-10T18:00:00Z','bad']:
   with self.assertRaises(ValueError):parse(self.xml(published=t),self.now)
 def test_entities_and_gzip_bombs_rejected(self):
  with self.assertRaises(ValueError):decode(b'<!DOCTYPE x><x/>')
  with self.assertRaises(ValueError):decode(gzip.compress(b'X'*25_000_001))
if __name__=='__main__':unittest.main()
