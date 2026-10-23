import unittest
from unittest.mock import patch
import news,starter,agenda_views
class LocationSources(unittest.TestCase):
 def test_picker_keeps_filter_and_day(self):
  h=starter.render([], 'utrecht','vandaag','morgen',{'categorie':'Sport','q':'fiets'})
  self.assertIn('name="dag" value="morgen"',h)
  self.assertIn('name="q" value="fiets"',h)
  self.assertIn('name="gemeente" value="woerden"',h)
  self.assertIn('municipality-picker',h)
 def test_province_and_city_are_distinct(self):
  with patch('news.app_content.get',return_value=([],'local_preview')):
   self.assertIn('Agenda van de provincie Utrecht',agenda_views.page('','agenda'))
   self.assertIn('Gemeenteagenda van Utrecht',agenda_views.page('utrecht','agenda'))
 def test_article_source_is_not_collapsed(self):
  a=news.articles()[0]
  with patch('newsroom.related',return_value=''),patch('promotions.article_navigation',return_value=('','')):
   h=news.detail(a)
  self.assertIn('<div class="article-sources" aria-label="Bronvermelding">',h)
  self.assertIn(news.e(a['sourceUrl']),h)
  self.assertIn(news.e(a['sourceName']),h)
  self.assertNotRegex(h,r'<details[^>]*(?:sourcebox|article-sources)')
  self.assertIn('href="/nieuws/verantwoording#correcties"',h)
