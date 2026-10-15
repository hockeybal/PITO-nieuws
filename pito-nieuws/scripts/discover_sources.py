"""Read official home pages; discover advertised RSS and council links, never guess feeds."""
import json,urllib.request,urllib.parse,concurrent.futures,datetime,time
if __package__:
 from .source_security import fetch_public_https, safe_external_url
else:
 from source_security import fetch_public_https, safe_external_url
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.feeds=[];self.title='';self.t=False
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='title':self.t=True
  if tag=='a' and d.get('href'):self.links.append(d['href'])
  if tag=='link' and d.get('type') in ('application/rss+xml','application/atom+xml'):self.feeds.append(d.get('href',''))
 def handle_endtag(self,tag):
  if tag=='title':self.t=False
 def handle_data(self,data):
  if self.t:self.title+=data
def source_links(base,hrefs):
 links=(urllib.parse.urljoin(base,href) for href in hrefs)
 return list(dict.fromkeys(url for url in links if safe_external_url(url)))
exceptions={'de-bilt':'debilt','de-ronde-venen':'derondevenen','stichtse-vecht':'stichtsevecht','utrechtse-heuvelrug':'heuvelrug','wijk-bij-duurstede':'wijkbijduurstede'}
cities=json.loads((ROOT/'data/municipalities.json').read_text())
def one(m):
 base='https://www.'+exceptions.get(m['slug'],m['slug'])+'.nl/'
 row=dict(municipality=m['slug'],name=m['name'],homepage=base,checkedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  raw,final=fetch_public_https(base,max_bytes=2_000_000,timeout=18,user_agent='PITO-source-discovery/1.0 (local editorial research)',return_final_url=True)
  parser=Links();parser.feed(raw.decode('utf-8','replace'));row.update(title=parser.title,homepage=final,status='reachable',feeds=source_links(final,parser.feeds),councilLinks=source_links(final,(x for x in parser.links if any(s in x.lower() for s in ('gemeenteraad','raadsinformatie','notubiz','ibabs','bestuur','besluit'))))[:10])
  (ROOT/'work'/('source-home-'+m['slug']+'.html')).write_bytes(raw)
 except Exception as e:row.update(status='unavailable',error=str(e),feeds=[],councilLinks=[])
 return row
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(one,cities))
 (ROOT/'data/municipal-source-discovery.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 for r in rows:print(r['name'],r['status'],r.get('title','')[:55],r['feeds'],len(r['councilLinks']))
