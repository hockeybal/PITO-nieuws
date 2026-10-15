import unittest
import official_content as content
class PublicationTests(unittest.TestCase):
 def test_only_publication(self):
  blocks=content.parse('<p>Navigation</p><div class="officiele-publicatie"><div><p>Locatie:</p><p>A &amp; B</p></div></div><p>Footer</p>')
  self.assertEqual([b['text'] for b in blocks],['Locatie:','A & B'])
 def test_no_inferred_deadline(self):
  data={'blocks':content.parse('<div class="officiele-publicatie"><p>Omschrijving van het verzoek:</p><p>het bouwen van een huis</p><p>Genomen besluit op het verzoek:</p><p>Verleend</p></div>')}
  title,intro,phase=content.presentation({'sourceTitle':'Besluit','authority':'Woerden'},data)
  self.assertIn('bouwen van een huis',title)
  self.assertEqual(phase,'verleend')
  self.assertNotIn('weken',intro)
 def test_empty_rejected(self):
  with self.assertRaises(ValueError):content.parse('<html>Not a publication</html>')
if __name__=='__main__':unittest.main()
