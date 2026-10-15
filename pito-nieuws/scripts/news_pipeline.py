"""Run-once ingestion coordinator. Intended for deployment scheduler; no publication.
Example: python3 scripts/news_pipeline.py --adapters rss,vru,koop --start 2026-04-11 --end 2026-10-11
"""
import argparse,contextlib,datetime,fcntl,json,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADAPTERS={'rss':'intake.py','vru':'vru_intake.py','koop':'koop_intake.py','council':'council_intake.py','ndw':'ndw_intake.py','amber':'amber_intake.py','municipal':'municipal_archive_intake.py','regional':'regional_archive_intake.py','documents':'read_source_documents.py'}
def consolidate():
 sys.path.insert(0,str(ROOT))
 import topic_policy
 result={}
 for name in ('regional-archive-inbox','municipal-archive-inbox','inbox','koop-inbox','council-inbox','vru-inbox','ndw-inbox'):
  p=ROOT/'data'/(name+'.json')
  if not p.exists():continue
  for row in json.loads(p.read_text()):
   # NDW uses a shared feed URL: retain each upstream incident identity.
   key=(row.get('sourceUrl','')+'#'+row.get('upstreamId','')) if name=='ndw-inbox' else row.get('sourceUrl',row['id'])
   item=result.setdefault(key,{'id':row['id'],'sourceUrl':row.get('sourceUrl'),'title':row.get('sourceTitle') or row.get('recordType'),'sourceRecords':[],'status':'signal_only','publicationAllowed':False})
   item['sourceRecords'].append({'inbox':name,'id':row['id'],'date':row.get('sourcePublishedAt') or row.get('meetingAt') or row.get('incidentAt') or row.get('startsAt'),'dateType':row.get('dateType','publication' if row.get('sourcePublishedAt') else 'validity'),'municipalityCandidates':row.get('municipalityCandidates') or row.get('sourceMunicipalities') or [row.get('municipality') or row.get('sourceMunicipality') or ''],'status':row.get('incidentStatus') or row.get('timing')})
 article_links={}
 for article in json.loads((ROOT/'data/articles.json').read_text()):
  for source_url in set([article.get('sourceUrl')]+[s.get('url') for s in article.get('additionalSources',[]) if isinstance(s,dict)]):
   if not source_url:continue
   article_links.setdefault(source_url,[]).append({'slug':article['slug'],'reviewStatus':article.get('reviewStatus'),'verifiedAt':article.get('verifiedAt')})
 documents_path=ROOT/'data/source-documents.json'
 documents={d['sourceUrl']:d for d in json.loads(documents_path.read_text())} if documents_path.exists() else {}
 for item in result.values():
  doc=documents.get(item.get('sourceUrl'),{})
  item['extractionStatus']=doc.get('readStatus','not_attempted')
  item['processingReason']='Tekst uitgelezen; feitencontrole en eigen artikel nodig' if doc.get('extractionVersion')=='article-body-v2' and doc.get('readStatus')=='read' else 'Brontekst niet beschikbaar; toegang of paginaopbouw controleren' if doc.get('readStatus') in ('error','no_article_body') else 'Nog niet inhoudelijk uitgelezen met de nieuwe lezer'
  item['linkedArticles']=article_links.get(item.get('sourceUrl'),[])
  item['processingStatus']='article_prepared' if item['linkedArticles'] else 'awaiting_source_review'
  if item['linkedArticles']:item['processingReason']='Artikel voorbereid; zie redactionele status'
 for item in result.values():item['topicSuggestions']=topic_policy.suggest(item.get('title'));item['topicPolicyVersion']='2026-10-11-user-hypotheses-v1'
 target=ROOT/'data/editorial-queue.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(list(result.values()),ensure_ascii=False,indent=2));tmp.replace(target)
 return len(result)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--adapters',default='rss,vru,documents');ap.add_argument('--start');ap.add_argument('--end',default=datetime.date.today().isoformat());ap.add_argument('--max-pages',type=int,default=30);ap.add_argument('--document-limit',type=int,default=120);ap.add_argument('--queue-only',action='store_true');a=ap.parse_args()
 start=a.start or (datetime.date.fromisoformat(a.end)-datetime.timedelta(days=7)).isoformat();adapters=a.adapters.split(',')
 if set(adapters)-ADAPTERS.keys():ap.error('Onbekende adapter')
 if datetime.date.fromisoformat(start)>datetime.date.fromisoformat(a.end):ap.error('Ongeldige periode')
 with (ROOT/'data/pipeline.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:sys.exit('Er draait al een inname; geen tweede schrijver gestart.')
  report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'window':[start,a.end],'runs':[],'autoPublish':False}
  for adapter in ([] if a.queue_only else adapters):
   cmd=[sys.executable,str(ROOT/'scripts'/ADAPTERS[adapter])]
   if adapter not in ('ndw','amber'):cmd+=['--start',start,'--end',a.end]
   if adapter in ('koop','vru','municipal','regional'):cmd+=['--max-pages',str(a.max_pages)]
   if adapter=='documents':cmd+=['--limit',str(a.document_limit)]
   if adapter=='regional':cmd+=['--all-regions']
   try:
    env=os.environ.copy()
    deps=ROOT/'work/intake-deps'
    if deps.is_dir():env['PYTHONPATH']=str(deps)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    process=subprocess.run(cmd,capture_output=True,text=True,timeout=3600,env=env)
    report['runs'].append({'adapter':adapter,'exitCode':process.returncode,'result':process.stdout[-2000:] if process.returncode==0 else process.stderr[-1000:]})
   except Exception as error:report['runs'].append({'adapter':adapter,'error':str(error)[:500]})
  report['queueSize']=consolidate()
  (ROOT/'data/pipeline-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
