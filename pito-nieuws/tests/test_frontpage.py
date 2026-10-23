import unittest,re
import news,frontpage,media_library
class FrontpageTests(unittest.TestCase):
 def test_overview_has_sections_without_pagination(self):
  html=news.home()
  self.assertEqual(html.count('class="topic-desk"'),6)
  self.assertNotIn('archive-pages',html)
  self.assertNotIn('Volg jouw onderwerpen',html)
  for promotion in ('proposition-warmtepomp','proposition-thuisbatterij','app-campaign'):self.assertIn(promotion,html)
 def test_selection_is_unique_and_local_in_every_municipality(self):
  library=news.read('images')
  for m in news.read('municipalities'):
   source=[a for a in news.articles() if news.selected(a,m['slug'])]
   _,selected=frontpage.overview(news.ranking.order(source,'relevance',diversify=True),m['slug'],'')
   self.assertEqual(len(selected),len({a['slug'] for a in selected}))
   self.assertTrue(all(news.selected(a,m['slug']) for a in selected))
   images=[media_library.media_for(a,library) for a in selected]
   # Missing licensed subject imagery leaves a text card; it must not select
   # an unrelated photo or reuse an already assigned asset to fill the gap.
   for a,image in zip(selected,images):
    if image:
     key=a['_displayImageKey']
     self.assertIn(key,media_library.candidates(a,{key:library[key]}))
   identities=[media_library.identity(a) for a in images if a]
   self.assertEqual(len(identities),len(set(identities)))
 def test_tip_destinations_have_real_content(self):
  for slug,title,_,paragraphs in frontpage.TIPS:
   html=frontpage.tip_page(slug)
   self.assertIn(title,html)
   for p in paragraphs:self.assertIn(news.e(p),html)
  self.assertIsNone(frontpage.tip_page('missing'))

 def test_archive_rows_keep_readable_links_and_dates_with_image_gaps(self):
  for page in range(1,29):
   html=news.home(period='archive',page=str(page))
   rows=re.findall(r'<li class="latest-row">.*?</li>',html,re.S)
   self.assertTrue(rows,page)
   for row in rows:
    self.assertIn('<time datetime=',row)
    self.assertRegex(row,r'<h2><a href="/nieuws/utrecht/artikel/[^\"]+">[^<]+</a></h2>')
