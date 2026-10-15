"""Build a reproducible coverage matrix from actual feed checks, not assumptions."""
import json,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def read(n):return json.loads((R/'data'/f'{n}.json').read_text())
def build():
 media=read('regional-media-sources');municipal=read('municipal-source-inventory');registry=read('feed-registry')
 rows=[]
 for m in read('municipalities'):
  local=[s for s in media if m['slug'] in s.get('municipalities',[])]
  inv=next((x for x in municipal if x['municipality']==m['slug']),{})
  feeds=[dict(name=s['name'],url=f['url'],items=f.get('items'),checkedAt=s.get('checkedAt')) for s in local for f in s.get('feedChecks',[]) if 'items' in f]
  rows.append(dict(municipality=m['slug'],name=m['name'],media=[dict(name=s['name'],url=s['url']) for s in local],verifiedFeeds=feeds,officialSources=inv.get('sources',[]),gaps=['Per bron tekst- en beeldrechten vastleggen; geen partnerrelatie veronderstellen','Verenigingen, ondernemers, cultuur en woningprojecten afzonderlijk verdiepen','Inname en eindredactie zijn afzonderlijke stappen']))
 report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sitesChecked':len(media),'feedChecks':sum(len(s.get('feedChecks',[])) for s in media),'reachableFeeds':sum('items' in f for s in media for f in s.get('feedChecks',[])),'municipalities':rows,'primaryChannels':[
 {'name':'Politie','method':'Gemeentelijke RSS-feeds en provinciale feed','url':'https://www.politie.nl/rss','action':'Gemeente bepalen per bericht; vermissingen en opsporing actueel houden.'},
 {'name':'Officiële publicaties / KOOP','method':'SRU 2.0','url':'https://data.overheid.nl/dataset/officiele-bekendmakingen','action':'Collectie officiële publicaties gebruiken; oude collectie lokale bekendmakingen is uitgefaseerd. Filter afzender, datum en locatie; aanvraag onderscheiden van besluit.'},
 {'name':'NDW','method':'DATEX II open data','url':'https://opendata.ndw.nu/','action':'Geometrie aan gemeente koppelen, hinder en eindtijd controleren. AVG v2.3 vervalt 9 februari 2027; nieuwe integraties op v3 voorbereiden.'},
 {'name':'NS','method':'Reisinformatie-API','url':'https://apiportal.ns.nl/','action':'API-toegang configureren en stations aan gemeenten koppelen; nieuwsfeed alleen is geen storingsdienst.'},
 {'name':'KNMI','method':'Dataplatform voor waarschuwingen; RSS voor nieuws','url':'https://www.knmi.nl/kennis-en-datacentrum/dataset/rss-feeds-van-het-knmi','action':'Nieuws-RSS niet verwarren met weerwaarschuwingen; Utrechtse waarschuwingsregio selecteren.'},
 {'name':'HDSR','method':'Website / projectpagina’s','url':'https://www.hdsr.nl/actueel/','action':'Dijkwerk, waterkwaliteit, droogte en lokale projecten; RSS nog niet bevestigd.'} ]}
 (R/'data/source-coverage-refresh.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':
 r=build();print(r['sitesChecked'],r['reachableFeeds'],len(r['municipalities']))
