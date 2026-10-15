"""Strapi 5 draft-only import. Default dry run; explicit --apply required."""
import argparse,json,os,sys,urllib.request,urllib.parse,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIELDS=['slug','title','summary','body','category','municipalities','sourceUrl','sourceName','sourcePublishedAt','eventDate','dateNote','verifiedAt','reviewer','reviewNote','rights','sensitive','impact','imageKey','imageTopics','additionalSources','ranking']
def payload(a):
 d={k:a.get(k) for k in FIELDS};d['reviewStatus']='approved' if a['reviewStatus']=='approved' else 'needs_review';d['provinceWide']=a.get('provinceWide',False);d['publishedAt']=None
 return {'data':d}
def request(base,path,token,method='GET',body=None):
 req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--approved-only',action='store_true');a=ap.parse_args()
 records=[r for r in json.loads((ROOT/'data/articles.json').read_text()) if r['reviewStatus'] in (['approved'] if a.approved_only else ['preview','approved'])]
 endpoint='/api/pito-news-articles';plan=[{'slug':r['slug'],'method':'upsert draft only','endpoint':endpoint+'?status=draft','payload':payload(r)} for r in records]
 if not a.apply:
  (ROOT/'strapi/import-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2));print(f'Dry run: {len(plan)} concepten voorbereid in strapi/import-plan.json. Geen netwerkverzoeken.');return
 base=os.environ.get('STRAPI_URL','').rstrip('/');token=os.environ.get('STRAPI_TOKEN','');u=urllib.parse.urlsplit(base)
 if not token or not base:sys.exit('Stel STRAPI_URL en STRAPI_TOKEN in de procesomgeving in.')
 if u.scheme!='https' and not (u.scheme=='http' and u.hostname in ['127.0.0.1','localhost']):sys.exit('HTTPS vereist buiten localhost')
 if u.username or u.password or u.query or u.fragment:sys.exit('Ongeldige basis-URL')
 # Do not guess a Strapi version or mutate an unconfirmed schema.
 if os.environ.get('STRAPI_MAJOR_VERSION')!='5' or os.environ.get('STRAPI_DRAFT_PUBLISH_CONFIRMED')!='true':sys.exit('Bevestig Strapi 5 en Draft & Publish via STRAPI_MAJOR_VERSION=5 en STRAPI_DRAFT_PUBLISH_CONFIRMED=true.')
 for item in plan:
  query=urllib.parse.urlencode({'filters[slug][$eq]':item['slug'],'status':'draft','pagination[pageSize]':2})
  found=request(base,endpoint+'?'+query,token)['data']
  if len(found)>1:sys.exit('Dubbele slug in Strapi; import gestopt.')
  if found:
   doc=found[0].get('documentId')
   if not doc:sys.exit('Geen Strapi 5 documentId; import gestopt.')
   # Preserve edits made in CMS: existing records are deliberately not overwritten.
   print(item['slug']+': bestaand concept overgeslagen');continue
  result=request(base,endpoint+'?status=draft',token,'POST',item['payload'])
  if result.get('data',{}).get('publishedAt') is not None:sys.exit('ONVERWACHT gepubliceerde response; verdere import gestopt. Controleer Strapi.')
  print(item['slug']+': concept aangemaakt')
if __name__=='__main__':main()
