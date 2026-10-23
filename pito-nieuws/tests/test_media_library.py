import unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import media_library,news,starter,community,app_content
class LibraryTests(unittest.TestCase):
 def test_aliases_share_identity_and_unrelated_never_selected(self):
  file=next(iter(news.read('images').values()))['file']
  lib={'a':{'file':file,'assetId':'same','topics':['bestuur']},'crop':{'file':file,'assetId':'same','topics':['bestuur']}}
  items=[{'slug':str(n),'imageTopics':['bestuur']} for n in range(3)]
  result=media_library.assign(items,lib)
  self.assertEqual(sum(bool(a['_displayImageKey']) for a in result),1)
  self.assertEqual(sum(a['_suppressImage'] for a in result),2)
  self.assertFalse(media_library.assign([{'slug':'x','imageTopics':['rechtspraak']}],lib)[0]['_displayImageKey'])
  self.assertNotIn('_displayImageKey',items[0])
 def test_all_editions_deterministic_with_relevant_unique_images(self):
  lib=news.read('images')
  for m in ['']+[x['slug'] for x in news.read('municipalities')]:
   articles=[a for a in news.articles() if news.selected(a,m)][:12]
   selected=media_library.assign(articles,lib)
   ids=[media_library.identity(lib[a['_displayImageKey']]) for a in selected if a['_displayImageKey']]
   for a in selected:
    if a['_displayImageKey']:self.assertIn(a['_displayImageKey'],media_library.candidates(a,lib))
    else:self.assertTrue(a['_suppressImage'])
   self.assertEqual(len(ids),len(set(ids)))
   self.assertEqual(selected,media_library.assign(articles,lib))
 def test_shortage_keeps_unique_images_and_leaves_text_cards(self):
  file=next(iter(news.read('images').values()))['file']
  lib={k:{'file':file,'assetId':k,'topics':['bestuur']} for k in ['a','b']}
  items=[{'slug':str(n),'imageTopics':['bestuur']} for n in range(3)]
  rows=media_library.assign(items,lib)
  self.assertEqual(len({a['_displayImageKey'] for a in rows if a['_displayImageKey']}),2)
  self.assertEqual(sum(bool(a['_displayImageKey']) for a in rows),2)
  self.assertEqual(sum(a['_suppressImage'] for a in rows),1)
 def test_page_composition_deduplicates_asset_aliases_without_removing_text(self):
  library={'original':{'file':'one.jpg','assetId':'same'},'crop':{'file':'crop.jpg','assetId':'same'}}
  markup=('<article><figure><img src="/news-static/images/one.jpg"><figcaption>First credit</figcaption></figure><h2>First article</h2></article>'
          '<article class="story lead"><figure><img src="/news-static/images/crop.jpg"><figcaption>Repeated credit</figcaption></figure><h2>Second article</h2></article>'
          '<a href="https://pito.app/event"><img class="invitation-event-photo" src="/news-static/images/one.jpg"><strong>Activity remains</strong></a>'
          '<img src="/news-static/campaign/pito-logo.png"><img src="/news-static/campaign/pito-logo.png">')
  html=media_library.deduplicate_images(markup,library)
  self.assertEqual(html.count('/news-static/images/'),1)
  self.assertIn('First credit',html);self.assertNotIn('Repeated credit',html)
  for text in ('First article','Second article','Activity remains'):self.assertIn(text,html)
  self.assertIn('<article class="story lead text-only"><h2>Second article</h2>',html)
  self.assertEqual(html.count('/news-static/campaign/pito-logo.png'),2)
 def test_matching_reassigns_flexible_article_before_leaving_a_gap(self):
  library={'one':{'file':'one.jpg','assetId':'one'},'two':{'file':'two.jpg','assetId':'two'}}
  articles=[{'slug':'flexible'},{'slug':'constrained'},{'slug':'unmatched'}]
  with patch.object(media_library,'candidates',side_effect=[['one','two'],['one'],[]]):
   rows=media_library.assign(articles,library)
  self.assertEqual([a['_displayImageKey'] for a in rows],['two','one',''])
  self.assertEqual(articles,[{'slug':'flexible'},{'slug':'constrained'},{'slug':'unmatched'}])
 def test_suppressed_card_has_title_and_link_without_generic_cover(self):
  a=dict(news.articles()[0],_suppressImage=True,_displayImageKey='')
  html=news.card(a)
  self.assertNotIn('<img',html)
  self.assertIn(news.e(a['title']),html)
  self.assertIn(news.url(a),html)
  self.assertIn('text-only',html)
 def test_starter_city_image_and_explicit_fallback(self):
  self.assertNotIn('hero-baarn.png',starter.render([],'baarn'))
  self.assertNotIn('Nieuw gemeentebeeld volgt',starter.render([],'baarn'))
  self.assertIn('municipality-eemnes.jpg',starter.render([],'eemnes'))
  self.assertNotIn('Nieuw gemeentebeeld volgt',starter.render([],'eemnes'))
  for city in news.read('municipalities'):
   self.assertNotIn('Nog geen lokaal luchtbeeld',starter.render([],city['slug']))
 def test_photo_capture_year_gate_includes_explicit_image_override(self):
  for date,accepted in [('2005-01-01',False),('2021-12-31',False),('2022-01-01',True),('2099-01-01',False),('',False)]:
   image={'kind':'photo','capturedAt':date,'verifiedAt':'2026-10-11','file':'test.jpg'}
   self.assertEqual(media_library.eligible(image),accepted)
   self.assertEqual(media_library.media_for({'_displayImageKey':'x'},{'x':image}) is not None,accepted)
 def test_agenda_only_selected_city(self):
  rows=[dict(title='Alleen Baarn',municipality='baarn',date='2026-10-11',label='Morgen',summary='',url='https://pito.app/a',agendaHighlight=True),dict(title='Alleen Woerden',municipality='woerden',date='2026-10-11',label='Morgen',summary='',url='https://pito.app/b',agendaHighlight=True)]
  with patch.object(app_content,'get',return_value=(rows,'connected')), patch.object(news.seo,'today',return_value=__import__('datetime').date(2026,10,10)):
   html=community.page('baarn','agenda')
   self.assertIn('Alleen Baarn',html);self.assertNotIn('Alleen Woerden',html)

 def test_football_does_not_select_fitness_or_generic_context(self):
  a=next(a for a in news.articles() if a['slug']=='sportlust-beker-excelsior-maassluis')
  choices=media_library.candidates(a,news.read('images'))
  self.assertIn('woerden-sportlust-clubgebouw-2022',choices)
  self.assertTrue(all(news.read('images')[key]['kind']=='photo' for key in choices))
 def test_irrelevant_explicit_preference_cannot_override_subject(self):
  a={'title':'Voetbalwedstrijd bij Sportlust','imageTopics':['voetbal'],'imageKey':'stock-gym'}
  self.assertNotIn('stock-gym',media_library.candidates(a,news.read('images')))
 def test_named_place_and_word_boundaries_are_respected(self):
  lib=news.read('images')
  self.assertNotIn('park',media_library.article_topics({'title':'Werk aan SPARK zorgt voor aangepast OV'}))
  self.assertNotIn('utrecht-park-2024',media_library.candidates({'title':'Arrestaties in het Griftpark','municipalities':['utrecht'],'imageTopics':['park','politie']},lib))
  self.assertNotIn('utrechtse-heuvelrug-station-maarn-2024',media_library.candidates({'title':'Werkzaamheden bij station Driebergen-Zeist','municipalities':['utrechtse-heuvelrug'],'imageTopics':['ov']},lib))
 def test_named_station_can_serve_neighbouring_municipality(self):
  a={'title':'Montfoort vraagt naar parkeren bij station Woerden','municipalities':['montfoort'],'imageTopics':['ov']}
  self.assertTrue(set(media_library.candidates(a,news.read('images'))).intersection({'woerden-station-2024','woerden-station-perron-2024'}))
 def test_preference_does_not_remove_equal_subject_alternatives(self):
  file=next(iter(news.read('images').values()))['file']
  lib={key:{'file':file,'topics':['geld'],'assetId':key} for key in ['a','b']}
  a={'title':'Begroting','imageTopics':['geld'],'imageKey':'a'}
  self.assertEqual(set(media_library.candidates(a,lib)),{'a','b'})
 def test_general_context_is_not_automatic_fallback(self):
  a={'title':'Een onderwerp zonder passend beeld','imageTopics':['onbekend']}
  self.assertEqual(media_library.candidates(a,news.read('images')),[])

class RealPhotoPreferenceTests(unittest.TestCase):
 def test_real_photo_wins_even_over_explicit_generated_key(self):
  file=next(iter(news.read('images').values()))['file']
  lib={'ai':{'file':file,'kind':'generated','topics':['politie']},'real':{'file':file,'kind':'photo','capturedAt':'2024-05-17','topics':['politie']}}
  self.assertEqual(media_library.candidates({'title':'Politieonderzoek','imageTopics':['politie'],'imageKey':'ai'},lib),['real'])
 def test_real_photo_of_other_city_is_not_substituted(self):
  file=next(iter(news.read('images').values()))['file']
  lib={'real':{'file':file,'kind':'photo','capturedAt':'2024-05-17','topics':['ov'],'municipalities':['utrecht']}}
  self.assertEqual(media_library.candidates({'title':'Station Woerden','imageTopics':['ov'],'municipalities':['woerden']},lib),[])
