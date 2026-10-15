"""Prepare portable local archive; keep written articles separate from source leads."""
import argparse,collections,csv,datetime,hashlib,html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from build_source_work_queue import canonical
def read(name):
 p=ROOT/'data'/(name+'.json');return json.loads(p.read_text()) if p.exists() else []
def build(start,end):
 municipalities={m['slug']:m['name'] for m in read('municipalities')}
 articles=[a for a in read('articles') if start<=str(a.get('sourcePublishedAt') or '')[:10]<=end]
 docs={canonical(r['sourceUrl']):r for r in read('source-documents')};linked={}
 queue=read('source-work-queue');decisions={canonical(r['sourceUrl']):r for r in queue.get('records',[])} if isinstance(queue,dict) else {}
 for a in articles:
  for url in [a.get('sourceUrl')]+[r.get('url') for r in a.get('additionalSources',[])]:
   if url:linked.setdefault(canonical(url),[]).append(a['slug'])
 records={}
 for name in ['municipal-archive-inbox','regional-archive-inbox','inbox','sports-inbox']:
  for r in read(name):
   url=r.get('sourceUrl')
   if not url:continue
   x=records.setdefault(canonical(url),{'id':hashlib.sha256(url.encode()).hexdigest()[:20],'sourceUrl':url,'sourceTitle':r.get('sourceTitle'),'dates':set(),'candidateMunicipalities':set(),'sourceIds':set()})
   if r.get('sourcePublishedAt'):x['dates'].add(r['sourcePublishedAt'][:10])
   x['sourceIds'].add(r.get('sourceId',''))
   candidates=r.get('municipalityCandidates',[])+r.get('sourceMunicipalities',[])+[r.get('municipality'),r.get('sourceMunicipality')]
   x['candidateMunicipalities'].update(m for m in candidates if m in municipalities)
 output=[]
 for url,r in records.items():
  d=docs.get(url,{});decision=decisions.get(url,{});dates=sorted(r.pop('dates'));date=d.get('sourcePublishedAt') or (dates[0] if len(dates)==1 else None)
  date=date[:10] if date else None
  if date and not start<=date<=end:continue
  r.update(sourcePublishedAt=date,dateStatus='source_page' if d.get('dateEvidence')=='source_page' and date else 'metadata' if date else 'missing_or_conflicting',candidateMunicipalities=sorted(r['candidateMunicipalities']),sourceIds=sorted(r['sourceIds']),linkedArticles=linked.get(url,[]),bodyAvailable=d.get('readStatus')=='read',evidenceFile=d.get('evidenceFile'),status='article_prepared' if url in linked else 'source_read' if d.get('readStatus')=='read' else 'awaiting_source_read',publicationAllowed=False)
  resolved=[s for s in decision.get('articleSlugs',[]) if any(a['slug']==s for a in articles)]
  r.update(processingStatus=decision.get('status','unclassified'),processingReason=decision.get('reason',''),processingEvidenceFile=decision.get('evidenceFile'),processingCheckedAt=decision.get('checkedAt'))
  if resolved:r.update(linkedArticles=sorted(set(r['linkedArticles']+resolved)),status='article_prepared')
  elif decision.get('status') in ('excluded','not_article','outside_window','needs_fact_check','source_unavailable','fetch_error','date_unconfirmed'):
   r['status']=decision['status']
  output.append(r)
 output.sort(key=lambda r:(r['sourcePublishedAt'] or '',r['id']),reverse=True)
 bycity=[]
 for slug,name in municipalities.items():
  local=[a for a in articles if slug in a.get('municipalities',[])];leads=[r for r in output if slug in r['candidateMunicipalities']]
  bycity.append(dict(slug=slug,name=name,articles=len(local),datedSourceLeads=sum(bool(r['sourcePublishedAt']) for r in leads),undatedSourceLeads=sum(not r['sourcePublishedAt'] for r in leads),months=dict(sorted(collections.Counter(a['sourcePublishedAt'][:7] for a in local).items()))))
 return articles,output,bycity

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2026-07-13');ap.add_argument('--end',default='2026-10-13');a=ap.parse_args()
 if datetime.date.fromisoformat(a.start)>datetime.date.fromisoformat(a.end):ap.error('Ongeldige periode')
 articles,leads,cities=build(a.start,a.end);out=ROOT/'exports/base-archive';out.mkdir(parents=True,exist_ok=True)
 metadata=dict(preparedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),window=[a.start,a.end],complete=False,articleCount=len(articles),sourceLeadCount=len(leads),sourceLeadCounts=dict(collections.Counter(x['status'] for x in leads)),municipalities=cities,note='Lokale basis. Bronrecords zijn geen geschreven artikelen. Ontbrekende data en gemeentekoppelingen blijven open. Geen Strapi-import uitgevoerd.')
 for name,value in [('articles',articles),('source-leads',leads),('manifest',metadata)]:
  p=out/(name+'.json');tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(p)
 for c in cities:
  target=out/'municipalities';target.mkdir(exist_ok=True)
  (target/(c['slug']+'.json')).write_text(json.dumps([x for x in articles if c['slug'] in x.get('municipalities',[])],ensure_ascii=False,indent=2))
 months=out/'months';months.mkdir(exist_ok=True)
 for month in sorted({x['sourcePublishedAt'][:7] for x in articles}):
  (months/(month+'.json')).write_text(json.dumps([x for x in articles if x['sourcePublishedAt'].startswith(month)],ensure_ascii=False,indent=2))
 with (out/'coverage.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['Gemeente','Artikelen','Gedateerde bronrecords','Ongedateerde bronrecords','Maanden'])
  for c in cities:w.writerow([c['name'],c['articles'],c['datedSourceLeads'],c['undatedSourceLeads'],json.dumps(c['months'])])
 e=lambda v:html.escape(str(v),quote=True)
 body='<h1>Basisarchief PITO Nieuws</h1><p>'+e(a.start)+' tot en met '+e(a.end)+'. '+str(len(articles))+' bestaande artikelen en '+str(len(leads))+' unieke bronrecords. De bronrecords zijn apart gehouden van de artikelen.</p><p>Dit is een gedeeltelijk voorbereid lokaal archief, geen volledig nieuwsarchief. Strapi is nog niet gekoppeld. Gemeentekoppelingen bij bronrecords zijn kandidaten, niet bevestigde locaties.</p><table><tr><th>Gemeente</th><th>Artikelen</th><th>Gedateerde bronnen</th><th>Datum ontbreekt</th><th>Artikelen per maand</th></tr>'
 for c in cities:body+='<tr><td>'+e(c['name'])+'</td><td>'+str(c['articles'])+'</td><td>'+str(c['datedSourceLeads'])+'</td><td>'+str(c['undatedSourceLeads'])+'</td><td>'+e(', '.join(k+': '+str(v) for k,v in c['months'].items()))+'</td></tr>'
 body+='</table><h2>Leesbare artikelen op datum</h2>'
 for month in sorted({x['sourcePublishedAt'][:7] for x in articles},reverse=True):
  body+='<details><summary>'+month+'</summary><ul>'
  for r in sorted([x for x in articles if x['sourcePublishedAt'].startswith(month)],key=lambda x:x['sourcePublishedAt'],reverse=True):body+='<li>'+e(r['sourcePublishedAt'])+' · <a href="/nieuws/utrecht/artikel/'+e(r['slug'])+'">'+e(r['title'])+'</a></li>'
  body+='</ul></details>'
 (ROOT/'static/source-audit/basisarchief.html').write_text('<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta name="robots" content="noindex,nofollow"><title>PITO basisarchief</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:24px;color:#2C2C2C}a{color:#1050C2}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}details{padding:14px 0}summary{cursor:pointer}li{margin:10px 0}</style>'+body+'</html>')
 import zipfile
 bundle=ROOT/'exports'/('pito-basisarchief-'+a.start+'-tot-'+a.end+'.zip')
 temporary=bundle.with_suffix('.tmp')
 with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as archive:
  for item in sorted(out.rglob('*')):
   if item.is_file():archive.write(item,item.relative_to(out.parent))
 temporary.replace(bundle)
 print(json.dumps({k:v for k,v in metadata.items() if k!='municipalities'},ensure_ascii=False))
if __name__=='__main__':main()
