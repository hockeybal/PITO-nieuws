import unittest
from source_attribution import public_sources

class AttributionTests(unittest.TestCase):
    def test_explicit_selection_keeps_dossier_private(self):
        a={'sourceName':'Media','sourceUrl':'https://media.test/a','additionalSources':[{'name':'Copy','url':'https://copy.test/a'}], 'publicSources':[{'name':'Operator','url':'https://operator.test/a'}]}
        self.assertEqual([s['name'] for s in public_sources(a)], ['Operator'])
        self.assertEqual(len(a['additionalSources']),1)
    def test_legacy_attribution_preserved_and_duplicates_hidden(self):
        a={'sourceName':'Media','sourceUrl':'https://media.test/a','additionalSources':[{'name':'Copy','url':'https://copy.test/a','role':'duplicate'},{'name':'Own reporting','url':'https://reporter.test/a'},{'name':'Repeat','url':'https://media.test/a'}]}
        self.assertEqual([s['name'] for s in public_sources(a)],['Media','Own reporting'])
