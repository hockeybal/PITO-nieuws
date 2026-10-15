import unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app_content,community
class AgendaDisplayTests(unittest.TestCase):
 def setUp(self):
  # These fixtures describe a fixed edition; the wall clock must not age them.
  import os
  from unittest.mock import patch
  clock=patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-10'})
  clock.start();self.addCleanup(clock.stop)

 def test_web_images_require_permission_and_credit(self):
  base=dict(id='1',title='Eigen activiteit',municipality='woerden',url='https://pito.app/activity/1',status='published',show_on_web=True,occurrences=[{'date':'2026-10-11'}])
  base['web_images']=[dict(url='https://pito.app/photo.jpg',alt='Eigen foto',credit='Organisator',web_usage_approved=True),dict(url='https://pito.app/unapproved.jpg',credit='Geen akkoord'),dict(url='javascript:alert(1)',credit='Onveilig',web_usage_approved=True)]
  rows=app_content.normalize({'activities':[base]},'2026-10-10')
  self.assertEqual(len(rows[0]['images']),1)
  self.assertIn('agenda-thumb',community.activity(rows[0],'agenda'))
 def test_tomorrow_and_upcoming_are_municipality_scoped(self):
  rows=[dict(id='1',title='Vandaag',municipality='woerden',date='2026-10-10',label='10:00',summary='',url='https://pito.app/a'),dict(id='2',title='Morgen Woerden',municipality='woerden',date='2026-10-11',label='12:00',summary='',url='https://pito.app/b'),dict(id='3',title='Morgen Baarn',municipality='baarn',date='2026-10-11',label='12:00',summary='',url='https://pito.app/c')]
  with patch.object(app_content,'get',return_value=(rows,'connected')):
   html=community.page('woerden','vandaag','morgen')
   self.assertIn('Morgen Woerden',html);self.assertNotIn('Morgen Baarn',html)
   self.assertNotIn('<strong>Vandaag</strong>',html)
   self.assertIn('<strong>Vandaag</strong>',community.page('woerden','vandaag','binnenkort'))
if __name__=='__main__':unittest.main()
