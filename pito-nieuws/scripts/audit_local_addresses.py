"""Discover official municipal service links without inventing contact details."""
import json,subprocess,concurrent.futures,datetime
from pathlib import Path
from urllib.parse import urljoin,urlparse
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1]
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.href=None;self.text=[]
 def handle_starttag(self,t,a):
  if t=='a':self.href=dict(a).get('href');self.text=[]
 def handle_data(self,s):
  if self.href:self.text.append(s)
 def handle_endtag(self,t):
  if t=='a' and self.href:self.links.append((self.href,' '.join(self.text).strip()));self.href=None

def fetch(url):
 p=subprocess.run(['curl','-L','--fail','--max-time','12','--max-filesize','2000000',url],capture_output=True)
 return p.returncode,p.stdout.decode(errors='replace')
def inspect(c):
 base=c['homepage'];status,body=fetch(base);p=Links();p.feed(body);out=dict(municipality=c['municipality'],name=c['name'],homepage=base,checkedAt=datetime.date.today().isoformat(),homepageReachable=status==0,services={})
 for key,words in [('municipality',['contact']),('waste',['afval']),('report',['melding openbare','melding doen','iets melden'])]:
  candidates=[(urljoin(base,u),label) for u,label in p.links if any(w in (label+' '+u).lower() for w in words) and not u.startswith(('mailto:','tel:','#'))]
  candidates=[(u,l) for u,l in candidates if urlparse(u).hostname==urlparse(base).hostname]
  if candidates:
   u,label=min(candidates,key=lambda x:len(x[0]));code,content=fetch(u);out['services'][key]=dict(url=u,label=label,status='verified' if code==0 else 'fetch_failed')
   if key=='waste' and code==0:
    links=Links();links.feed(content)
    out['services'][key]['calendarCandidates']=[dict(url=urljoin(u,h),label=l) for h,l in links.links if any(w in (h+' '+l).lower() for w in ['afvalkalender','afvalwijzer','ophaaldagen','mijnafval','afval-app'])][:8]
  else:out['services'][key]=dict(status='not_found')
 overrides=json.loads((ROOT/'data/local-address-overrides.json').read_text()).get(c['municipality'],{})
 for key,u in overrides.items():
  code,_=fetch(u);out['services'][key]=dict(url=u,label=key,status='verified' if code==0 else 'fetch_failed')
 return out
if __name__=='__main__':
 cs=json.loads((ROOT/'data/municipal-source-discovery.json').read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(inspect,cs))
 (ROOT/'data/local-addresses.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 for r in rows:print(r['name'],[(k,v['status']) for k,v in r['services'].items()])
