"""KOOP SRU 2.0 candidates for important local changes; never auto-publishes."""
import argparse,datetime,hashlib,json,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET
if __package__:
 from .source_security import parse_xml
else:
 from source_security import parse_xml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENDPOINT='https://repository.overheid.nl/sru'
NS={'sru':'http://docs.oasis-open.org/ns/search-ws/sruResponse','dt':'http://purl.org/dc/terms/','gzd':'http://standaarden.overheid.nl/sru'}
NOISE=('gehandicaptenparkeerplaats','laadpaal','oplaadpunt','dakkapel','dakopbouw','boom kappen','kappen van een boom')

def parse(raw,municipality,start,end):
 root=parse_xml(raw,3_000_000)
 if root.find('.//{http://docs.oasis-open.org/ns/search-ws/diagnostic}diagnostic') is not None:raise ValueError('SRU-query niet geaccepteerd')
 rows=[];skipped=0
 for record in root.findall('.//sru:record',NS):
  def text(path):return record.findtext(path,default='',namespaces=NS).strip()
  title=text('.//dt:title');url=text('.//gzd:preferredUrl');pub=text('.//dt:date');modified=text('.//dt:modified');creator=text('.//dt:creator');kind=text('.//dt:type');identifier=text('.//dt:identifier')
  # Exact authority check avoids names occurring only in text or other collections.
  if creator.casefold()!=municipality['name'].casefold() or not start<=pub<=end:skipped+=1;continue
  if not re.fullmatch(r'https://zoek\.officielebekendmakingen\.nl/[a-z]+-\d{4}-\d+\.html',url):skipped+=1;continue
  low=title.lower()
  if any(w in low for w in NOISE):skipped+=1;continue
  rows.append({'id':hashlib.sha256(identifier.encode()).hexdigest()[:20],'sourceId':'koop-sru','upstreamId':identifier,'sourceTitle':title[:500],'sourceUrl':url,'sourcePublishedAt':pub,'sourceModifiedAt':modified,'authority':creator,'municipality':municipality['slug'],'type':kind,'status':'needs_review','decisionStatus':'unconfirmed','note':'Controleer ontwerp, aanvraag of vastgesteld besluit en werkelijke gevolgen voor inwoners. Geen automatische hoofdnieuwsplaatsing.'})
 return rows,int(root.findtext('sru:numberOfRecords','0',NS)),skipped

def run(start,end,max_pages=30):
 for d in (start,end):datetime.date.fromisoformat(d)
 if start>end or max_pages<1:raise ValueError('Ongeldig bereik')
 p=ROOT/'data/koop-inbox.json';known={r['sourceUrl']:r for r in json.loads(p.read_text())} if p.exists() else {}
 report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'window':[start,end],'queryScope':'Alle officiële publicaties op publicatiedatum en gemeentelijke afzender; kleine individuele gevallen uitgefilterd, relevantie nog te beoordelen','fullArchive':False,'sources':[]}
 for municipality in json.loads((ROOT/'data/municipalities.json').read_text()):
  name=municipality['name'];query=f'c.product-area==officielepublicaties AND dt.date>={start} AND dt.date<={end} AND dt.creator="{name}"'
  r={'municipality':municipality['slug'],'status':'ok','pages':0,'fetched':0,'candidates':0,'skipped':0,'added':0,'hasMore':True}
  try:
   for page in range(max_pages):
    url=ENDPOINT+'?'+urllib.parse.urlencode(dict(operation='searchRetrieve',version='2.0',query=query,maximumRecords=100,startRecord=page*100+1))
    with urllib.request.urlopen(url,timeout=25) as response:raw=response.read(3_000_001)
    candidates,total,skipped=parse(raw,municipality,start,end)
    fetched=len(parse_xml(raw,3_000_000).findall('.//sru:record',NS))
    r['pages']+=1;r['fetched']+=fetched;r['totalMatches']=total;r['skipped']+=skipped;r['candidates']+=len(candidates)
    for item in candidates:
     old=known.get(item['sourceUrl']);item['lastSeenAt']=report['runAt']
     if old is None:r['added']+=1
     elif old.get('sourceModifiedAt')==item.get('sourceModifiedAt') and old.get('sourceTitle')==item.get('sourceTitle'):item={**old,'lastSeenAt':report['runAt']}
     known[item['sourceUrl']]=item
    r['hasMore']=page*100+fetched<total
    if not r['hasMore']:break
    if not fetched:raise ValueError('Lege pagina vóór einde resultaten')
  except Exception as e:r.update(status='error',error=str(e)[:250])
  report['sources'].append(r)
  # Checkpoint per authority: an interrupted backfill can be safely re-run.
  for filename,data in [('koop-inbox',list(known.values())),('koop-report',report)]:
   target=ROOT/'data'/(filename+'.json');tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(target)
 print(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--start',required=True);ap.add_argument('--end',required=True);ap.add_argument('--max-pages',type=int,default=30);a=ap.parse_args();run(a.start,a.end,a.max_pages)
