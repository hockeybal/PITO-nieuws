import unittest,datetime
from unittest.mock import patch
import homepage_agenda,seo
class AgendaHomepageTests(unittest.TestCase):
 def test_week_is_remaining_calendar_week_and_keeps_city(self):
  now=datetime.date(2026,10,14)
  def row(i,day,city='woerden',**extra):return dict(id=i,title=i,url='https://example.org/'+i,date=day,municipality=city,**extra)
  rows=[row('past','2026-10-13'),row('today','2026-10-14'),row('sunday','2026-10-18'),row('monday','2026-10-19'),row('other','2026-10-14','utrecht'),row('cancel','2026-10-14',cancelled=True)]
  self.assertEqual([r['id'] for r in homepage_agenda.select(rows,'woerden',now,True)],['today','sunday'])
  with patch('seo.today',return_value=now):
   self.assertTrue(seo.matches(rows[2],'deze-week'));self.assertFalse(seo.matches(rows[3],'deze-week'))
 def test_sunday_and_empty_feed(self):
  with patch('seo.today',return_value=datetime.date(2026,10,18)):
   self.assertFalse(seo.matches({'date':'2026-10-19'},'deze-week'))
  with patch('news.app_content.get',return_value=([],'unavailable')):
   html=homepage_agenda.block('woerden');self.assertIn('tijdelijk niet beschikbaar',html);self.assertIn('/woerden/deze-week',html)
 def test_unconfigured_agenda_preserves_city_without_claiming_an_empty_live_feed(self):
  with patch('news.app_content.get',return_value=([],'not_configured')):
   html=homepage_agenda.block('woerden')
  self.assertIn('actuele PITO-agenda is nog niet beschikbaar',html)
  self.assertIn('/woerden/deze-week',html)
  self.assertNotIn('Vandaag in de regio',html)
 def test_region_link_only_replaces_city_when_regional_events_exist(self):
  row=dict(id='regional',title='Regionaal evenement',municipality='baarn',date=seo.today().isoformat(),url='https://example.org/regional')
  with patch('news.app_content.get',return_value=([row],'connected')):
   html=homepage_agenda.block('woerden')
  self.assertIn('Vandaag in de regio',html)
  self.assertIn('href="/agenda/utrecht/vandaag"',html)
