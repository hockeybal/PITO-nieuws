"""Explicitly configured RSS/Atom signals only; never copies article bodies or publishes."""
import argparse,datetime,email.utils,hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
if __package__:
 from .source_security import fetch_public_https, parse_xml
else:
 from source_security import fetch_public_https, parse_xml
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
ROOT=Path(__file__).resolve().parents[1]
def canonical(url):
 u=urlsplit(url)
 if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Alleen publieke HTTPS-bronlinks')
 return urlunsplit((u.scheme,u.netloc.lower(),u.path,urlencode([(k,v) for k,v in parse_qsl(u.query) if not k.lower().startswith('utm_')]),''))
def parse_feed(raw,source,start,end):
 root=parse_xml(raw,2_000_000);items=root.findall('.//item') or root.findall('{http://www.w3.org/2005/Atom}entry');result=[];skipped=0
 for item in items:
  def text(name):
   for child in item:
    if child.tag.split('}')[-1]==name:return child.text or ''
   return ''
  title=re.sub('<[^>]*>','',text('title')).strip()[:350];link=text('link')
  if not link:
   link=next((x.attrib.get('href','') for x in item if x.tag.split('}')[-1]=='link' and x.attrib.get('rel','alternate')=='alternate'),'')
  rawdate=text('pubDate') or text('published') or text('updated') or text('date')
  try:
   try:dt=email.utils.parsedate_to_datetime(rawdate)
   except (ValueError,TypeError):dt=datetime.datetime.fromisoformat(rawdate.replace('Z','+00:00'))
   day=dt.date().isoformat();link=canonical(link)
   allowed=source.get('articleHosts',[])
   if allowed and urlsplit(link).hostname not in allowed:raise ValueError('Linkhost buiten broncontract')
   if not start<=day<=end or not title:skipped+=1;continue
  except (ValueError,TypeError,IndexError):skipped+=1;continue
  images=[]
  for child in item.iter():
   tag=child.tag.split('}')[-1]
   if tag not in ('content','thumbnail','enclosure'):continue
   candidate=child.attrib.get('url','')
   if candidate.startswith('https://') and (tag=='thumbnail' or child.attrib.get('medium')=='image' or child.attrib.get('type','').startswith('image/') or re.search(r'\.(jpg|jpeg|png|webp)(?:\?|$)',candidate,re.I)):
    images.append({'url':candidate,'sourcePage':link,'rightsStatus':'unknown','publicationAllowed':False})
  result.append({'imageCandidates':images[:4],'municipalityCandidates':source.get('coverageCandidates',[]),'id':hashlib.sha256(link.encode()).hexdigest()[:20],'sourceTitle':title,'sourceUrl':link,'sourcePublishedAt':day,'sourceId':source['id'],'status':'needs_review','municipalities':[],'sourceMunicipality':source.get('municipality',''),'sourceTimestamp':dt.isoformat(),'fingerprint':hashlib.sha256((title+'|'+rawdate).encode()).hexdigest()[:20],'note':'Geografie en primaire feiten nog door redactie controleren.'})
 return result,skipped

def merge_signal(known,inbox,item,run_at):
 old=known.get(item['sourceUrl'])
 if old is None:
  item['sourceIds']=[item['sourceId']]
  item['sourceMunicipalities']=[item['sourceMunicipality']] if item.get('sourceMunicipality') else []
  item['firstSeenAt']=run_at;item['lastSeenAt']=run_at
  inbox.append(item);known[item['sourceUrl']]=item
  return 1
 old['sourceIds']=sorted(set(old.get('sourceIds',[old['sourceId']])+[item['sourceId']]))
 old['sourceMunicipalities']=sorted(set(old.get('sourceMunicipalities',([old['sourceMunicipality']] if old.get('sourceMunicipality') else []))+([item['sourceMunicipality']] if item.get('sourceMunicipality') else [])))
 old['lastSeenAt']=run_at
 old['imageCandidates']=item.get('imageCandidates',[])
 old['municipalityCandidates']=sorted(set(old.get('municipalityCandidates',[])+item.get('municipalityCandidates',[])))
 if old.get('fingerprint')!=item['fingerprint']:
  if old.get('fingerprint'):old.setdefault('revisions',[]).append({k:old.get(k) for k in ('sourceTitle','sourcePublishedAt','sourceTimestamp','fingerprint')})
  old.update({k:item[k] for k in ('sourceTitle','sourcePublishedAt','sourceTimestamp','fingerprint')})
  old['sourceChangedAt']=run_at;old['status']='needs_review'
 return 0

def run(start,end):
 if start>end:raise ValueError('Begin ligt na einde')
 sources=json.loads((ROOT/'data/sources.json').read_text());p=ROOT/'data/inbox.json';inbox=json.loads(p.read_text());known={x['sourceUrl']:x for x in inbox};report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'window':[start,end],'sources':[],'added':0}
 for s in sources:
  if not s.get('feed'):continue
  r={'source':s['id'],'url':s['feed']}
  try:
   canonical(s['feed'])
   raw=fetch_public_https(s['feed'],max_bytes=2_000_000,timeout=25,user_agent='PITO-feed-intake/1.0')
   items,skipped=parse_feed(raw,s,start,end);added=0
   for item in items:added+=merge_signal(known,inbox,item,report['runAt'])
   r.update(status='ok',receivedInWindow=len(items),skipped=skipped,added=added,oldestReceived=min((i['sourcePublishedAt'] for i in items),default=None),newestReceived=max((i['sourcePublishedAt'] for i in items),default=None),fullArchive=False);report['added']+=added
  except Exception as err:r.update(status='error',error=(err.stderr.decode()[:300] if isinstance(err,subprocess.CalledProcessError) else str(err)))
  report['sources'].append(r)
 p.with_suffix('.tmp').write_text(json.dumps(inbox,ensure_ascii=False,indent=2));p.with_suffix('.tmp').replace(p)
 (ROOT/'data/intake-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
 return report
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2026-04-10');ap.add_argument('--end',default='2026-10-10');a=ap.parse_args();datetime.date.fromisoformat(a.start);datetime.date.fromisoformat(a.end);run(a.start,a.end)
