import sys,unittest,datetime,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ranking,news
class RankingTests(unittest.TestCase):
 def setUp(self):
  # These fixtures describe a fixed edition; the wall clock must not age them.
  import os
  from unittest.mock import patch
  clock=patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-10'})
  clock.start();self.addCleanup(clock.stop)

 def record(self,**extra):
  a={'slug':'test','category':'Bestuur','municipalities':['woerden'],'sourceUrl':'https://example.org/test','sourcePublishedAt':'2026-10-10','ranking':{'impact':5,'reach':5,'urgency':5,'duration':5,'actionability':5}};a.update(extra);return a
 def test_max_and_expired_urgency(self):
  a=self.record();self.assertEqual(ranking.score(a),100);a['ranking']['activeUntil']='2026-10-09';self.assertEqual(ranking.score(a),85)
 def test_old_or_future_is_not_recent(self):
  for day in ['2026-04-10','2026-10-11']:
   a=self.record(sourcePublishedAt=day);self.assertFalse(ranking.is_recent(a));self.assertEqual(ranking.breakdown(a)['urgency'],0);self.assertEqual(ranking.breakdown(a)['freshness'],0)
 def test_cluster_latest_wins_and_latest_sort(self):
  old=self.record(sourcePublishedAt='2026-05-01');new=self.record(slug='new',sourcePublishedAt='2026-07-01');self.assertEqual([a['slug'] for a in ranking.order([old,new])],['new'])
 def test_diversity_does_not_drop_items(self):
  items=[self.record(slug=str(i),sourceUrl='https://example.org/'+str(i)) for i in range(4)];items[3]['category']='Verkeer';ordered=ranking.order(items);self.assertEqual({a['category'] for a in ordered[:2]},{'Bestuur','Verkeer'});self.assertEqual(len(ordered),4)
 def test_invalid_scores(self):
  for x in [-1,6,'x',True]:
   r=dict(self.record()['ranking'],impact=x,reason='Test')
   with self.assertRaises(ValueError):ranking.validate(r)
 def test_latest_uses_source_time_and_normalizes_timezone(self):
  earlier=self.record(slug='z-earlier',sourceUrl='https://example.org/earlier',sourcePublishedAt='2026-10-10',sourcePublishedAtExact='2026-10-10T10:00:00+02:00')
  later=self.record(slug='a-later',sourceUrl='https://example.org/later',sourcePublishedAt='2026-10-10T09:00:00Z')
  self.assertEqual(['a-later','z-earlier'],[a['slug'] for a in ranking.order([earlier,later],'latest')])
 def test_source_date_is_not_replaced_by_new_test_import_date(self):
  old=self.record(sourcePublishedAt='2026-10-10',webPublishedAt='2026-10-21T12:00:00Z')
  new=self.record(slug='new',sourcePublishedAt='2026-10-21T08:00:00Z')
  self.assertLess(ranking.chronology_key(old),ranking.chronology_key(new))
 def test_archive_month_and_pagination(self):
  s=news.home(period='archive',month='2026-07',sort='latest');self.assertIn('voorbereiding-nieuw-kindcentrum-noorderwaard-gestart',s);self.assertNotIn('amersfoort-spoorwerk-12-18-oktober',s)
  s=news.home();self.assertNotIn('houten-het-rond-ontwikkeling-mei',s)
  self.assertIn('data-latest-next',news.home(period='archive'))
  import re
  s=news.home(period='archive',sort='latest',page='4')
  rows=re.findall(r'<li class="latest-row">.*?</li>',s,re.S)
  headings=[re.search(r'<h2><a href="([^"]+)">',row).group(1) for row in rows]
  by_url={news.url(a):a for a in news.articles()}
  days=[by_url[u.split('?')[0]]['sourcePublishedAt'] for u in headings if u.split('?')[0] in by_url]
  self.assertEqual(days,sorted(days,reverse=True));self.assertGreater(len(days),1)
 def test_article_categories_dates_and_ranking_are_valid(self):
  for a in news.articles():
   self.assertIn(a['category'],news.CATEGORIES)
   published=datetime.date.fromisoformat(a['sourcePublishedAt'][:10])
   self.assertLessEqual(published,datetime.date.today())
   ranking.validate(a['ranking'])
if __name__=='__main__':unittest.main()
