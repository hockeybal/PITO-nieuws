import sys,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import community,news
class CommunityTests(unittest.TestCase):
 def setUp(self):
  # These fixtures describe a fixed edition; the wall clock must not age them.
  import os
  from unittest.mock import patch
  clock=patch.dict(os.environ,{'PITO_EDITION_DATE':'2026-10-10'})
  clock.start();self.addCleanup(clock.stop)

  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'data').mkdir();self.p=patch.object(community,'ROOT',self.root);self.p.start()
 def tearDown(self):self.p.stop();self.tmp.cleanup()
 def story(self,name='Testschrijver'):
  return dict(kind='story',municipality='woerden',authorName=name,email='test@example.test',confirmed=True,title='Testverhaal',summary='Introductie',body='Eigen tekst',evidence='Eigen waarneming',sourceUrl='')
 def test_pending_hidden_approved_credit_and_private_contact(self):
  community.submit(self.story('<script>Auteur</script>'));self.assertEqual(community.visible(),[])
  a=community.records()[0];d=dict(id=a['id'],status='approved',reviewer='Testredacteur',reviewNote='Gecontroleerd',confirmed=True);community.moderate(d)
  a=community.visible('woerden')[0];html=community.detail(a);self.assertIn('&lt;script&gt;Auteur',html);self.assertNotIn('test@example.test',html);self.assertEqual(community.visible('baarn'),[])
  d['status']='rejected';community.moderate(d);self.assertEqual(community.visible(),[])
 def test_multiple_authors_and_signup_is_not_story(self):
  for name in ['Test Een','Test Twee']:community.submit(self.story(name))
  community.submit(dict(self.story(),kind='join',motivation='Ik wil schrijven'))
  for a in community.records():community.moderate(dict(id=a['id'],status='approved',reviewer='Test',reviewNote='Test',confirmed=True))
  self.assertEqual(len(community.visible('woerden')),2)
 def test_validation_and_moderation(self):
  for d in [dict(self.story(),confirmed=False),dict(self.story(),sourceUrl='javascript:bad'),dict(self.story(),evidence=''),dict(self.story(),municipality='parijs')]:
   with self.assertRaises(ValueError):community.submit(d)
  community.submit(self.story());a=community.records()[0]
  with self.assertRaises(ValueError):community.moderate(dict(id=a['id'],status='approved',reviewer='',reviewNote='',confirmed=False))
  self.assertEqual(community.visible(),[])
 def test_today_filters_date_and_municipality(self):
  base=dict(label='Dag',summary='Test',sourceName='PITO-app',url='https://pito.app/test')
  items=[dict(base,title='Vandaag Woerden',date='2026-10-10',municipality='woerden'),dict(base,title='Morgen Woerden',date='2026-10-11',municipality='woerden'),dict(base,title='Vandaag Baarn',date='2026-10-10',municipality='baarn')]
  with patch.object(news.app_content,'get',return_value=(items,'connected')):
   s=community.page('woerden','vandaag');self.assertIn('Vandaag Woerden',s);self.assertNotIn('Morgen Woerden',s);self.assertNotIn('Vandaag Baarn',s)
   self.assertIn('Morgen Woerden',community.page('woerden','agenda'))
if __name__=='__main__':unittest.main()
