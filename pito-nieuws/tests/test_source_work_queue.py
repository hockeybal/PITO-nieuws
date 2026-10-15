import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_source_work_queue import disposition,canonical
class WorkQueueTests(unittest.TestCase):
 def test_successful_extraction_never_approves_publication(self):
  r={'sourceUrl':'https://example.org/news/1','sourcePublishedAt':'2026-09-15'}
  d={'readStatus':'read','pageTitle':'New railway works','sourceParagraphs':['Actual source content '*30]}
  self.assertEqual(disposition(r,d,{},{} )[0],'ready_for_writing')
 def test_maintenance_is_not_article(self):
  r={'sourceUrl':'https://example.org/news/1'}
  d={'readStatus':'read','pageTitle':'Gemeenteraad','sourceParagraphs':['De website is wegens onderhoud tijdelijk niet beschikbaar.']}
  self.assertEqual(disposition(r,d,{},{} )[0],'source_unavailable')
 def test_local_link_takes_precedence_over_later_source_outage(self):
  r={'sourceUrl':'https://example.org/news/1/'}
  self.assertEqual(disposition(r,{'readStatus':'error'},{canonical(r['sourceUrl']):['own-story']},{})[2],['own-story'])
 def test_missing_date_remains_unconfirmed(self):
  self.assertEqual(disposition({'sourceUrl':'https://example.org/a'},{'readStatus':'read'}, {},{})[0],'date_unconfirmed')
if __name__=='__main__':unittest.main()
