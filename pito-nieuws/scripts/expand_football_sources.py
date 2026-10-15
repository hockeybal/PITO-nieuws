import sys,json,datetime,concurrent.futures,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
R=Path.cwd();sys.path.insert(0,str(R/'scripts'))
from audit_media_sources import audit
u='https://www.fcutrecht.nl/club/fc-utrecht-partnerclubs/fc-utrecht-partnerclubs/'
raw=urllib.request.urlopen(u,timeout=30).read();(R/'work/football-directory.html').write_bytes(raw)
soup=BeautifulSoup(raw,'html.parser')
places={'abcoude':'de-ronde-venen','mijdrecht':'de-ronde-venen','werkhoven':'bunnik','benschop':'lopik','de bilt':'de-bilt','vianen':'vijfheerenlanden','breukelen':'stichtse-vecht','bunnik':'bunnik','amersfoort':'amersfoort','utrecht':'utrecht','de meern':'utrecht','veenendaal':'veenendaal','doorn':'utrechtse-heuvelrug','den dolder':'zeist','driebergen':'utrechtse-heuvelrug','amerongen':'utrechtse-heuvelrug','maarssen':'stichtse-vecht','eemnes':'eemnes',"'t goy":'houten','leersum':'utrechtse-heuvelrug','vinkeveen':'de-ronde-venen','houten':'houten','ijsselstein':'ijsselstein','spakenburg-bunschoten':'bunschoten','nieuwegein':'nieuwegein','zeist':'zeist','kamerik':'woerden','kockengen':'stichtse-vecht','lexmond':'vijfheerenlanden','lopik':'lopik','leerdam':'vijfheerenlanden','maarn':'utrechtse-heuvelrug','maartensdijk':'de-bilt','montfoort':'montfoort','odijk':'bunnik','vleuten':'utrecht','cothen':'wijk-bij-duurstede','langbroek':'wijk-bij-duurstede','harmelen':'woerden','woerden':'woerden','soest':'soest','baarn':'baarn','oudewater':'oudewater','loenen aan de vecht':'stichtse-vecht','huis ter heide':'zeist','woudenberg':'woudenberg','elst':'rhenen','wijk bij duurstede':'wijk-bij-duurstede'}
p=R/'data/sports-sources.json';rows=json.loads(p.read_text());host=lambda x:urlsplit(x).netloc.lower().removeprefix('www.')
known={host(x['url']) for x in rows};new=[]
for tr in soup.select('tr'):
 td=tr.select('td');a=tr.select_one('a[href]')
 if len(td)<2 or not a:continue
 place=td[1].get_text(' ',strip=True).lower();url=a['href']
 if place not in places or not url.startswith('http') or host(url) in known:continue
 known.add(host(url));new.append(dict(name=a.get_text(' ',strip=True),url=url.replace('http:','https:'),municipality=places[place],sport='voetbal',discoverySource=u))
def check(r):
 try:
  v=audit(r);v.update(status='website_verified' if v['homepageStatus']=='Opgehaald' else 'fetch_error',publicationEnabled=False,rights='Feitenbron; hergebruik van clubfoto’s en teksten niet vrijgegeven.',scope='Eigen clubnieuws; wedstrijd, team en datum afzonderlijk controleren.')
  good=[f for f in v.get('feedChecks',[]) if f.get('items',0)>0]
  v['feedStatus']='feed_verified_not_connected' if good else 'no_verified_feed'
  if good:v['feed']=good[0]['url']
  return v
 except Exception as e:return dict(r,status='fetch_error',error=str(e),publicationEnabled=False,feedStatus='no_verified_feed')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:added=list(pool.map(check,new))
rows+=added;p.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(R/'reports/football-expansion.json').write_text(json.dumps(dict(checkedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=u,added=added,total=len(rows),complete=False),ensure_ascii=False,indent=2))
print(json.dumps(dict(added=len(added),total=len(rows),reachable=sum(r['status']=='website_verified' for r in added))))
