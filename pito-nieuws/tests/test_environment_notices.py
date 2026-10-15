import sys,unittest,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import environment_notices as env
class EnvironmentNotices(unittest.TestCase):
 def test_status_is_not_grant_from_application(self):
  for title,want in [('Ontvangen aanvraag omgevingsvergunning','aanvraag'),('Besluit op aanvraag omgevingsvergunning','besluit'),('Verlenging beslistermijn aanvraag','procedure'),('Omgevingsvergunning geweigerd','geweigerd'),('Ontwerpbesluit vergunning','ontwerp'),('Omgevingsvergunning verleend','verleend')]:self.assertEqual(env.stage(title),want)
 def test_all_municipalities_and_unique_sources(self):
  rows=env.records();self.assertEqual(len({r['municipality'] for r in rows}),26);self.assertEqual(len(rows),len({r['sourceUrl'] for r in rows}))
 def test_scope_and_source_visible(self):
  html=env.page('woerden',q='vergunning');self.assertIn('Omgevingszaken in Woerden',html)
  self.assertTrue(all(city=='woerden' for city in re.findall(r'href="/nieuws/utrecht/([^/]+)/omgevingszaken/bekendmaking/',html)))
  r=next(r for r in env.records() if r['municipality']=='woerden');detail=env.detail(r);self.assertIn(r['sourceUrl'],detail);self.assertIn('noindex,nofollow',detail)
 def test_escaping(self):self.assertNotIn('<script>alert(1)</script>',env.page('woerden',q='<script>alert(1)</script>'))
if __name__=='__main__':unittest.main()
