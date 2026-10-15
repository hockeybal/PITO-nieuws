import datetime,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import facts,news
class FactTests(unittest.TestCase):
 def test_scope_and_stable_week(self):
  self.assertIsNone(facts.pick('baarn'))
  self.assertEqual(facts.pick('woerden')['municipality'],'woerden')
  a=facts.pick(day=datetime.date(2026,10,5));b=facts.pick(day=datetime.date(2026,10,11));c=facts.pick(day=datetime.date(2026,10,12))
  self.assertEqual(a['slug'],b['slug']);self.assertNotEqual(a['slug'],c['slug'])
 def test_hidden_and_expired(self):
  a=dict(facts.records()[0],status='draft')
  with patch.object(facts,'records',return_value=[a]):self.assertEqual(facts.visible(),[])
  a.update(status='approved',reviewBy='2026-10-09')
  with patch.object(facts,'records',return_value=[a]):self.assertEqual(facts.visible(),[])
 def test_block_separate_from_search_archive_and_local_scope(self):
  self.assertIn('Weetje van de week',news.home())
  self.assertNotIn('Weetje van de week',news.home(m='baarn'))
  self.assertNotIn('Weetje van de week',news.home(period='archive'))
  self.assertNotIn('Weetje van de week',news.home(q='spoor'))
  self.assertIn('Ontdek het verhaal',news.home(m='woerden'))
 def test_detail_escapes_and_cites(self):
  a=dict(facts.records()[0],title='<script>test</script>')
  s=facts.detail(a);self.assertNotIn('<script>test</script>',s);self.assertIn(a['sourceUrl'],s)
if __name__=='__main__':unittest.main()
