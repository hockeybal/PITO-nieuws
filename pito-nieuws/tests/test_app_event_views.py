import unittest,datetime
from unittest.mock import patch
import app_content,community,seo,agenda_views
class AppViews(unittest.TestCase):
 def rows(self):
  return [dict(id='one',municipality='woerden',title='Sportdag',category='Sport',date=seo.today().isoformat(),url='https://example.org/sport',label='12:00',summary='Een sportdag',images=[dict(url='https://example.org/'+str(i)+'.jpg',alt='Beeld',credit='Maker') for i in range(5)]),dict(id='two',municipality='woerden',title='Koffiemoment',category='Op de koffie gaan',date=seo.today().isoformat(),url='https://example.org/koffie',label='10:00',summary='')]
 def test_filters_use_existing_categories(self):
  self.assertEqual(len(agenda_views.categories()),11)
  with patch.object(app_content,'get',return_value=(self.rows(),'connected')):
   html=community.page('woerden','vandaag',category='Sport')
   self.assertIn('<strong>Sportdag</strong>',html);self.assertNotIn('<strong>Koffiemoment</strong>',html)
 def test_agenda_one_image_and_direct_link(self):
  html=community.activity(self.rows()[0],'agenda')
  self.assertEqual(html.count('<img '),1);self.assertIn('href="https://example.org/sport"',html)
 def test_activity_list_is_text_first(self):
  html=community.activity(self.rows()[0],'vandaag')
  self.assertNotIn('<img ',html);self.assertIn('https://example.org/sport',html)
 def test_no_image_is_valid(self):
  self.assertNotIn('activity-gallery',community.activity(self.rows()[1],'agenda'))
 def test_unsafe_link_is_not_rendered(self):
  row=self.rows()[0];row['url']='javascript:alert(1)';self.assertEqual(community.activity(row,'agenda'),'')
 def test_upcoming_has_own_route(self):
  self.assertEqual(seo.agenda_path('woerden','binnenkort'),'/agenda/utrecht/woerden/binnenkort')
