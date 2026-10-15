"""Evidence-linked municipal source map. Discovery is never marked as a working feed."""
import json,re,csv,sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
if __package__:
 from .source_security import safe_external_url
else:
 from source_security import safe_external_url
ROOT=Path(__file__).resolve().parents[1]
def read(n,default=None):
 p=ROOT/'data'/(n+'.json');return json.loads(p.read_text()) if p.exists() else default
GROUPS={'Wonen & bouwplannen':r'bouwproject|woningbouw|gebiedsontwikkel|projecten|houten.bouwt|woonvisie','Omgeving & inspraak':r'omgevings|participatie|denk.mee|praat.mee','Verkeer & werkzaamheden':r'wegwerk|werkzaamheden|verkeer|bereikbaarheid','Ondernemers':r'ondernem|winkel|bedrijv','Sport & verenigingen':r'sport|verenigin','Agenda & cultuur':r'evenement|agenda|cultuur|uitagenda','Zorg & buurtinitiatieven':r'vrijwillig|welzijn|zorg|buurt|subsidie','Bestuur & besluiten':r'college|gemeenteraad|begroting|besluit'}
MEDIA={'amersfoort':['De Stad Amersfoort'],'baarn':['Baarnsche Courant'],'bunnik':['Bunniks Nieuws'],'de-bilt':['De Vierklank'],'houten':['Houtens Nieuws'],'leusden':['Leusder Krant'],'soest':['Soester Courant'],'utrechtse-heuvelrug':['De Kaap'],'veenendaal':['De Rijnpost'],'rhenen':['De Rijnpost'],'wijk-bij-duurstede':['Wijks Nieuws'],'woudenberg':['De Woudenberger'],'zeist':['De Nieuwsbode']}
KMP={'woerden':['Woerdense Courant'],'ijsselstein':['Zenderstreeknieuws'],'lopik':['Zenderstreeknieuws'],'montfoort':['Zenderstreeknieuws'],'nieuwegein':['Molenkruier'],'vijfheerenlanden':['Het Kontakt Vijfheerenlanden']}
def build():
 articles=read('articles',[]);sources=read('sources',[]);reports={r['municipality']:r for r in read('municipal-archive-report',{}).get('sources',[])};out=[]
 for m in read('municipal-source-discovery',[]):
  slug=m['municipality'];local=[a for a in articles if slug in a.get('municipalities',[]) and '2026-07-11'<=(a.get('sourcePublishedAt') or '')<='2026-10-11' and a.get('reviewStatus') in ['preview','approved']]
  found=[];seen=set()
  def add(topic,name,url,state,evidence,workflow):
   if not safe_external_url(url) or (topic,url) in seen:return
   seen.add((topic,url));found.append(dict(topic=topic,name=name,url=url,state=state,evidence=evidence,workflow=workflow))
  ar=reports.get(slug,{})
  for url in ar.get('archiveUrls',[]):add('Gemeentenieuws','Nieuwsarchief '+m['name'],url,ar.get('status','onbekend'),m['homepage'],'Gemeentelijke archiefadapter → privé broncontrole → eigen concept')
  add('Bestuur & besluiten','Gemeenteraad',m.get('councilFinalUrl') or m.get('councilCheckedUrl'),m.get('councilStatus','onbekend'),m['homepage'],'OpenBesluitvorming waar beschikbaar; voorstel en besluit afzonderlijk lezen')
  for url in m.get('councilPortals',[])[:3]:add('Bestuur & besluiten','Raadsportaal',url,'Link aangetroffen',m.get('councilFinalUrl') or m['homepage'],'Documenten en besluitstatus beoordelen; geen automatische artikelpublicatie')
  soup=BeautifulSoup((ROOT/'work'/('source-home-'+slug+'.html')).read_text(),'html.parser')
  for a in soup.select('a[href]'):
   url=urljoin(m['homepage'],a['href']);label=a.get_text(' ',strip=True)
   if urlsplit(url).scheme!='https' or not label:continue
   for topic,pattern in GROUPS.items():
    if re.search(pattern,label+' '+url,re.I):add(topic,label[:140],url,'Link aangetroffen op gemeentewebsite',m['homepage'],'Rubriek ontdekken; volledige inhoud en datering nog controleren')
  for s in sources:
   if s.get('municipality')==slug and s.get('feed'):add('Politie & veiligheid' if 'politie' in s['id'] else 'Gemeentenieuws',s['name'],s['feed'],'Feedadapter aanwezig',s.get('url') or s['feed'],'Metadata ontdubbelen; bronpagina lezen; geen automatische urgente melding')
  add('Omgeving & inspraak','Officiële bekendmakingen — '+m['name'],'https://zoek.officielebekendmakingen.nl/','KOOP-inname per gemeentelijke afzender', 'https://repository.overheid.nl/sru','Aanvraag, ontwerp en besluit onderscheiden; kleine routinemeldingen selecteren')
  for name in MEDIA.get(slug,[]):add('Lokale media',name,'https://bdumedia.nl/nieuwsmerk/','Titel geverifieerd in uitgeversoverzicht','https://bdumedia.nl/nieuwsmerk/','Signaleringsbron; lokale redactie/site en eigen primaire bevestiging vervolgen')
  for name in KMP.get(slug,[]):add('Lokale media',name,'https://www.kmp.nl/onze-titels/hetkontakt/','Titel geverifieerd in uitgeversoverzicht','https://www.kmp.nl/onze-titels/hetkontakt/','Signaleringsbron; geen overname van artikelen of foto’s')
  add('Regionale media','RTV Utrecht','https://www.rtvutrecht.nl/','RSS-signalering aanwezig','https://www.rtvutrecht.nl/','Provinciebreed signaleren; artikel vervolgens lokaal bevestigen')
  if slug in ['baarn','bunschoten','soest']:add('Lokale media','Eemland1','https://www.eemland1.nl/','Website gecontroleerd','https://www.eemland1.nl/live-tv/','Nieuws signaleren; rechten en primaire bron per verhaal vastleggen')
  missing=['Lokale sportclubs en wedstrijdbronnen nog niet volledig geïnventariseerd','Ondernemersverenigingen en winkelopeningen nog niet volledig aangesloten','Woningcorporaties, ontwikkelaars en makelaars nog per gemeente uitwerken','Agenda-organisatoren aanvullen naast bestaande PITO-Strapi-koppeling','Geen bewijs dat alle nieuwsberichten uit drie maanden zijn gevonden']
  if not ar.get('discovered'):missing.insert(0,'Gemeentelijk nieuwsarchief nog niet werkend ontsloten')
  out.append(dict(municipality=slug,name=m['name'],window=['2026-07-11','2026-10-11'],articles=len(local),monthly=dict(Counter(a['sourcePublishedAt'][:7] for a in local)),articleSlugs=[a['slug'] for a in sorted(local,key=lambda a:a['sourcePublishedAt'],reverse=True)],archive=ar,sources=found,gaps=missing,complete=False))
 (ROOT/'data/municipal-source-inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 with (ROOT/'data/municipal-source-inventory.csv').open('w') as f:
  fields=['municipality','topic','name','url','state','evidence','workflow'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for m in out:
   for s in m['sources']:w.writerow(dict(municipality=m['municipality'],**s))
 print(len(out),'gemeenten;',sum(len(m['sources']) for m in out),'bronroutes')
if __name__=='__main__':build()
