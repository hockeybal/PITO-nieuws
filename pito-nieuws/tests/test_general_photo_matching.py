import unittest
import news,media_library
class GeneralPhotoTests(unittest.TestCase):
 def test_topic_specific_images(self):
  lib=news.read('images')
  for title,key in [('Een kledingbeurs in het buurthuis','kledingrek-2024'),('Onderzoek naar rivierkreeften','rivierkreeft-2024'),('Ontbijt voor mantelzorgers','ontbijt-2024'),('Ruimtevaart centraal in familievoorstellingen','ruimtevaart-2024')]:
   a=dict(title=title,summary='',category='Samenleving',municipalities=['woerden'])
   self.assertIn(key,media_library.candidates(a,lib))
 def test_panda_is_explicitly_archive(self):
  self.assertIn('niet Lang Yue',news.read('images')['panda-ouwehands-2022']['contextLabel'])
 def test_real_imkerspark_photo(self):
  a=next(a for a in news.articles() if a['slug']=='herfsttocht-voor-peuters-en-kleuters-in-het-imkerspark')
  self.assertIn('archive-photo-132504755',media_library.candidates(a,news.read('images')))
if __name__=='__main__':unittest.main()
