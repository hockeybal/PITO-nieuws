import unittest
import frontpage, media_library, news

class TopicCompositionTests(unittest.TestCase):
 def test_local_stories_surface_below_province_opening(self):
  source=news.ranking.order(news.articles())
  html,shown=frontpage.overview(source,'','')
  self.assertGreater(len(shown),29)
  self.assertTrue(any(a.get('editorialScope')=='municipal' for a in shown[4:]))
  self.assertFalse(any(a.get('editorialScope')=='municipal' for a in shown[:4]))
  self.assertEqual(len(shown),len({a['slug'] for a in shown}))
  self.assertIn('topic-composition',html)
 def test_generated_images_never_selected_even_if_explicit(self):
  library=media_library.load()
  key=next(k for k,v in library.items() if v.get('kind')=='generated')
  self.assertIsNone(media_library.media_for({'_displayImageKey':key},library))
 def test_missing_photos_keep_an_editorial_image_slot(self):
  card=news.card(dict(news.articles()[0],_displayImageKey=''))
  self.assertIn('editorial-cover',card)
  self.assertIn('width="960" height="540"',card)
 def test_sport_has_a_dedicated_topic_route(self):
  import seo, community
  self.assertEqual(seo.topic_path('woerden','Sport'),'/nieuws/utrecht/woerden/onderwerp/sport')
  self.assertIn('Sport',news.CATEGORIES)
 def test_topic_landing_has_new_composition_and_no_duplicate_filters(self):
  html=news.home(category='Bestuur')
  self.assertIn('topic-composition',html)
  self.assertNotIn('class="filterbar"',html)
  self.assertNotIn('archive-pages',html)
