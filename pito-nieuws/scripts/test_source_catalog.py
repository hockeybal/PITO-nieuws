"""Bounded live checks for all registered municipality routes, not a full-site crawl.
Reads robots and one public page per registered URL. Discovers advertised feeds.
"""
import json,datetime,subprocess,concurrent.futures,threading,hashlib
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];AGENT='PITO-source-audit/1.0'
locks={};robots={}
def fetch(url):
 p=subprocess.run(['curl','-sS','-L','--proto','=https','--proto-redir','=https','--max-redirs','3','--max-time','10','--max-filesize','1500000','-A',AGENT,'-w','\n%{http_code}\t%{url_effective}\t%{content_type}',url],capture_output=True)
 if p.returncode:raise ValueError(p.stderr.decode(errors='replace')[:160])
 body,meta=p.stdout.rsplit(b'\n',1);code,final,typ=meta.decode().split('\t',2);return body,int(code),final,typ

def check(row):
 u=row['url'];host=urlsplit(u).netloc;out=dict(row,checkedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),crawlTest='not_tested',feedCandidates=[],discoveredRoutes=[])
 with locks[host]:
  try:
   if host not in robots:
    raw,code,final,typ=fetch('https://'+host+'/robots.txt');rp=RobotFileParser();rp.parse(raw.decode(errors='replace').splitlines());robots[host]=(code,rp,'text/html' in typ)
   code,rp,ishtml=robots[host];out['robotsHttp']=code
   if code==200 and not ishtml:
    if not rp.can_fetch(AGENT,u):out['crawlTest']='robots_disallow';return out
    out['robotsStatus']='allowed'
   elif code==404:out['robotsStatus']='not_present'
   else:out['crawlTest']='robots_unresolved';return out
   raw,code,final,typ=fetch(u);out.update(http=code,finalUrl=final,contentType=typ)
   if code!=200:out['crawlTest']='http_error';return out
   if 'html' not in typ:out['crawlTest']='reachable_non_html';return out
   s=BeautifulSoup(raw,'html.parser');out['title']=s.title.get_text(' ',strip=True)[:200] if s.title else ''
   out['crawlTest']='page_accessible'
   if any(t in out['title'].lower() for t in ['just a moment','access denied','captcha']):out['crawlTest']='access_challenge';return out
   out['feedCandidates']=list(dict.fromkeys(urljoin(final,l['href']) for l in s.select('link[rel="alternate"][href]') if 'rss' in l.get('type','') or 'atom' in l.get('type','')))
   terms=['vereniging','sportaanbod','sportclub','nieuws','agenda','woningcorpor','ondernemersvereniging','cultuur','vrijwilliger','bibliotheek']
   routes={}
   for a in s.select('a[href]'):
    label=a.get_text(' ',strip=True);v=urljoin(final,a['href']);p=urlsplit(v)
    if p.scheme=='https' and any(t in label.lower() for t in terms) and 3<len(label)<180:routes[v]={'url':v,'name':label,'external':p.netloc!=urlsplit(final).netloc}
   out['discoveredRoutes']=list(routes.values())[:40]
  except Exception as ex:out['crawlTest']='error';out['error']=str(ex)
 return out

def main():
 catalog={}
 for c in json.loads((ROOT/'data/municipal-source-inventory.json').read_text()):
  for s in c['sources']:
   if not s['url'].startswith('https://'):continue
   r=catalog.setdefault(s['url'],dict(url=s['url'],name=s['name'],municipalities=[],topics=[]))
   if c['municipality'] not in r['municipalities']:r['municipalities'].append(c['municipality'])
   if s['topic'] not in r['topics']:r['topics'].append(s['topic'])
 for s in json.loads((ROOT/'data/regional-media-sources.json').read_text()):catalog.setdefault(s['url'],dict(url=s['url'],name=s['name'],municipalities=s['municipalities'],topics=['Lokale media']))
 extra=ROOT/'data/supplementary-source-research.json'
 if extra.exists():
  for r in json.loads(extra.read_text()):catalog.setdefault(r['url'],{k:r[k] for k in ('url','name','municipalities','topics')})
 hosts={}
 for r in catalog.values():hosts.setdefault(urlsplit(r['url']).netloc,[]).append(r)
 for host in hosts:locks[host]=threading.Lock()
 jobs=[]
 while hosts:
  for h in list(hosts):
   jobs.append(hosts[h].pop(0))
   if not hosts[h]:del hosts[h]
 output=[];path=ROOT/'data/source-live-tests.json'
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  for row in pool.map(check,jobs):
   output.append(row)
   if len(output)%25==0:
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2));print(len(output),'/',len(jobs),flush=True)
 path.write_text(json.dumps(output,ensure_ascii=False,indent=2));print('Done',len(output),flush=True)
if __name__=='__main__':main()
