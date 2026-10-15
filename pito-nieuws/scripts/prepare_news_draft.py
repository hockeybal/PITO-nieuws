"""Validate an evidence bundle and prepare an unpublished Strapi-shaped concept.
No article is produced from a headline alone. Every paragraph references checked facts.
"""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rights_review import image_review

def prepare(bundle):
 sources={s['id']:s for s in bundle['sources']};facts={f['id']:f for f in bundle['facts']}
 if not bundle.get('municipalities') or not sources or not facts:raise ValueError('Lokale duiding, bronnen en feiten verplicht')
 for source in sources.values():
  u=urlsplit(source['url'])
  if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Ongeldige bronlink')
  if not source.get('checkedAt'):raise ValueError('Broncontrole ontbreekt')
 for fact in facts.values():
  if not fact.get('sourceIds') or any(s not in sources for s in fact['sourceIds']):raise ValueError('Feit zonder herleidbare bron')
  if not fact.get('statement') or not fact.get('verified'):raise ValueError('Feit nog niet geverifieerd')
 for paragraph in bundle['paragraphs']:
  if not paragraph.get('text') or not paragraph.get('factIds') or any(f not in facts for f in paragraph['factIds']):raise ValueError('Alinea zonder gecontroleerde feiten')
 if not bundle.get('title') or not bundle.get('summary') or not bundle['paragraphs']:raise ValueError('Concept incompleet')
 return {'data':{'title':bundle['title'],'summary':bundle['summary'],'body':'\n\n'.join(p['text'] for p in bundle['paragraphs']),'municipalities':bundle['municipalities'],'reviewStatus':'needs_review','publishedAt':None},'evidence':bundle,'imageReviews':[image_review(i) for i in bundle.get('images',[])],'checksPending':['Feiten en formulering door redacteur vergelijken met brondocumenten','Geografie, besluitstatus, incidentstatus en vervaldatum','Rechten van tekst en beeld; geen overgenomen persfoto zonder grondslag','Kop en intro volledig gedekt door feiten; geen suggestieve of persoonlijke details']}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('bundle');ap.add_argument('--output',required=True);a=ap.parse_args();result=prepare(json.loads(Path(a.bundle).read_text()));Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2));print('Ongepubliceerd concept met bewijsdossier opgeslagen; menselijke inhoudscontrole blijft nodig.')
