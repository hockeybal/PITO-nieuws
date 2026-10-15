import unittest
from scripts.discover_club_photos import Images

class PhotoDiscovery(unittest.TestCase):
 def test_empty_html_attributes_do_not_drop_other_photos(self):
  p=Images();p.feed('<a href>rechten</a><img src="team.jpg" alt><img data-src="veld.jpg" alt="Veld">')
  self.assertEqual(p.images,[('team.jpg',''),('veld.jpg','Veld')])
 def test_small_ui_images_are_not_photos(self):
  p=Images();p.feed('<img src="button.png" width="24"><img src="team.jpg" width="1200" height="800">')
  self.assertEqual(p.images,[('team.jpg','')])
