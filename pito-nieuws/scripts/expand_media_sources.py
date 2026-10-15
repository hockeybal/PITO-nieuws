"""Probe explicitly scoped regional feeds and discover publisher-linked local sites.
Successful XML endpoints enter the existing metadata-only intake. No publication.
"""
import json,datetime,time,hashlib,sys
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from bs4 import BeautifulSoup
from audit_media_sources import fetch,audit
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=ROOT/'data';media=json.loads((p/'regional-media-sources.json').read_text());known={x['url']:x for x in media};log=[]
 cities=json.loads((p/'municipalities.json').read_text())
 probes=[{'name':'AD '+m['name'],'url':'https://www.ad.nl/'+m['slug']+'/','municipalities':[m['slug']],'knownFeed':'https://www.ad.nl/'+m['slug']+'/rss.xml'} for m in cities]
 probes += [{'name':'indebuurt '+m['name'],'url':'https://indebuurt.nl/'+m['slug']+'/','municipalities':[m['slug']],'knownFeed':'https://indebuurt.nl/'+m['slug']+'/rss.xml'} for m in cities if m['slug'] in ['utrecht','amersfoort','woerden','veenendaal']]
 brands={'de-woudenberger':['woudenberg'],'bunniks-nieuws':['bunnik'],'wijks-nieuws':['wijk-bij-duurstede'],'houtens-nieuws':['houten'],'de-nieuwsbode':['zeist'],'vierklank':['de-bilt'],'de-stad-amersfoort':['amersfoort'],'leusder-krant':['leusden'],'soester-courant':['soest'],'baarnsche-courant':['baarn'],'de-rijnpost':['rhenen','veenendaal','renswoude'],'nieuwsblad-de-kaap':['utrechtse-heuvelrug']}
 if '--bdu-only' in sys.argv:probes=[]
 for brand,area in brands.items():
  evidence='https://bdumedia.nl/nieuwsmerk/'+brand
  try:
   soup=BeautifulSoup(fetch(evidence),'html.parser')
   links=[a for a in soup.select('a[href]') if ('website' in a.get_text(' ',strip=True).lower() or a.get_text(strip=True).startswith('https://www.')) and urlsplit(a['href']).hostname and not urlsplit(a['href']).hostname.endswith('bdumedia.nl')]
   if not links:log.append({'publisherPage':evidence,'status':'site_link_missing'});continue
   url=links[0]['href'];probes.append({'name':brand.replace('-',' ').title(),'url':url,'municipalities':area,'evidence':evidence})
  except Exception as ex:log.append({'publisherPage':evidence,'status':'error','error':str(ex)})
 for row in probes:
  checked=audit(row);ok=any(f.get('items',0)>0 for f in checked['feedChecks'])
  checked.update(evidence=row.get('evidence',row['url']),discoveredOn=datetime.date.today().isoformat(),role='journalistieke signalering',integration='Gecontroleerde feed; inname volgt' if ok else 'Geen werkende feed bevestigd',rights='Alleen privé-signalering. Geen herpublicatielicentie voor tekst of beeld.',next='Metadata inlezen; plaats en feiten onafhankelijk controleren' if ok else 'Website-index nog onderzoeken; blokkades niet omzeilen')
  known[row['url']]=checked;log.append({'name':row['name'],'url':row['url'],'feeds':checked['feedChecks'],'homepage':checked['homepageStatus']});print(row['name'], 'feed_ok' if ok else 'unresolved',flush=True)
  time.sleep(.3)
 (p/'regional-media-sources.json').write_text(json.dumps(list(known.values()),ensure_ascii=False,indent=2));(p/'media-expansion-report.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
