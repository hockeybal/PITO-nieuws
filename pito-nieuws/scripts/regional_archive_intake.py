"""Bounded, robots-aware local news index crawler. Stores metadata, never publishes.
Only follows visible same-origin article and pagination links. Stops on blocks.
"""
import argparse,datetime,hashlib,json,re,subprocess,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urldefrag
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
AGENT='PITO-source-index/1.0'
SOURCES=[
 {'id':'woerdense-courant','name':'Woerdense Courant','origin':'https://www.woerdensecourant.nl','seeds':['/','/112','/sport','/search?q=Woerden&preset=NewestFirst','/search?q=Harmelen&preset=NewestFirst','/search?q=Kamerik&preset=NewestFirst','/search?q=Zegveld&preset=NewestFirst'],'article':r'^/(nieuws|112|sport)/[^/]+/[0-9]+/','local':True},
 {'id':'indebuurt-woerden','name':'indebuurt Woerden','origin':'https://indebuurt.nl','seeds':['/woerden/'],'article':r'^/woerden/.+~\d+','local':True},
 {'id':'rtv-midden-holland','name':'RTV Midden Holland','origin':'https://rtvmiddenholland.nl','seeds':['/midlandfm/'],'article':r'^/nieuws/.+','local':False},
 {'id':'gemeente-woerden','name':'Gemeente Woerden','origin':'https://www.woerden.nl','seeds':['/Actueel','/Nieuws'],'article':r'^/(Nieuws|Actueel)/.+','local':True}]
def fetch(url):
 p=subprocess.run(['curl','-sS','--proto','=https','--max-time','20','--max-filesize','2000000','-A',AGENT,'-w','\n%{http_code}',url],capture_output=True)
 if p.returncode:raise ValueError(p.stderr.decode()[-200:])
 raw,code=p.stdout.rsplit(b'\n',1);code=int(code)
 if code!=200:raise ValueError('HTTP '+str(code))
 return raw

def extract(raw,base,config):
 soup=BeautifulSoup(raw,'html.parser');links={};pages=[];host=urlsplit(config['origin']).netloc
 for a in soup.select('a[href]'):
  u=urldefrag(urljoin(base,a['href']))[0];p=urlsplit(u);heading=a.select_one('h2,h3,h4,.font-vesta-pro-bold,[id="feed-title"],.feed-title');text=(heading or a).get_text(' ',strip=True)
  if p.scheme!='https' or p.netloc!=host or p.username or p.password:continue
  if a.get('rel')==['next'] or re.fullmatch(r'(volgende|volgende pagina|ouder|next|[0-9]+|›|»)',text,re.I):
   if p.path.startswith(urlsplit(base).path.rstrip('/').split('/page/')[0]) or p.path.startswith('/search'):pages.append(u)
   continue
  if config.get('regionalRun') and re.search(r'^/(archive|reader|privacy|bezorgklachten|familieberichten|contact|over-ons|adverteren|vacatures|agenda|joboffers)(/|$)',p.path):continue
  if config.get('regionalRun') and not heading and not a.find_parent('article'):continue
  if not re.search(config['article'],p.path) or len(text)<15 or len(text)>350:continue
  parent=a.find_parent('article') or a.find_parent('li') or a
  context=parent.get_text(' ',strip=True)
  if config.get('localTerms') and not any(re.search(r'\b'+re.escape(t)+r'\b',context,re.I) for t in config['localTerms']):continue
  if not config['local'] and not config.get('regionalRun') and not re.search(r'\b(woerden|harmelen|kamerik|zegveld)\b',context,re.I):continue
  stamp=parent.find('time');d=stamp.get('datetime','')[:10] if stamp else None
  try:datetime.date.fromisoformat(d)
  except (ValueError,TypeError):d=None
  image_candidates=[]
  for image in a.select('img[src]')[:2]:
   image_url=urljoin(base,image.get('src',''))
   if urlsplit(image_url).scheme=='https':image_candidates.append({'url':image_url,'sourcePage':u,'rightsStatus':'unknown','publicationAllowed':False,'note':'Alleen vindplaats; geen toestemming afgeleid uit zichtbaarheid of bronvermelding.'})
  links[u]={'imageCandidates':image_candidates,'sourceUrl':u,'sourceTitle':text,'sourcePublishedAt':d,'dateEvidence':'listing_time' if d else 'missing','discoveredOn':base}
 return list(links.values()),list(dict.fromkeys(pages))
def crawl(config,start,end,maxpages):
 report={'id':config['id'],'name':config['name'],'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pages':0,'dynamicPagination':False,'discovered':0,'errors':[],'fullArchive':False,'autoPublish':False,'window':[start,end],'municipalities':config.get('municipalities',['woerden'])};items={}
 try:
  raw=fetch(config['origin']+'/robots.txt')
  if b'<html' in raw.lower() or b'<!doctype' in raw.lower():raise ValueError('robots.txt bevat HTML; crawl niet gestart')
  robot=RobotFileParser();robot.parse(raw.decode('utf8','replace').splitlines())
 except Exception as ex:report.update(status='blocked',errors=[str(ex)]);return report,[]
 queue=[config['origin']+p for p in config['seeds']];seen=set();delay=max(1,robot.crawl_delay(AGENT) or robot.crawl_delay('*') or 1)
 if delay>30:report.update(status='deferred',errors=['Bron vraagt crawl-delay boven 30 seconden; aparte planning nodig']);return report,[]
 while queue and len(seen)<maxpages:
  u=queue.pop(0)
  if u in seen:continue
  seen.add(u)
  if not robot.can_fetch(AGENT,u):report['errors'].append(u+' uitgesloten door robots');continue
  try:raw=fetch(u);found,pages=extract(raw,u,config)
  except Exception as ex:
   report['errors'].append(u+' '+str(ex))
   if '403' in str(ex) or '429' in str(ex):break
   continue
  report['pages']+=1
  if b'Meer laden' in raw:report['dynamicPagination']=True
  for r in found:
   if r['sourcePublishedAt'] and not start<=r['sourcePublishedAt']<=end:continue
   r.update(id=hashlib.sha256(r['sourceUrl'].encode()).hexdigest()[:20],sourceId=config['id'],municipality=(config.get('municipalities',['woerden'])[0] if len(config.get('municipalities',['woerden']))==1 else ''),municipalityCandidates=config.get('municipalities',['woerden']),geographyStatus='candidate_needs_review',status='needs_full_source_review',note='Indexsignaal; lees bronartikel, controleer datum, plaats en feiten vóór publicatie.')
   items[r['sourceUrl']]=r
  queue.extend(p for p in pages if p not in seen and p not in queue)
  if queue and len(seen)<maxpages:time.sleep(delay)
 report.update(status='partial' if items else 'unresolved',discovered=len(items),hasMore=bool(queue))
 return report,list(items.values())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2026-07-12');ap.add_argument('--end',default=datetime.date.today().isoformat());ap.add_argument('--max-pages',type=int,default=8);ap.add_argument('--all-regions',action='store_true');ap.add_argument('--without-feeds',action='store_true');a=ap.parse_args()
 if datetime.date.fromisoformat(a.start)>datetime.date.fromisoformat(a.end):ap.error('Ongeldige periode')
 p=ROOT/'data/regional-archive-inbox.json';known={x['sourceUrl']:x for x in json.loads(p.read_text())} if p.exists() else {};reports=[]
 configs=SOURCES
 if a.all_regions:
  configs=[]
  for media in json.loads((ROOT/'data/regional-media-sources.json').read_text()):
   if '*' in media['municipalities']:continue
   if a.without_feeds and any(f.get('items',0)>0 for f in media.get('feedChecks',[])):continue
   parsed=urlsplit(media['url']);seeds=[parsed.path or '/']
   research_path=ROOT/'data/archive-image-demand.json'
   if research_path.exists():
    for source in json.loads(research_path.read_text()).get('sources',[]):
     if source['url']!=media['url']:continue
     for category in source.get('categories',[]):
      cp=urlsplit(category['url'])
      if cp.netloc==parsed.netloc and re.fullmatch(r'(112|Sport|Lokaal|Politiek|Horeca|Wonen|Cultuur|Economie)',category['label'],re.I) and cp.path not in seeds:seeds.append(cp.path)
   configs.append({'id':'region-'+hashlib.sha256(media['url'].encode()).hexdigest()[:10],'name':media['name'],'origin':parsed.scheme+'://'+parsed.netloc,'seeds':seeds,'article':r'^/(?!tag/|category/|author/|feed/|wp-|contact|over-ons)[^?#]+','local':True,'regionalRun':True,'municipalities':media['municipalities']})
 for s in configs:
  report,rows=crawl(s,a.start,a.end,a.max_pages);reports.append(report)
  for r in rows:known[r['sourceUrl']]=r
  print(s['name'],report['status'],report['discovered'],flush=True)
 for name,value in [('regional-archive-inbox',list(known.values())),('regional-unfed-crawl-report' if a.without_feeds else 'regional-all-crawl-report' if a.all_regions else 'regional-archive-report',reports)]:
  p=ROOT/'data'/(name+'.json');tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(p)
if __name__=='__main__':main()
