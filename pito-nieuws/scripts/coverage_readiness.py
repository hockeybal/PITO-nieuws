"""Reproducible coverage audit: source footprints are candidates, not proven coverage."""
import json,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/'data'/name).read_text())
def main():
 cities=read('municipal-source-inventory.json');media=read('regional-media-sources.json');inbox=read('regional-archive-inbox.json');articles=read('articles.json');runs=read('regional-all-crawl-report.json')
 latest={r['id']:r for r in runs}
 for r in read('regional-unfed-crawl-report.json') if (ROOT/'data/regional-unfed-crawl-report.json').exists() else []:
  if r.get('checkedAt','') >= latest.get(r['id'],{}).get('checkedAt',''): latest[r['id']]=r
 runs=list(latest.values())
 rows=[]
 for city in cities:
  slug=city['municipality'];sources=[s for s in media if slug in s['municipalities'] or '*' in s['municipalities']]
  candidates=[x for x in inbox if slug in x.get('municipalityCandidates',[x.get('municipality')])]
  own=[x for x in articles if slug in x.get('municipalities',[])]
  rows.append({'municipality':slug,'name':city['name'],'registeredRoutes':len(city['sources']),'mediaSources':[s['name'] for s in sources], 'crawlRuns':[r for r in runs if slug in r.get('municipalities',[])], 'candidateLinksInSourceArea':len(candidates),'candidateImages':sum(len(x.get('imageCandidates',[])) for x in candidates),'articleRecordsIncludingConcepts':len(own),'benchmarkAgainstLocalEditions':'not_completed','readyForRollout':False,'gaps':['Brongebied is nog geen bevestigde plaats van het nieuws','Driemaandsarchief niet volledig ingelezen en beoordeeld','Artikelinhoud en beeldrechten per publicatie controleren','Lokale sport, ondernemers, woningprojecten en bewonersbronnen verder verdiepen','Productie-Strapi, geplande inname en storingsmonitoring niet geactiveerd']})
 report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete':False,'uniqueIndexCandidates':len(inbox),'imageCandidates':sum(len(x.get('imageCandidates',[])) for x in inbox),'newArticlesPublishedByThisCrawl':0,'municipalities':rows}
 (ROOT/'data/coverage-readiness.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 lines=['PITO — dekking en uitrolgereedheid','Controle: '+report['checkedAt'],'Geen gemeente is hiermee volledig verklaard. Aantallen zijn onderzoeksvoorraad, geen nieuwsproductie.','Unieke indexkandidaten: '+str(len(inbox)), 'Beeldvindplaatsen (rechten onbekend): '+str(report['imageCandidates']), 'Nieuwe publicaties door deze crawl: 0','']
 for row in rows:
  lines.extend([row['name'], 'Media: '+', '.join(row['mediaSources']),f"Bronroutes: {row['registeredRoutes']}; kandidaten in brongebied: {row['candidateLinksInSourceArea']}; bestaande artikelrecords inclusief concepten: {row['articleRecordsIncludingConcepts']}", 'Uitrol: nog niet gereed. Vergelijking met lokale edities: niet afgerond.',*['- '+g for g in row['gaps']],''])
 (ROOT/'reports/dekking-per-gemeente.txt').write_text('\n'.join(lines))
 print(json.dumps({k:v for k,v in report.items() if k!='municipalities'}))
if __name__=='__main__':main()
