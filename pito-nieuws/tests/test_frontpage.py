import unittest,re
import news,frontpage,media_library
class FrontpageTests(unittest.TestCase):
 def test_overview_has_sections_without_pagination(self):
  html=news.home()
  self.assertEqual(html.count('class="topic-desk"'),5)
  self.assertNotIn('archive-pages',html)
  self.assertNotIn('Volg jouw onderwerpen',html)
  for campaign in ('vacatures','aanbod','app'):self.assertIn('campaign-'+campaign,html)
 def test_selection_is_unique_and_local_in_every_municipality(self):
  for m in news.read('municipalities'):
   source=[a for a in news.articles() if news.selected(a,m['slug'])]
   _,selected=frontpage.overview(news.ranking.order(source,'relevance',diversify=True),m['slug'],'')
   self.assertEqual(len(selected),len({a['slug'] for a in selected}))
   self.assertTrue(all(news.selected(a,m['slug']) for a in selected))
   images=[media_library.media_for(a) for a in selected]
   self.assertTrue(all(images),m['slug'])
   identities=[media_library.identity(a) for a in images if a]
   self.assertEqual(len(identities),len(set(identities)))
 def test_tip_destinations_have_real_content(self):
  for slug,title,_,paragraphs in frontpage.TIPS:
   html=frontpage.tip_page(slug)
   self.assertIn(title,html)
   for p in paragraphs:self.assertIn(news.e(p),html)
  self.assertIsNone(frontpage.tip_page('missing'))

 def test_archive_cards_all_have_images(self):
  for page in range(1,29):
   html=news.home(period='archive',page=str(page))
   cards=re.findall(r'<article class="story .*?</article>',html)
   self.assertTrue(all('<img ' in c for c in cards),page)
