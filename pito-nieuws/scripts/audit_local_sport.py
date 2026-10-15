"""Probe official club sites and advertised feeds. No content/photo republication."""
import json,sys,concurrent.futures
from pathlib import Path
from audit_media_sources import audit
ROOT=Path(__file__).resolve().parents[1]
DIRECTORY='https://www.fcutrecht.nl/club/fc-utrecht-partnerclubs/fc-utrecht-partnerclubs/'
SEEDS='''amersfoort|CJVV|www.cjvv.nl
baarn|TOV|www.tov-baarn.nl
bunnik|Bunnik 73|www.bunnik73.nl
de-bilt|FC De Bilt|www.fcdebilt.nl
de-ronde-venen|SV Argon|www.svargon.nl
eemnes|SV Eemnes|www.sveemnes.nl
houten|SV Houten|www.svhouten.nl
ijsselstein|IJFC|www.ijfc.nl
leusden|Roda 46|www.roda46.nl
lopik|SV Lopik|www.svlopik.nl
montfoort|Montfoort SV 19|www.montfoortsv19.nl
nieuwegein|JSV Nieuwegein|www.jsv-nieuwegein.nl
oudewater|FC Oudewater|www.fcoudewater.nl
rhenen|Oranje Wit Elst|www.vvoranjewit.nl
soest|SO Soest|www.so-soest.nl
stichtse-vecht|FC Breukelen|www.fcbreukelen.nl
utrecht|USV Hercules|www.usvhercules.nl
utrechtse-heuvelrug|DEV Doorn|www.devdoorn.nl
veenendaal|GVVV|www.gvvv.nl
vijfheerenlanden|Brederodes|www.brederodes.nl
wijk-bij-duurstede|CDW|cdw.nl
woerden|SCH 44|www.sch44.nl
woudenberg|VV Woudenberg|www.vvwoudenberg.nl
zeist|VV Jonathan|www.vvjonathan.nl'''
rows=json.loads((ROOT/'data/sports-sources.json').read_text())
known={r['url'] for r in rows}
for line in SEEDS.splitlines():
 m,n,d=line.split('|');u='https://'+d+'/'
 if u not in known:rows.append(dict(name=n,url=u,municipality=m,sport='voetbal',discoverySource=DIRECTORY))
for m,n,u in [('renswoude','VV Renswoude','https://www.vvrenswoude.nl/'),('woerden','SC Woerden','https://www.scwoerden.nl/'),('amersfoort','VV Hoogland','https://www.vvhoogland.nl/'),('veenendaal','DOVO','https://www.dovo.nl/196/nieuws/')]:
 if u not in known:rows.append(dict(name=n,url=u,municipality=m,sport='voetbal',discoverySource=u))
def check(row):
 r=audit(row);r['status']='website_verified' if r['homepageStatus']=='Opgehaald' else 'fetch_error'
 r['publicationEnabled']=False
 r['rights']='Bron voor feiten/signalen; geen toestemming voor overname van teksten of clubfoto’s vastgesteld.'
 r['scope']='Eigen clubnieuws, wedstrijdverslagen, evenementen en afgelastingen; geen externe nationale voetbalfeed.'
 good=[f for f in r['feedChecks'] if f.get('items',0)>0]
 if good:r['feed']=good[0]['url'];r['feedStatus']='feed_verified_not_connected'
 else:r['feedStatus']='no_verified_feed'
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(check,rows))
(ROOT/'data/sports-sources.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'clubs':len(result),'municipalities':len({r['municipality'] for r in result}),'websitesReachable':sum(r['status']=='website_verified' for r in result),'feedsVerified':sum(r['feedStatus']=='feed_verified_not_connected' for r in result)}))
