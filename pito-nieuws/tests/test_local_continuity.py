import unittest,datetime,os
from unittest.mock import patch
import agenda_views,news,app_content,environment_notices
class LocalContinuityTests(unittest.TestCase):
 def test_context_keeps_existing_image_parameter(self):
  html=news.context_links('<a href="/nieuws/utrecht/artikel/test?beeld=foto">Lees</a>','woerden')
  self.assertIn('beeld=foto&amp;gemeente=woerden',html)
 def test_sixty_day_window_and_pages(self):
  today=datetime.date(2026,10,13)
  rows=[dict(id=str(i),title='Event '+str(i),municipality='woerden',date=(today+datetime.timedelta(days=i)).isoformat(),url='https://pito.app/e/'+str(i),summary='',label='12:00') for i in range(65)]
  with patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-13'}),patch.object(app_content,'get',return_value=(rows,'connected')):
   first=agenda_views.page('woerden','agenda')
   third=agenda_views.page('woerden','agenda',page_number='3')
   self.assertEqual(first.count('class="agenda-card '),24)
   self.assertEqual(third.count('class="agenda-card '),12)
   self.assertIn('Event 59',third);self.assertNotIn('Event 60',third)
   self.assertIn('event-city',first)
 def test_month_and_city_filters_combine(self):
  rows=[dict(id='1',title='Woerden november',municipality='woerden',date='2026-11-03',url='https://pito.app/a',summary='',label=''),dict(id='2',title='Baarn november',municipality='baarn',date='2026-11-04',url='https://pito.app/b',summary='',label='')]
  with patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-13'}),patch.object(app_content,'get',return_value=(rows,'connected')):
   html=agenda_views.page('woerden','agenda',month='2026-11')
   self.assertIn('Woerden november',html);self.assertNotIn('Baarn november',html)
if __name__=='__main__':unittest.main()
