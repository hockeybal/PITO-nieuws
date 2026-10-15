import unittest
from rights_review import image_review
class RightsTests(unittest.TestCase):
 def test_credit_alone_does_not_authorize(self):
  self.assertFalse(image_review({'author':'Photographer','sourceUrl':'https://example.org/photo'})['readyForPublication'])
 def test_noncommercial_or_unknown_date_block(self):
  image=dict(sourceUrl='https://example.org/photo',author='Maker',rightsEvidence='Licence attached to this image',rightsCheckedBy='Editor',rightsCheckedAt='2026-10-12',rightsBasis='licensed',licenseUrl='https://creativecommons.org/licenses/by/4.0/',commercialUseAllowed=True,privacyReviewed=True,kind='photo',capturedAt='2024-05-12',editorialApproved=True)
  self.assertTrue(image_review(image)['readyForPublication'])
  image['commercialUseAllowed']=False
  self.assertFalse(image_review(image)['readyForPublication'])
  image['commercialUseAllowed']=True;image.pop('capturedAt')
  self.assertFalse(image_review(image)['readyForPublication'])
