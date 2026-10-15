import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from intake import merge_signal,parse_feed
from vru_intake import parse as parse_vru
from amber_intake import parse as parse_amber
from prepare_news_draft import prepare

class SourcePipelineTests(unittest.TestCase):
 def test_duplicate_across_municipalities(self):
  known={};inbox=[];a={'sourceUrl':'https://www.politie.nl/example','sourceId':'a','sourceMunicipality':'woerden','fingerprint':'1'}
  self.assertEqual(merge_signal(known,inbox,a,'now'),1)
  self.assertEqual(merge_signal(known,inbox,{**a,'sourceId':'b','sourceMunicipality':'utrecht'},'later'),0)
  self.assertEqual(len(inbox),1);self.assertEqual(inbox[0]['sourceMunicipalities'],['utrecht','woerden'])
 def test_feed_image_is_not_publication_permission(self):
  raw=b'<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Nieuws</title><link>https://www.ad.nl/woerden/a</link><pubDate>Mon, 12 Oct 2026 08:00:00 +0200</pubDate><media:content url="https://images.example/a.jpg" medium="image" /></item></channel></rss>'
  rows,_=parse_feed(raw,{'id':'ad','articleHosts':['www.ad.nl'],'coverageCandidates':['woerden']},'2026-07-12','2026-10-12')
  self.assertEqual(rows[0]['municipalities'],[])
  self.assertEqual(rows[0]['municipalityCandidates'],['woerden'])
  self.assertFalse(rows[0]['imageCandidates'][0]['publicationAllowed'])
 def test_closed_incident_date_is_not_publication(self):
  raw=b'<div class="incident-result"><h2>Test</h2><div class="incident-result__meta-data">vrijdag 09 oktober 2026 - 16:40 | status: <span>Gesloten</span> | soort: Brand</div><a href="/incidenten/test/">Lees verder</a>'
  rows,dates,next_url=parse_vru(raw,'https://vru.nl/incidenten/','2026-04-11','2026-10-11')
  self.assertEqual(rows[0]['incidentStatus'],'Gesloten');self.assertNotIn('sourcePublishedAt',rows[0]);self.assertIsNone(next_url)
 def test_cancel_never_active_and_personal_content_not_stored(self):
  raw=json.dumps([{'AlertId':'1','MessageId':'2','Type':'Cancel','State':'Actual','AlertLevel':'10','Message':{'Title':'Sensitive name'}}]).encode()
  rows=parse_amber(raw);self.assertFalse(rows[0]['activeCandidate']);self.assertNotIn('Sensitive',json.dumps(rows))
 def test_invalid_alert_response(self):
  with self.assertRaises(ValueError):parse_amber(b'{}')
 def test_headline_alone_cannot_become_draft(self):
  with self.assertRaises(ValueError):prepare({'sources':[],'facts':[],'municipalities':['woerden'],'title':'Test'})
 def test_draft_keeps_evidence_and_never_publishes(self):
  b={'sources':[{'id':'s','url':'https://www.woerden.nl/','checkedAt':'2026-10-11'}],'facts':[{'id':'f','sourceIds':['s'],'statement':'Fixture','verified':True}],'paragraphs':[{'text':'Fixture','factIds':['f']}],'municipalities':['woerden'],'title':'Fixture','summary':'Fixture'}
  d=prepare(b);self.assertIsNone(d['data']['publishedAt']);self.assertEqual(d['data']['reviewStatus'],'needs_review')
  b['paragraphs'][0]['factIds']=['missing']
  with self.assertRaises(ValueError):prepare(b)
if __name__=='__main__':unittest.main()
