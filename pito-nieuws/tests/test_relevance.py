import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import news,ranking
class RelevanceTests(unittest.TestCase):
 def setUp(self):
  # These fixtures describe a fixed edition; the wall clock must not age them.
  import os
  from unittest.mock import patch
  clock=patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-10'})
  clock.start();self.addCleanup(clock.stop)

 def story(self,slug='s',**rank):
  return {'slug':slug,'sourceUrl':'https://example.org/'+slug,'sourcePublishedAt':'2026-10-10','category':'Verkeer','reviewStatus':'preview','municipalities':['baarn'],'ranking':dict(impact=3,audienceNeed='service',audienceReason='Reis plannen.',**rank)}
 def test_alert_requires_approval_reviewer_and_same_day_check(self):
  a=self.story(actionFrom='2026-10-09',actionUntil='2026-10-12',alertConfirmed=True,alertCheckedOn='2026-10-10')
  self.assertEqual(ranking.relevance_tier(a),2)
  a.update(reviewStatus='approved',reviewer='Redacteur');self.assertEqual(ranking.relevance_tier(a),3)
  a['ranking']['alertCheckedOn']='2026-10-09';self.assertEqual(ranking.relevance_tier(a),2)
  a['ranking']['actionUntil']='2026-10-09';self.assertEqual(ranking.relevance_tier(a),1)
 def test_old_and_future_never_time_priority(self):
  a=self.story(actionFrom='2026-10-09',actionUntil='2026-10-15')
  for day in ['2026-09-01','2026-10-11']:
   a['sourcePublishedAt']=day;self.assertEqual(ranking.relevance_tier(a),1)
 def test_dated_service_beats_undated_incident_without_clicks(self):
  practical=self.story(actionFrom='2026-10-12',actionUntil='2026-10-18')
  incident=self.story('incident');incident['ranking']={'impact':5};incident['clicks']=10000000
  self.assertEqual(ranking.order([incident,practical])[0]['slug'],'s')
  self.assertEqual(ranking.order([incident,practical],'impact')[0]['slug'],'incident')
 def test_diversity_never_displaces_alert(self):
  a=self.story('alert',actionFrom='2026-10-09',actionUntil='2026-10-12',alertConfirmed=True,alertCheckedOn='2026-10-10');a.update(reviewStatus='approved',reviewer='Redacteur')
  items=[a]
  for i in range(8):
   x=self.story(str(i));x['ranking']['audienceNeed']='explanation';items.append(x)
  result=ranking.order(items);self.assertEqual(result[0]['slug'],'alert');self.assertEqual(len(result),9)
 def test_bad_annotations_are_not_boosted(self):
  for extra in [{'audienceNeed':'fake'},{'audienceReason':''},{'actionFrom':'garbage'},{'actionFrom':'2026-10-12','actionUntil':'2026-10-10'}]:
   a=self.story();a['ranking'].update(extra);self.assertEqual(ranking.relevance_tier(a),0)
   with self.assertRaises(ValueError):ranking.validate_audience(a['ranking'])
 def test_editorial_overview_links_to_independent_chronological_archive(self):
  s=news.home();self.assertIn('class="news-opening"',s);self.assertNotIn('Waarom dit bericht?',s)
  self.assertIn('periode=archive&sortering=latest',s)
  self.assertIn('data-latest-rows',news.home(period='archive',sort='latest'))
  self.assertIn('waarde',news.research_page())
 def test_local_filter_remains_hard_boundary(self):
  for slug in ['baarn','woerden']:
   items=ranking.order([a for a in news.articles() if news.selected(a,slug)])
   self.assertTrue(all(slug in a['municipalities'] or a.get('provinceWide') for a in items))
 def test_import_preserves_audience_metadata(self):
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
  import import_strapi
  a=self.story();self.assertEqual(import_strapi.payload(a)['data']['ranking'],a['ranking'])
if __name__=='__main__':unittest.main()
