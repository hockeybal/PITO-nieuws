"""Follow one council link from each verified municipal homepage."""
import json,datetime,urllib.request,urllib.parse,concurrent.futures
from pathlib import Path
if __package__:
 from .discover_sources import Links, source_links
 from .source_security import fetch_public_https, safe_external_url
else:
 from discover_sources import Links, source_links
 from source_security import fetch_public_https, safe_external_url
ROOT=Path(__file__).resolve().parents[1]
def one(row):
 result=dict(row)
 links=[url for url in row.get('councilLinks',[]) if safe_external_url(url)]
 result['councilLinks']=links
 result['councilPortals']=[url for url in row.get('councilPortals',[]) if safe_external_url(url)]
 for key in ('councilCheckedUrl','councilFinalUrl'):
  if key in result and not safe_external_url(result[key]):result.pop(key)
 if not links:return result
 def score(u):return 10*('gemeenteraad' in u)+8*('raadsinformatie' in u)+5*any(x in u for x in ['bestuurlijkeinformatie','notubiz','gemeentebestuur'])-len(u)/1000
 target=max(links,key=score);result['councilCheckedUrl']=target
 try:
  raw,url=fetch_public_https(target,max_bytes=2_000_000,timeout=15,user_agent='PITO-source-discovery/1.0 (local editorial research)',return_final_url=True)
  parser=Links();parser.feed(raw.decode('utf8','replace'))
  found=source_links(url,(x for x in parser.links if any(w in x.lower() for w in ['raadsinformatie','bestuurlijkeinformatie','notubiz','ibabs','gemeentebestuur','raadsagenda','raadsvergadering','vergaderingen','raadlive'])))
  result.update(councilStatus='page_verified',councilFinalUrl=url,councilPortals=found[:12],councilCheckedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 except Exception as e:result.update(councilStatus='needs_manual_check',councilError=str(e))
 return result
if __name__=='__main__':
 p=ROOT/'data/municipal-source-discovery.json';rows=json.loads(p.read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(one,rows))
 p.write_text(json.dumps(results,ensure_ascii=False,indent=2))
 for r in results:print(r['name'],r.get('councilStatus'),r.get('councilPortals',[])[:3])
