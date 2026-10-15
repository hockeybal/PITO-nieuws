"""Bounded official VRU archive metadata ingestion. Never copies incident prose/photos."""
import argparse,datetime,hashlib,html,json,re,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MONTHS='januari februari maart april mei juni juli augustus september oktober november december'.split()
def clean(value):return html.unescape(re.sub('<[^>]+>',' ',value)).strip()
def parse(raw,url,start,end):
 if len(raw)>3_000_000:raise ValueError('Pagina te groot')
 source=raw.decode('utf-8');rows=[];dates=[]
 for block in source.split('<div class="incident-result">')[1:]:
  title=re.search(r'<h2>(.*?)</h2>',block,re.S);meta=re.search(r'incident-result__meta-data">(.*?)</div>',block,re.S);link=re.search(r'href="(/incidenten/[^"?]+/)"',block)
  if not(title and meta and link):raise ValueError('Onbekende incidentstructuur')
  text=clean(meta.group(1));match=re.search(r'(\d{2}) (\w+) (\d{4}) - (\d{2}:\d{2})',text)
  if not match:raise ValueError('Incidentdatum ontbreekt')
  day,month,year,time=match.groups();date=datetime.date(int(year),MONTHS.index(month)+1,int(day)).isoformat();dates.append(date)
  if not start<=date<=end:continue
  source_url=urllib.parse.urljoin(url,link.group(1));state=re.search(r'status:\s*(.*?)\s*\|',text)
  rows.append({'id':hashlib.sha256(source_url.encode()).hexdigest()[:20],'sourceId':'vru-incidents','sourceUrl':source_url,'sourceTitle':clean(title.group(1)),'incidentAt':date+'T'+time,'dateType':'incident_date_not_publication','incidentStatus':state.group(1) if state else 'unknown','status':'needs_review','municipalities':[],'note':'Gemeente en feiten verifiëren; gesloten incident nooit als actuele waarschuwing behandelen.'})
 next_link=re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*<div class="sr-only">volgende</div>',source)
 next_url=urllib.parse.urljoin(url,html.unescape(next_link.group(1))) if next_link else None
 if next_url and (urllib.parse.urlsplit(next_url).hostname!='vru.nl' or urllib.parse.urlsplit(next_url).path!='/incidenten/'):raise ValueError('Paginering buiten bron')
 return rows,dates,next_url

def run(start,end,max_pages=40):
 if datetime.date.fromisoformat(start)>datetime.date.fromisoformat(end):raise ValueError('Ongeldige periode')
 p=ROOT/'data/vru-inbox.json';known={r['sourceUrl']:r for r in json.loads(p.read_text())} if p.exists() else {};url='https://vru.nl/incidenten/';seen=set();report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'window':[start,end],'pages':0,'added':0,'status':'ok','completeWithinWindow':False}
 try:
  while url and report['pages']<max_pages:
   if url in seen:raise ValueError('Herhaalde archiefpagina')
   seen.add(url)
   with urllib.request.urlopen(url,timeout=25) as response:raw=response.read(3_000_001)
   rows,dates,next_url=parse(raw,url,start,end);report['pages']+=1
   if not dates:raise ValueError('Geen incidentmetadata; controleer bronstructuur')
   for row in rows:
    old=known.get(row['sourceUrl']);row['lastSeenAt']=report['runAt']
    if old is None:report['added']+=1
    elif old['incidentStatus']==row['incidentStatus'] and old['sourceTitle']==row['sourceTitle']:row={**old,'lastSeenAt':report['runAt']}
    known[row['sourceUrl']]=row
   if not next_url or max(dates)<start:report['completeWithinWindow']=True;break
   url=next_url
 except Exception as e:report.update(status='error',error=str(e)[:250])
 report['signalsInWindow']=sum(start<=r['incidentAt'][:10]<=end for r in known.values())
 for name,data in [('vru-inbox',list(known.values())),('vru-report',report)]:
  target=ROOT/'data'/(name+'.json');tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(target)
 print(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--start',required=True);ap.add_argument('--end',required=True);ap.add_argument('--max-pages',type=int,default=40);a=ap.parse_args();run(a.start,a.end,a.max_pages)
