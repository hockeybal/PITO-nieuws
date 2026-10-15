"""Test advertised RSS/Atom routes. --connect enables proven, dated feeds as signals.
Never copies article bodies, grants image rights or enables publication.
"""
import argparse,datetime,hashlib,json,threading,concurrent.futures
from urllib.parse import urlsplit
from pathlib import Path
from test_source_catalog import check,fetch,locks
from intake import parse_feed
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--connect',action='store_true');a=ap.parse_args()
 sources=json.loads((ROOT/'data/sources.json').read_text());known={s.get('feed') for s in sources};candidates={}
 for row in json.loads((ROOT/'data/source-live-tests.json').read_text()):
  for url in row['feedCandidates']:
   if '/comments/' in url or urlsplit(url).hostname in ('bdumedia.nl','www.kmp.nl','kmp.nl'):continue
   c=candidates.setdefault(url,dict(url=url,name=row['name'],municipalities=[],topics=[]))
   c['municipalities']=sorted(set(c['municipalities']+row['municipalities']));c['topics']=sorted(set(c['topics']+row['topics']))
 today=datetime.date.today();start=(today-datetime.timedelta(days=92)).isoformat();results=[]
 for c in candidates.values():
  if c['url'] in known:results.append(dict(c,status='already_configured'));continue
  locks.setdefault(urlsplit(c['url']).netloc,threading.Lock());r=check(c)
  if r['crawlTest'] not in ('reachable_non_html','page_accessible'):results.append(dict(r,status='unavailable'));continue
  try:
   raw,code,final,typ=fetch(c['url']);identity='discovered-'+hashlib.sha256(c['url'].encode()).hexdigest()[:12]
   # Domains are pinned after inspecting parsed links; later intakes enforce this contract.
   items,skipped=parse_feed(raw,{'id':identity},start,today.isoformat());r.update(received=len(items),skipped=skipped)
   if not items:r['status']='no_dated_items_in_window'
   else:
    hosts=sorted({urlsplit(i['sourceUrl']).hostname for i in items});r.update(status='tested',articleHosts=hosts)
    if a.connect:
     sources.append(dict(id=identity,name=c['name'],kind='RSS / signalering',url=c['url'],feed=c['url'],mode='signal',coverageCandidates=c['municipalities'],articleHosts=hosts,status='Live XML-inname getest; geografische selectie per bericht vereist',connectedAt=r['checkedAt']));r['status']='connected'
  except Exception as ex:r.update(status='invalid_feed',error=str(ex)[:250])
  results.append(r)
 if a.connect:
  p=ROOT/'data/sources.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(sources,ensure_ascii=False,indent=2));t.replace(p)
 (ROOT/'data/discovered-feed-tests.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps([{'url':r['url'],'status':r['status'],'received':r.get('received')} for r in results],indent=2))
if __name__=='__main__':main()
