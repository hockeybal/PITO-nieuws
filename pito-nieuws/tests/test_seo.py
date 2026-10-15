import unittest,sys,datetime,json,re,threading,urllib.request,urllib.error,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import seo,news,community,app_content,server

class SeoTests(unittest.TestCase):
 def activity(self,**kw):
  a=dict(id='event1',title='Lokale activiteit',municipality='woerden',date='2026-10-10',label='10 oktober, 14:00',summary='Een eigen omschrijving.',url='https://pito.app/activiteit/1',occurrenceKey='occ1',startDate='2026-10-10T14:00:00+02:00',locationName='Buurthuis',address='Voorbeeldstraat 1, Woerden')
  a.update(kw);return a
 def test_weekend_saturday_sunday_and_monday(self):
  for current,expected in [('2026-10-09',['2026-10-10','2026-10-11']),('2026-10-11',['2026-10-11']),('2026-10-12',['2026-10-17','2026-10-18'])]:
   with patch.dict(os.environ,{'PITO_EDITION_DATE':current}):
    actual=[d for d in ['2026-10-10','2026-10-11','2026-10-12','2026-10-17','2026-10-18'] if seo.matches({'date':d},'dit-weekend')]
    self.assertEqual(actual,expected)
 def test_unique_canonicals_and_titles(self):
  with patch.object(app_content,'get',return_value=([],'not_configured')):
   for m in news.read('municipalities'):
    for view,day in [('agenda','vandaag'),('vandaag','vandaag'),('vandaag','morgen'),('vandaag','dit-weekend')]:
     html=community.page(m['slug'],view,day)
     self.assertIn('href="'+seo.origin()+seo.view_path(m['slug'],view,day)+'"',html)
     self.assertIn('noindex,nofollow',html)
     self.assertIn(m['name'],html)
 def test_event_schema_only_when_data_is_complete(self):
  a=self.activity();html=seo.activity_detail(a)
  self.assertIn('"@type": "Event"',html)
  self.assertIn(a['startDate'],html)
  self.assertNotIn('"@type": "Event"',seo.activity_detail(dict(a,address=None)))
  self.assertEqual(seo.activity_path(a),seo.activity_path(dict(a,title='Gewijzigde kop')))
  stable=dict(a,occurrenceId='fixed')
  self.assertEqual(seo.activity_path(stable),seo.activity_path(dict(stable,date='2026-10-12')))
  self.assertNotIn('\"@type\": \"Event\"',seo.activity_detail(dict(a,startDate='geen datum')))
 def test_past_detail_remains_available(self):
  with patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-11'}):self.assertIn('Deze activiteit is afgelopen',seo.activity_detail(self.activity()))
 def test_sitemap_excludes_preview_and_empty_agendas(self):
  with patch.object(app_content,'get',return_value=([],'not_configured')):
   self.assertNotIn('<url>',seo.sitemap());self.assertNotIn('<url>',seo.news_sitemap())
  with patch.object(app_content,'get',return_value=([self.activity()],'connected')),patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-10'}):
   xml=seo.sitemap();self.assertIn('/agenda/utrecht/woerden/vandaag',xml);self.assertNotIn('/agenda/utrecht/baarn',xml)
 def test_article_never_uses_source_date_as_publication(self):
  a=dict(news.articles()[0]);a.pop('webPublishedAt',None)
  self.assertNotIn('"datePublished"',news.detail(a))
  a.update(publicationStatus='published',webPublishedAt='2026-10-10T12:00:00+02:00')
  self.assertIn('"datePublished": "2026-10-10T12:00:00+02:00"',news.detail(a))
 def test_http_routes_redirects_and_unknown_places(self):
  http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
  origin='http://127.0.0.1:'+str(http.server_port)
  try:
   for path in ['/agenda/utrecht/woerden','/agenda/utrecht/rhenen/vandaag','/agenda/utrecht/woerden/dit-weekend']:
    with urllib.request.urlopen(origin+path) as r:self.assertEqual(r.status,200)
   with urllib.request.urlopen(origin+'/nieuws/utrecht/woerden?weergave=vandaag&dag=morgen') as r:self.assertTrue(r.url.endswith('/agenda/utrecht/woerden/morgen'))
   with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(origin+'/agenda/utrecht/fantasiestad')
   self.assertEqual(error.exception.code,404)
  finally:http.shutdown();http.server_close();thread.join()
if __name__=='__main__':unittest.main()
