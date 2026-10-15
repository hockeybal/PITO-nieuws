"""Discover club-owned image candidates; never automatically approve/download photos."""
import concurrent.futures, datetime, json, re, subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
ROOT=Path(__file__).resolve().parents[1]
AGENT='PITO-SourceAudit/1.0'
def fetch(url):
 p=subprocess.run(['curl','--fail','--location','--max-time','18','--max-filesize','4000000','--user-agent',AGENT,url],capture_output=True)
 if p.returncode: raise ValueError(p.stderr.decode(errors='replace')[-200:])
 return p.stdout.decode(errors='replace')
class Images(HTMLParser):
 def __init__(self): super().__init__(); self.images=[];self.rights=[]
 def handle_starttag(self,tag,attrs):
  a={k:(v or '') for k,v in attrs}
  if tag=='img':
   src=a.get('data-src') or a.get('src');alt=a.get('alt','')
   width=re.match(r'^([0-9]+)(?:px)?$',a.get('width',''))
   height=re.match(r'^([0-9]+)(?:px)?$',a.get('height',''))
   if any(m and int(m.group(1))<100 for m in (width,height)):return
   if src:self.images.append((src,alt))
  if tag=='meta' and a.get('property')=='og:image': self.images.append((a.get('content',''),'Sociale hoofdfoto; onderwerp controleren'))
  if tag=='a' and any(x in a.get('href','').lower() for x in ['copyright','disclaimer','voorwaarden','creativecommons.org']): self.rights.append(a['href'])
def inspect(c):
 out={'club':c['club'],'municipality':c['municipality'],'pageUrl':c['source'],'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidates':[],'automaticPhotoReuse':False}
 try:
  origin=urlparse(c['source']); robots=f'{origin.scheme}://{origin.netloc}/robots.txt'
  try:
   raw=fetch(robots);rp=RobotFileParser();rp.parse(raw.splitlines())
   if not rp.can_fetch(AGENT,c['source']):out['status']='robots_disallowed';return out
  except ValueError as e:
   # Only an explicit absent robots file permits continuing.
   if '404' not in str(e):out.update(status='robots_check_failed',error=str(e));return out
  html=fetch(c['source']); parser=Images();parser.feed(html)
  seen=set()
  for src,alt in parser.images:
   url=urljoin(c['source'],src)
   if not url.startswith(('http://','https://')) or url in seen:continue
   seen.add(url)
   if re.search(r'logo|icon|sponsor|badge|pixel|banner|emailbutton|printbutton|facebooklikeandshare|social[-_]|spacer|avatar',url+' '+alt,re.I):continue
   out['candidates'].append({'imageUrl':url,'alt':alt,'sourcePage':c['source'],'rightsStatus':'unverified','capturedAt':None,'approved':False,'next':'Onderwerp, fotograaf, opnamedatum vanaf 2022 en expliciete licentie controleren.'})
   if len(out['candidates'])>=20:break
  out['rightsPages']=list(dict.fromkeys(urljoin(c['source'],x) for x in parser.rights))
  out['status']='candidates_need_verification' if out['candidates'] else 'no_photo_candidate'
 except Exception as e:out.update(status='fetch_failed',error=str(e),candidates=[])
 return out
if __name__=='__main__':
 clubs=json.loads((ROOT/'reports/club-photo-queue.json').read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(inspect,clubs))
 target=ROOT/'reports/club-photo-discovery.json';target.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'clubs':len(rows),'candidates':sum(len(r['candidates']) for r in rows),'clubsWithCandidates':sum(bool(r['candidates']) for r in rows),'statuses':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})}}))
