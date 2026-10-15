import unittest,json
from pathlib import Path
import useful_addresses
class UsefulAddressesTests(unittest.TestCase):
 def test_every_municipality_has_substantive_local_information(self):
  facts=json.loads((Path(useful_addresses.ROOT)/'data/local-service-facts.json').read_text())
  self.assertEqual(len(facts),26)
  for row in useful_addresses.records():
   m=row['municipality'];html=useful_addresses.page(m)
   self.assertIn('value="adressen"',html)
   self.assertNotIn('useful-city-form',html)
   self.assertIn(facts[m]['phone'],html)
   self.assertGreaterEqual(len(facts[m]['wasteFacts']),2)
 def test_region_uses_single_header_selector(self):
  html=useful_addresses.page()
  self.assertEqual(html.count('class="municipality-picker"'),1)
  self.assertNotIn('useful-cities',html)
