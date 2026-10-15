"""Inspect configured homepages and explicitly advertised feeds; never publish."""
import json,subprocess,datetime,concurrent.futures,xml.etree.ElementTree as ET
if __package__:
 from .source_security import fetch_public_https, parse_xml
else:
 from source_security import fetch_public_https, parse_xml
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Links(HTMLParser):
 def __init__(self):super().__init__();self.feeds=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='link' and a.get('type') in ('application/rss+xml','application/atom+xml') and 'comments' not in a.get('href',''):self.feeds.append(a.get('href',''))
def fetch(url):
 return fetch_public_https(url,max_bytes=2_000_000,timeout=15,user_agent='PITO-media-source-audit/1.0')
def audit(row):
 row['checkedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();row['feedChecks']=[]
 try:
  raw=fetch(row['url']);parser=Links();parser.feed(raw.decode('utf8','replace'));row['homepageStatus']='Opgehaald';feeds=list(dict.fromkeys(urljoin(row['url'],u) for u in parser.feeds))[:3]
 except Exception as ex:row['homepageStatus']=str(ex);feeds=[]
 if row.get('knownFeed'):feeds.insert(0,row['knownFeed'])
 for url in dict.fromkeys(feeds):
  item={'url':url}
  try:
   raw=fetch(url)
   root=parse_xml(raw,2_000_000)
   if root.tag not in ('rss','{http://www.w3.org/2005/Atom}feed','{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF'):raise ValueError('Geen RSS/Atom')
   item.update(status='XML-feed bereikbaar',items=len(root.findall('.//item') or root.findall('{http://www.w3.org/2005/Atom}entry')))
  except Exception as ex:item['status']=str(ex)
  row['feedChecks'].append(item)
 row['next']='Feedadapter toevoegen en geografie controleren' if any(x.get('items',0)>0 for x in row['feedChecks']) else 'Website-index / sitemap onderzoeken; toegang, voorwaarden en archiefpaginering nog toetsen'
 return row
if __name__=='__main__':
 p=ROOT/'data/regional-media-sources.json';rows=json.loads(p.read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:result=list(pool.map(audit,rows))
 p.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps([{'name':r['name'],'homepage':r['homepageStatus'],'feeds':r['feedChecks']} for r in result],ensure_ascii=False,indent=2))
