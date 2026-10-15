import unittest
from unittest.mock import patch
import media_library as m

class ClubPhotoMatching(unittest.TestCase):
 def test_punctuation_and_aliases(self):
  club={'name':'Sportlust 46','aliases':['Sportlust'],'municipality':'woerden'}
  with patch.object(m,'football_clubs',return_value=[club]):
   self.assertEqual(m.matching_football_clubs({'title':'Sportlust ’46 wint','category':'Sport','municipalities':['woerden']}),[club])
   self.assertEqual(m.matching_football_clubs({'title':'Sportlust wint','category':'Sport','municipalities':['baarn']}),[])
   self.assertEqual(m.matching_football_clubs({'title':'Sportlust wint','category':'Wonen','municipalities':['woerden']}),[])
 def test_no_partial_name_match(self):
  self.assertFalse(m.club_mentions('PVCV wint',{'name':'PVC'}))
 def test_photo_of_named_club_cannot_serve_another_club(self):
  file=next(iter(m.load().values()))['file']
  bank={'club':{'file':file,'kind':'photo','capturedAt':'2024-04-01','topics':['voetbal'],'clubNames':['Sportlust'],'municipalities':['woerden']}}
  self.assertEqual(m.candidates({'title':'VEP wint voetbalwedstrijd','municipalities':['woerden']},bank),[])
  self.assertEqual(m.candidates({'title':'Sportlust wint voetbalwedstrijd','municipalities':['woerden']},bank),['club'])
