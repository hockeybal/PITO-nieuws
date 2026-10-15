"""Metadata-only intake of audited feeds; no publication."""
import json,datetime,hashlib,subprocess
from pathlib import Path
from urllib.parse import urlsplit
from intake import parse_feed,merge_signal
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=ROOT/'data'
 def read(n):return json.loads((p/(n+'.json')).read_text())
 media=read('regional-media-sources');sources=read('sources');inbox=read('inbox');registry=read('feed-registry');known={s['sourceUrl']:s for s in inbox};report=[];now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 for row in media:
  feeds=[f for f in row.get('feedChecks',[]) if f.get('items',0)>0]
  if not feeds:continue
  feed=feeds[0]['url'];s=next((x for x in sources if x.get('feed')==feed),None)
  if s is None:
   host=urlsplit(row['url']).hostname;s={'id':'local-'+hashlib.sha256(feed.encode()).hexdigest()[:10],'name':row['name'],'kind':'Regionale media','url':row['url'],'feed':feed,'articleHosts':list({host,host.removeprefix('www.'),'www.'+host.removeprefix('www.')}),'mode':'signal','status':'RSS-metadata; feiten en gemeente controleren vóór concept','coverageCandidates':row['municipalities']};sources.append(s)
  r={'source':s['id'],'name':s['name'],'feed':feed,'checkedAt':now,'fullArchive':False,'autoPublish':False}
  try:
   raw=subprocess.run(['curl','--fail','--silent','--show-error','--location','--proto','=https','--proto-redir','=https','--max-time','20','--max-filesize','2000000',feed],capture_output=True,check=True).stdout
   from zoneinfo import ZoneInfo
   today=datetime.datetime.now(ZoneInfo('Europe/Amsterdam')).date()
   items,skipped=parse_feed(raw,s,(today-datetime.timedelta(days=93)).isoformat(),today.isoformat());added=0
   for item in items:added+=merge_signal(known,inbox,item,now)
   r.update(status='ok',received=len(items),added=added,skipped=skipped);row['integration']='RSS aangesloten op privé-inbox; geen automatische publicatie';row['lastIntake']=r;row['next']='Gemeente en feiten per signaal controleren; periodieke productierun nog activeren'
   entry=next((x for x in registry if x['id']==s['id']),None)
   if entry is None:entry={'id':s['id']};registry.append(entry)
   entry.update(name=s['name'],endpoint=feed,adapter='rss',state='ok',scope='Gemeente per bericht controleren',history='Alleen beschikbare feeditems; geen volledig archief',proposedIntervalMinutes=30,rights='Privé-signalering; artikel- en beeldrechten apart controleren',latestCheck=now,received=len(items))
  except Exception as ex:r.update(status='error',error=str(ex))
  report.append(r)
 for name,value in [('sources',sources),('inbox',inbox),('feed-registry',registry),('regional-media-sources',media),('regional-feed-intake-report',report)]:
  target=p/(name+'.json');tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(target)
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
