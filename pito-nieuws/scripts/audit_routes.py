"""HTTP/HTML audit of every editorial route; no browser or external crawling."""
import sys,json,re,urllib.request,concurrent.futures,datetime
from pathlib import Path
from html.parser import HTMLParser
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import news,seo,dossiers
ROOT=Path(__file__).resolve().parents[1]
class Head(HTMLParser):
 def __init__(self):super().__init__();self.h1=0;self.canonical=[];self.description=[];self.title='';self.intitle=False;self.images=[]
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='h1':self.h1+=1
  if t=='title':self.intitle=True
  if t=='link' and d.get('rel')=='canonical':self.canonical.append(d.get('href'))
  if t=='meta' and d.get('name')=='description':self.description.append(d.get('content'))
  if t=='img' and 'news-static' in d.get('src',''):self.images.append(d)
 def handle_endtag(self,t):
  if t=='title':self.intitle=False
 def handle_data(self,s):
  if self.intitle:self.title+=s

def one(path):
 row={'path':path,'issues':[]}
 try:
  with urllib.request.urlopen('http://127.0.0.1:4198'+path,timeout=15) as r:html=r.read().decode();row['status']=r.status
  p=Head();p.feed(html);row.update(title=p.title,h1=p.h1,canonical=p.canonical)
  if p.h1!=1:row['issues'].append('H1 count '+str(p.h1))
  if len(p.canonical)!=1:row['issues'].append('canonical count')
  if len(p.description)!=1 or not p.description[0]:row['issues'].append('description missing')
  if 'noindex,nofollow' not in html:row['issues'].append('preview indexing guard missing')
  for raw in re.findall('<script type="application/ld\\+json">(.*?)</script>',html):json.loads(raw)
  for image in p.images:
   if 'alt' not in image:row['issues'].append('image alt missing')
 except Exception as e:row['issues'].append(str(e))
 return row
if __name__=='__main__':
 paths=[news.BASE,'/nieuws/dossiers','/nieuws/over-de-redactie','/nieuws/redactie/overzicht','/nieuws/seo-controle']
 for m in ['']+[m['slug'] for m in news.read('municipalities')]:
  if m:paths.append(news.BASE+'/'+m)
  paths.extend(seo.agenda_path(m,d) for d in ['','vandaag','morgen','dit-weekend'])
  paths.extend(seo.topic_path(m,c) for c in news.CATEGORIES)
 paths.extend(news.BASE+'/artikel/'+a['slug'] for a in news.articles())
 paths.extend('/nieuws/dossiers/'+k for k in dossiers.DOSSIERS)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,paths))
 issues=[r for r in results if r['issues']];report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'routes':len(results),'failures':len(issues),'results':results}
 (ROOT/'work/route-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({'routes':len(results),'failures':issues},ensure_ascii=False,indent=2))
 sys.exit(bool(issues))
