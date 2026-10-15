"""Conservative editorial readiness checks, not a legal opinion or licence detector."""
import datetime
from urllib.parse import urlsplit

def image_review(image):
 issues=[]
 for key in ('sourceUrl','author','rightsEvidence','rightsCheckedBy','rightsCheckedAt'):
  if not image.get(key):issues.append('Ontbreekt: '+key)
 if image.get('rightsBasis') not in ('owned','permission','licensed','public_domain'):
  issues.append('Geen vastgelegde gebruiksgrond')
 if image.get('rightsBasis')=='licensed':
  if not image.get('licenseUrl'):issues.append('Licentielink ontbreekt')
  if image.get('commercialUseAllowed') is not True:issues.append('Commercieel gebruik niet bevestigd')
  if image.get('changes') and image.get('modificationsAllowed') is not True:issues.append('Bewerking niet bevestigd toegestaan')
  if image.get('shareAlikeRequired') and not image.get('shareAlikeFulfilled'):issues.append('Gelijkdelenvoorwaarde niet verwerkt')
 if image.get('rightsBasis')=='permission' and not image.get('permissionCoversWeb'):issues.append('Toestemming voor website ontbreekt')
 if image.get('privacyReviewed') is not True:issues.append('Privacy/portret/context nog beoordelen')
 if image.get('kind')=='photo':
  try:
   if datetime.date.fromisoformat(image.get('capturedAt',''))<datetime.date(2022,1,1):issues.append('Ouder dan de afgesproken beeldgrens 2022')
  except (ValueError,TypeError):issues.append('Opnamedatum niet bevestigd')
 if image.get('editorialApproved') is not True:issues.append('Redactionele beeldcontrole ontbreekt')
 return {'readyForPublication':not issues,'issues':issues,'automaticLegalClearance':False}
