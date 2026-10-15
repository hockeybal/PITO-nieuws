"""Discover municipal news through advertised links. Stores private evidence, never publishes.
Requires beautifulsoup4. Run with --start/--end and bounded pages per municipality.
"""
import argparse,concurrent.futures,datetime,hashlib,json,re,subprocess,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urldefrag
from bs4 import BeautifulSoup
if __package__:
 from .source_security import fetch_public_https
else:
 from source_security import fetch_public_https
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'work/quarter-sources';CACHE.mkdir(exist_ok=True)
MONTHS={x:i+1 for i,x in enumerate('januari februari maart april mei juni juli augustus september oktober november december'.split())}
def date(text):
 m=re.search(r'\b(20\d{2})-(\d{2})-(\d{2})(?=T|\b)',text)
 if m:return m.group(0)
 m=re.search(r'\b(\d{1,2})[\s-]+('+'|'.join(MONTHS)+r')[\s-]+(20\d{2})\b',text.lower())
 if m:return '%s-%02d-%02d'%(m[3],MONTHS[m[2]],int(m[1]))
 m=re.search(r'\b(\d{2})-(\d{2})-(20\d{2})\b',text)
 if m:return '%s-%s-%s'%(m[3],m[2],m[1])
def fetch(url):
 key=hashlib.sha256(url.encode()).hexdigest()[:24];p=CACHE/(key+'.html')
 if not p.exists() or time.time()-p.stat().st_mtime>21600:
  raw=fetch_public_https(url,max_bytes=3_000_000,timeout=20,user_agent='PITO-local-source-research/1.0')
  p.write_bytes(raw)
 blob=p.read_bytes();version=CACHE/(key+'-'+hashlib.sha256(blob).hexdigest()[:12]+'.html')
 if not version.exists():version.write_bytes(blob)
 return BeautifulSoup(blob,'html.parser'),str(version.relative_to(ROOT))
def listing_date(parent):
 stamp=parent.select_one('time, .objectinfo, .news-date, .date, .news__link > div > span')
 return date(stamp.get('datetime','') or stamp.get_text(' ',strip=True)) if stamp else None
def cleanurl(base,href):return urldefrag(urljoin(base,href))[0]
def run_city(m,start,end,maxpages):
 base=m['homepage'];host=urlsplit(base).netloc
 home=BeautifulSoup((ROOT/'work'/('source-home-'+m['municipality']+'.html')).read_text(),'html.parser')
 links=[cleanurl(base,a['href']) for a in home.select('a[href]')]
 for fragment in home.select('[data-live-region-href]'):
  endpoint=cleanurl(base,fragment['data-live-region-href'])
  if 'news' in endpoint and urlsplit(endpoint).netloc==host:
   lazy,_=fetch(endpoint)
   links.extend(cleanurl(base,a['href']) for a in lazy.select('a[href]'))
 candidates=[u for u in links if urlsplit(u).netloc==host and (re.search(r'/(nieuws|nieuwsoverzicht|nieuwsberichten|nieuws-en-actualiteiten|nieuws-en-meer|actueel)/?$',urlsplit(u).path,re.I) or 'Nieuws:' in u)]
 candidates=list(dict.fromkeys(candidates))
 report={'municipality':m['municipality'],'name':m['name'],'homepage':base,'archiveUrls':candidates,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pages':0,'discovered':0,'hasMore':False,'errors':[],'fullArchive':False}
 pending=candidates[:2];seen=set();records={}
 while pending and len(seen)<maxpages:
  u=pending.pop(0)
  if u in seen:continue
  seen.add(u)
  try:soup,file=fetch(u)
  except Exception as err:report['errors'].append({'url':u,'error':str(err)});continue
  report['pages']+=1
  for fragment in soup.select('[data-live-region-href]'):
   endpoint=cleanurl(u,fragment['data-live-region-href'])
   if 'news' in endpoint and urlsplit(endpoint).netloc==host:
    lazy,_=fetch(endpoint);fragment.replace_with(lazy)
  main=soup.find('main') or soup.find(id='content') or soup
  for a in main.select('a[href]'):
   v=cleanurl(u,a['href']);label=a.get_text(' ',strip=True)
   if urlsplit(v).netloc!=host or v==u or len(v)>1500:continue
   if re.search(r'volgende|next|ouder',label,re.I) or a.get('rel')==['next'] or (label.isdigit() and '?' in v):
    if v not in seen and v not in pending:pending.append(v)
    continue
   if len(label)<18 or len(label)>450 or not a.find(['h2','h3','time']) and not any(x in ' '.join(a.get('class',[])) for x in ['news','teaser','card']):
    parent=(a.find_parent(['article','li']) or a.find_parent(class_='news-list-content'))
    if not parent or not (parent.find('time') or parent.find(['h2','h3']) or date(parent.get_text(' ',strip=True)[:600])):continue
   parent=(a.find_parent(['article','li']) or a.find_parent(class_='news-list-content')) or a
   d=listing_date(parent)
   tm=parent.find('time');d=date(tm.get('datetime','')) if tm and tm.get('datetime') else d
   if d and not start<=d<=end:continue
   if re.search(r'\.(pdf|jpg|png|zip)$',v,re.I):continue
   records[v]={'id':hashlib.sha256(v.encode()).hexdigest()[:20],'sourceUrl':v,'sourceTitle':label,'municipality':m['municipality'],'sourceId':'municipality-'+m['municipality'],'sourcePublishedAt':d,'dateEvidence':'archive_listing' if d else 'missing','status':'needs_full_source_review','discoveredOn':u}
 report['hasMore']=bool(pending);report['discovered']=len(records);report['status']='partial' if records else 'unresolved'
 return report,list(records.values())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2026-07-11');ap.add_argument('--end',default='2026-10-11');ap.add_argument('--max-pages',type=int,default=20);a=ap.parse_args()
 cities=json.loads((ROOT/'data/municipal-source-discovery.json').read_text());reports=[];records=[]
 existing=ROOT/'data/municipal-archive-inbox.json'
 known={r['sourceUrl']:r for r in json.loads(existing.read_text())} if existing.exists() else {}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for report,items in pool.map(lambda m:run_city(m,a.start,a.end,a.max_pages),cities):
   reports.append(report)
   for item in items:known[item['sourceUrl']]=item
   records=list(known.values());print(report['municipality'],report['pages'],len(items),flush=True)
   (ROOT/'data/municipal-archive-report.json').write_text(json.dumps({'window':[a.start,a.end],'sources':reports},ensure_ascii=False,indent=2))
   (ROOT/'data/municipal-archive-inbox.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
