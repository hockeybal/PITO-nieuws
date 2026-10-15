import json,concurrent.futures,subprocess,re
from html.parser import HTMLParser
from urllib.parse import urljoin
from pathlib import Path
root=Path(__file__).resolve().parents[1]
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.img=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='img':
   src=a.get('src') or a.get('data-src') or ''
   if 'logo' in (src+' '+str(a.get('alt',''))+' '+str(a.get('class',''))).lower():self.img.append({'url':src,'alt':a.get('alt','')})
def run(c):
 p=subprocess.run(['curl','-L','--fail','--max-time','12',c['url']],capture_output=True)
 parser=Parser();parser.feed(p.stdout.decode(errors='replace'))
 return dict(name=c['name'],municipality=c['municipality'],aliases=c.get('aliases',[]),source=c['url'],logos=[dict(x,url=urljoin(c['url'],x['url'])) for x in parser.img][:20],status=p.returncode)
cs=json.load(open(root/'data/sports-sources.json'))
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:out=list(pool.map(run,cs))
(root/'reports/club-logo-discovery.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
for c in out:
 if c['logos']: print(c['name'],json.dumps(c['logos'][:3],ensure_ascii=False))
