"""Import dated official club signals; never republish bodies or unlicensed images."""
import argparse, concurrent.futures, datetime, hashlib, json, subprocess
from pathlib import Path
from urllib.parse import urlsplit
from intake import parse_feed, merge_signal
ROOT=Path(__file__).resolve().parents[1]
def save(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2026-07-13');ap.add_argument('--end',default=datetime.date.today().isoformat());args=ap.parse_args()
 assert datetime.date.fromisoformat(args.start)<=datetime.date.fromisoformat(args.end)
 clubs=json.loads((ROOT/'data/sports-sources.json').read_text());sources=json.loads((ROOT/'data/sources.json').read_text())
 p=ROOT/'data/sports-inbox.json';inbox=json.loads(p.read_text()) if p.exists() else [];known={x['sourceUrl']:x for x in inbox};now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 def fetch(club):
  feed=club['feed'];host=urlsplit(club['url']).hostname.removeprefix('www.')
  contract=dict(id='club-'+hashlib.sha256(club['url'].encode()).hexdigest()[:12],name=club['name'],url=club['url'],feed=feed,kind='Amateursport / RSS',mode='signal',municipality=club['municipality'],coverageCandidates=[club['municipality']],articleHosts=[host,'www.'+host],publicationEnabled=False)
  try:
   raw=subprocess.run(['curl','--fail','--silent','--show-error','--location','--proto','=https','--proto-redir','=https','--max-time','25','--max-filesize','2000000',feed],capture_output=True,check=True).stdout
   items,skipped=parse_feed(raw,contract,args.start,args.end)
   for i in items:i.update(club=club['name'],sport=club['sport'],categoryCandidate='sport')
   return club,contract,items,dict(name=club['name'],feed=feed,status='ok',received=len(items),skipped=skipped,fullArchive=False)
  except Exception as e:return club,contract,[],dict(name=club['name'],feed=feed,status='error',error=str(e)[:300])
 candidates=[c for c in clubs if c.get('feed') and c.get('feedStatus') in ('feed_verified_not_connected','connected_signals')];report=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fetch,candidates))
 for club,contract,items,r in results:
  if r['status']=='ok':
   r['added']=sum(merge_signal(known,inbox,i,now) for i in items)
   if not items:
    club.update(feedStatus='no_dated_items_in_window',next='Geen gedateerde clubberichten in deze feed; nieuwsindex onderzoeken')
   if items:
    existing=next((s for s in sources if s.get('feed')==contract['feed']),None)
    if existing is None:sources.append(dict(contract,connectedAt=now,status='Clubfeed getest; feiten en beelden apart controleren'))
    club.update(feedStatus='connected_signals',received=len(items),next='Feiten, wedstrijd-/publicatiedatum en beeldrechten beoordelen',connectedAt=now)
  report.append(r)
 save(p,inbox);save(ROOT/'data/sources.json',sources);save(ROOT/'data/sports-sources.json',clubs)
 save(ROOT/'reports/sports-intake.json',dict(checkedAt=now,window=[args.start,args.end],sources=report,added=sum(r.get('added',0) for r in report),publicationEnabled=False))
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
