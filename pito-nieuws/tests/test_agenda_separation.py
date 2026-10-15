import unittest
from unittest.mock import patch
import agenda_views, seo

class AgendaSeparationTests(unittest.TestCase):
 def render(self,view='agenda',day='vandaag',**kw):
  def row(title,highlight):
   return dict(id=title,title=title,agendaHighlight=highlight,municipality='woerden',date=seo.today().isoformat(),url='https://example.org/'+title,summary='',category='Sport')
  with patch('news.app_content.get',return_value=([row('Agendapunt',True),row('Dagactiviteit',False),row('Ongeclassificeerd',None)],'connected')):
   return agenda_views.page('woerden',view,day,**kw)
 def test_agenda_has_only_explicit_agenda_items_and_no_activity_filters(self):
  html=self.render(category='Sport',q='absent')
  self.assertIn('>Agendapunt</a>',html)
  self.assertNotIn('>Dagactiviteit</a>',html)
  self.assertNotIn('>Ongeclassificeerd</a>',html)
  self.assertNotIn('agenda-category-tabs',html)
  self.assertNotIn('app-event-filters',html)
 def test_week_is_agenda_with_week_navigation_base(self):
  html=self.render(day='deze-week')
  self.assertIn('app-month-group',html)
  self.assertIn('/agenda/utrecht/woerden/deze-week?',html)
  self.assertNotIn('app-event-filters',html)
 def test_activity_filters_stay_on_activity_route(self):
  html=self.render('vandaag',category='Sport')
  self.assertIn('class="app-event-filters" action="/agenda/utrecht/woerden/vandaag"',html)
  self.assertIn('<strong>Dagactiviteit</strong>',html)
