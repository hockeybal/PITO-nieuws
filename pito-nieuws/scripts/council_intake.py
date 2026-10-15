"""Sample council meetings through the documented OpenBesluitvorming API.
Meeting dates are never publication dates. No source prose or public articles.
"""
import argparse,datetime,hashlib,json,urllib.request,urllib.parse,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='https://openbesluitvorming.nl'
def get(path,params=None):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PITO-local-research/1.0'}),timeout=20) as r:
  raw=r.read(5_000_001)
  if len(raw)>5_000_000:raise ValueError('Response te groot')
 return json.loads(raw)
def run(start,end):
 for d in (start,end):datetime.date.fromisoformat(d)
 if start>end:raise ValueError('Ongeldig datumbereik')
 rows=json.loads((ROOT/'data/municipal-source-discovery.json').read_text());inbox=[];report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'window':[start,end],'sources':[],'fullArchive':False}
 for row in rows:
  source=next(iter(row.get('openBesluitvorming',[])),None)
  if not source or source.get('health',{}).get('state')!='ok':
   report['sources'].append({'municipality':row['municipality'],'status':'direct_council_required'});continue
  try:
   data=get('/api/search',dict(organization=source['key'],entityType='Meeting',dateFrom=start,dateTo=end,sort='date_desc',limit=24))
   items=data.get('results',[])
   for item in items:
    if item.get('entityType')!='Meeting' or not item.get('entityId'):continue
    inbox.append({'id':hashlib.sha256(item['entityId'].encode()).hexdigest()[:20],'entityId':item['entityId'],'municipality':row['municipality'],'sourceTitle':item.get('title','')[:350],'meetingAt':item.get('sortDate'),'dateType':'meeting_date_not_publication','sourceUrl':BASE+'/api/entities/'+urllib.parse.quote(item['entityId'],safe=''),'officialCouncilUrl':row.get('councilFinalUrl') or row['homepage'],'status':'needs_review','note':'Vergadering is geen besluit. Lees agenda, raadsvoorstel, besluitenlijst en eventuele stemuitslag bij de primaire bron.'})
   report['sources'].append({'municipality':row['municipality'],'status':'ok','received':len(items),'hasMore':bool(data.get('hasMore')),'totalEstimate':data.get('totalCount')})
  except Exception as e:
   report['sources'].append({'municipality':row['municipality'],'status':'error','error':str(e)[:300]})
   if isinstance(e,urllib.error.HTTPError) and e.code==429:break
 for name,data in [('council-inbox',inbox),('council-report',report)]:
  p=ROOT/'data'/(name+'.json');p.with_suffix('.tmp').write_text(json.dumps(data,ensure_ascii=False,indent=2));p.with_suffix('.tmp').replace(p)
 print(json.dumps({'meetings':len(inbox),'sources':report['sources']},ensure_ascii=False,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2026-04-10');ap.add_argument('--end',default='2026-10-10');a=ap.parse_args();run(a.start,a.end)
