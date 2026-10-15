import unittest,news,ranking
class ProvinceSelection(unittest.TestCase):
 def test_club_report_stays_local(self):
  rows=news.articles();sport=next(a for a in rows if a['slug']=='sportlust-beker-excelsior-maassluis')
  self.assertTrue(news.selected(sport,'woerden'))
  self.assertNotIn(sport,ranking.province_frontpage(rows))
 def test_current_news_precedes_old_club_story(self):
  rows=ranking.order(news.articles())[:4]
  self.assertNotIn('sportlust-beker-excelsior-maassluis',[a['slug'] for a in rows])
