import unittest,json
from pathlib import Path
import media_library,news,rights_review
R=Path(__file__).resolve().parents[1]
class ArchivePhotoBankTests(unittest.TestCase):
 def test_location_archive_requires_explicit_choice(self):
  bank=media_library.load();key='archive-photo-165595566';photo=bank[key]
  a={'slug':'test','title':'Gemeenteraad bespreekt begroting','summary':'','municipalities':['de-ronde-venen'],'imageTopics':['bestuur']}
  self.assertEqual(media_library.candidates(a,{key:photo}),[])
  a['imageKey']=key
  self.assertIn(key,media_library.candidates(a,{key:photo}))
 def test_archive_photos_have_rights_and_files(self):
  for key,m in media_library.load().items():
   if m.get('batch')!='archive-expansion-2026-10-12':continue
   with self.subTest(key=key):
    self.assertTrue((R/'static/images'/m['file']).is_file())
    self.assertTrue(rights_review.image_review(m)['readyForPublication'])
    self.assertGreaterEqual(m['capturedAt'],'2022-01-01')
 def test_library_is_paginated(self):
  page=news.image_library()
  self.assertLessEqual(page.count('class="library-card"'),36)
  self.assertIn('name="gemeente"',page)
  self.assertIn('Bladeren door beelden',page)
 def test_library_filters_municipality(self):
  page=news.image_library('locatiearchief','baarn')
  self.assertIn('Stationsgebouw van Baarn',page)
  self.assertNotIn('Gemeentehuis van De Ronde Venen',page)
if __name__=='__main__':unittest.main()
