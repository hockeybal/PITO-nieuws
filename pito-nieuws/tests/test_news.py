import os,sys,json,unittest,tempfile,shutil,threading,urllib.request,urllib.error,xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import news,server,intake,import_strapi,app_content,community
class CoreTests(unittest.TestCase):
 def test_feed_dates_and_tracking(self):
  raw=b'<rss><channel><item><title>Relevant</title><link>https://www.politie.nl/news?utm_source=a</link><pubDate>Fri, 09 Oct 2026 10:00:00 +0200</pubDate></item><item><title>Old</title><link>https://www.politie.nl/old</link><pubDate>Mon, 01 Sep 2025 10:00:00 +0200</pubDate></item><item><title>Missing</title><link>javascript:alert(1)</link></item></channel></rss>'
  items,skipped=intake.parse_feed(raw,{'id':'politie','articleHosts':['www.politie.nl']},'2026-10-03','2026-10-10');self.assertEqual(len(items),1);self.assertEqual(skipped,2);self.assertEqual(items[0]['sourceUrl'],'https://www.politie.nl/news');self.assertEqual(items[0]['status'],'needs_review');self.assertNotIn('body',items[0])
 def test_xml_entities_rejected(self):
  with self.assertRaises(ValueError):intake.parse_feed(b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss/>',{},'2026-10-03','2026-10-10')
 def test_agenda_publication_expiry_and_dedup(self):
  a={'id':'app1','title':'Gemeenschapsavond','status':'published','show_on_web':True,'municipality':'Woerden','url':'https://pito.app/activiteiten/1','occurrences':[{'date':'2026-10-01'},{'date':'2026-10-11'},{'date':'2026-10-11'}]}
  self.assertEqual(len(app_content.normalize({'data':{'activities':[a,a]}},'2026-10-10')),1);a['status']='draft';self.assertEqual(app_content.normalize({'activities':[a]},'2026-10-10'),[])
 def test_import_drafts(self):
  for a in news.read('articles'):
   p=import_strapi.payload(a)['data'];self.assertIsNone(p['publishedAt']);self.assertEqual(p['reviewStatus'],'needs_review' if a['reviewStatus']!='approved' else 'approved')
 def test_html_escape(self):
  a=dict(news.read('articles')[0]);a['title']='<script>alert(1)</script>';s=news.detail(a);self.assertNotIn('<script>alert(1)</script>',s);self.assertIn('&lt;script&gt;',s)
class ServerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);shutil.copytree(ROOT/'data',cls.root/'data')
  cls.oldcommunityroot=community.ROOT;community.ROOT=cls.root;cls.oldroot=server.ROOT;cls.olddata=news.DATA;server.ROOT=cls.root;news.DATA=cls.root/'data'
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.origin=f'http://127.0.0.1:{cls.http.server_port}';cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join();server.ROOT=cls.oldroot;news.DATA=cls.olddata;community.ROOT=cls.oldcommunityroot;cls.tmp.cleanup()
 def get(self,path):
  try:
   with urllib.request.urlopen(self.origin+path) as r:return r.status,r.read().decode()
  except urllib.error.HTTPError as r:return r.code,r.read().decode()
 def post(self,data,token=server.TOKEN,endpoint="/api/news/review"):
  req=urllib.request.Request(self.origin+endpoint,data=json.dumps(data).encode(),headers={'Origin':self.origin,'X-Pito-CSRF':token,'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as r:return r.code,json.load(r)
 def test_all_municipalities(self):
  ms=news.read('municipalities');self.assertEqual(len(ms),26);self.assertEqual(len({m['slug'] for m in ms}),26)
  for m in ms:
   code,s=self.get(news.BASE+'/'+m['slug']);self.assertEqual(code,200);self.assertIn(m['name'],s)
  self.assertEqual(self.get(news.BASE+'/buitenland')[0],404)
 def test_filter_and_search(self):
  _,s=self.get(news.BASE+'/woerden');self.assertIn('woerden-geen-vuurwerkontheffingen',s);self.assertNotIn('griftpark-toezicht-na-online-oproep',s.split('Ook in de provincie Utrecht')[0])
  _,s=self.get(news.BASE+'?q=onvindbaarzz');self.assertIn('Nog geen berichten voor deze selectie',s)
 def test_draft_not_public(self):
  a=next(a for a in news.read('articles') if a['reviewStatus']=='draft');self.assertEqual(self.get(news.url(a))[0],404)
 def test_feeds_and_seo(self):
  code,s=self.get('/nieuws/feed.xml');self.assertEqual(code,200);ET.fromstring(s)
  code,s=self.get('/nieuws/sitemap.xml');ET.fromstring(s);self.assertNotIn('/nieuws/utrecht/artikel/',s) # unpublished previews are excluded
  _,s=self.get(news.BASE);self.assertIn('rel="canonical"',s);self.assertIn('noindex,nofollow',s)
 def test_review_security_and_persistence(self):
  a=dict(news.read('articles')[0]);a.update(reviewStatus='approved',confirmed=False,reviewer='',reviewNote='')
  self.assertEqual(self.post(a,token='wrong')[0],403);self.assertEqual(self.post(a)[0],400)
  a.update(confirmed=True,reviewer='TESTREDACTEUR',reviewNote='Test in tijdelijke database');self.assertEqual(self.post(a)[0],200);self.assertEqual(news.read('articles')[0]['reviewStatus'],'approved')
  a['reviewStatus']='rejected';self.assertEqual(self.post(a)[0],200);self.assertEqual(self.get(news.url(a))[0],404)
 def test_archive_routing_and_recent_feed(self):
  code,s=self.get(news.BASE+'?periode=archive&maand=2026-07');self.assertEqual(code,200);self.assertIn('uplg-programma-landelijk-gebied-juli',s);self.assertNotIn('amersfoort-spoorwerk-12-18-oktober',s)
  _,s=self.get('/nieuws/feed.xml');self.assertNotIn('utrecht-stroomnet-pauze-aangekondigd-april',s)
  code,s=self.get('/nieuws/selectie');self.assertEqual(code,200)
  code,s=self.get('/nieuws/onderzoek');self.assertEqual(code,200);self.assertIn('Zoekdekking per instelling',s)
  code,s=self.get('/nieuws/kies?gemeente=utrecht&periode=archive&maand=2026-07');self.assertEqual(code,200);self.assertIn('uplg-programma-landelijk-gebied-juli',s)
 def test_ranking_edit_validates_and_persists(self):
  a=dict(news.read('articles')[0]);a.update({'rank_'+k:v for k,v in a['ranking'].items()});a.update(rank_impact='5',rank_reason='Testmotivering',rank_activeUntil='2026-10-15',rank_audienceNeed='service',rank_audienceReason='Andere reisroute nodig',rank_actionFrom='2026-10-12',rank_actionUntil='2026-10-18')
  self.assertEqual(self.post(a)[0],200);self.assertEqual(news.read('articles')[0]['ranking']['impact'],5)
  self.assertEqual(news.read('articles')[0]['ranking']['audienceNeed'],'service');self.assertEqual(news.read('articles')[0]['ranking']['actionUntil'],'2026-10-18')
  a['rank_impact']='9';self.assertEqual(self.post(a)[0],400);self.assertEqual(news.read('articles')[0]['ranking']['impact'],5)
 def test_community_endpoint_is_private_pending(self):
  d=dict(kind='story',municipality='baarn',authorName='Test Auteur',email='test@example.test',confirmed=True,title='Privé testverhaal',summary='Test',body='Testinhoud',evidence='Testcontrole')
  self.assertEqual(self.post(d,token='wrong',endpoint='/api/community/submit')[0],403)
  self.assertEqual(self.post(d,endpoint='/api/community/submit')[0],200)
  a=community.records()[-1];self.assertEqual(a['status'],'pending')
  self.assertEqual(self.get('/nieuws/community/artikel/'+a['id'])[0],404)
  _,s=self.get(news.BASE+'/baarn?weergave=community');self.assertNotIn('Privé testverhaal',s);self.assertNotIn('test@example.test',s)
 def test_existing_homepage_retained(self):
  code,s=self.get('/');self.assertEqual(code,200)
  if os.environ.get('PITO_STANDALONE')=='1':
   with urllib.request.urlopen(self.origin+'/') as r:self.assertEqual(r.url,self.origin+news.BASE)
   self.assertIn('news-site',s);self.assertIn('PITO Nieuws',s)
  else:
   self.assertIn('pn-news-link',s);self.assertIn('pito-navigation',s)
 def test_invalid_host(self):
  req=urllib.request.Request(self.origin+news.BASE,headers={'Host':'evil.test'})
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
  self.assertEqual(e.exception.code,403)
if __name__=='__main__':unittest.main(verbosity=2)
