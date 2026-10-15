import unittest
import official_content as o
class DecisionTests(unittest.TestCase):
 def data(self,*texts):return {'blocks':[{'kind':'paragraph','text':t} for t in texts]}
 def test_explicit_grant(self):self.assertEqual(o.decision_status(self.data('Het college heeft besloten de omgevingsvergunning te verlenen.')),'verleend')
 def test_refusal(self):self.assertEqual(o.decision_status(self.data('De vergunning is geweigerd.')),'geweigerd')
 def test_generic_decision_is_not_a_grant(self):self.assertEqual(o.decision_status(self.data('Besluit over omgevingsvergunning','Bezwaar tegen een verleende omgevingsvergunning')),'')
 def test_application(self):self.assertEqual(o.decision_status(self.data('Ingekomen aanvraag voor het bouwen van een schuur')),'aanvraag')
 def test_conflicting_decisions_stay_neutral(self):self.assertEqual(o.decision_status(self.data('De vergunning is geweigerd.','Verleende omgevingsvergunningen')),'')
