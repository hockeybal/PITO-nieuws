import unittest
import club_identity, news, media_library
class ClubIdentityTest(unittest.TestCase):
 def article(self,title,city,sport='voetbal'):
  return dict(category='Sport',title=title,summary='',municipalities=[city],imageTopics=[sport])
 def test_named_club(self):
  self.assertEqual(club_identity.for_article(self.article('Jonathan ontvangt Victoria','zeist'))['name'],'VV Jonathan')
 def test_city_is_not_a_club(self):
  self.assertIsNone(club_identity.for_article(self.article('Zeist opent een sportpark','zeist')))
  self.assertIsNone(club_identity.for_article(self.article('Rugbyers Spakenburg winnen','bunschoten','rugby')))
 def test_real_club_photo_wins(self):
  self.assertIsNone(club_identity.for_article(self.article('Jonathan wint','zeist'),{'clubNames':['Jonathan']}))
 def test_reuse_before_empty_cover(self):
  articles=[a for a in news.articles() if a.get('slug')=='staking-bus-tram-utrecht-14-oktober-2026']
  assigned=media_library.assign(articles*2)
  self.assertTrue(all(a['_displayImageKey'] for a in assigned))
if __name__=='__main__':unittest.main()
