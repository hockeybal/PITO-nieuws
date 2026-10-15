"""Import explicitly written, source-linked summaries into the local preview only."""
import csv,json,re,unicodedata,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run():
 candidates=json.loads((ROOT/'work/quarter-sources/editorial-candidates.json').read_text());p=ROOT/'data/articles.json';articles=json.loads(p.read_text());by_url={a['sourceUrl']:a for a in articles};written=[]
 names={m['slug']:m['name'] for m in json.loads((ROOT/'data/municipalities.json').read_text())}
 for row in csv.reader((ROOT/'work/quarter-sources/written.tsv').open(),delimiter='\t'):
  if len(row)!=5:raise ValueError('Vijf velden vereist: '+str(row[:2]))
  idx,category,title,intro,body=row;r=candidates[int(idx)]
  if not r.get('withinWindow') or r.get('readStatus')!='read':raise ValueError('Onvoldoende broncontrole')
  slug=re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',title).encode('ascii','ignore').decode().lower()).strip('-')
  item={'slug':slug,'title':title,'summary':intro,'body':body,'category':category,'municipalities':r.get('targetMunicipalities',[r['municipality']]),'provinceWide':r.get('targetMunicipalities')==[],'sourceUrl':r['sourceUrl'],'sourceName':r.get('publisher') or 'Gemeente '+names[r['municipality']],'sourcePublishedAt':r['sourcePublishedAt'],'eventDate':None,'dateNote':'Brondatum uit '+r.get('dateEvidence','bron')+'. Dit bericht beschrijft de situatie bij die publicatie; aankondiging is geen bevestiging van uitvoering.','verifiedAt':'2026-10-11','reviewStatus':'preview','reviewer':'','reviewNote':'Broninhoud geraadpleegd en eigen korte tekst opgesteld; menselijke eindredactie vóór externe publicatie.','rights':'Eigen feitelijke samenvatting met bronlink; geen bronfoto’s of citaten overgenomen.','sensitive':category=='Veiligheid' or 'privacyincident' in title.lower(),'priority':2,'imageTopics':{'Bestuur':['bestuur'],'Wonen':['wonen'],'Samenleving':['samenleving'],'Verkeer':['verkeer'],'Veiligheid':['veiligheid']}[category],'ranking':{'impact':2,'reach':2,'urgency':0,'duration':2,'actionability':1,'reason':'Voorlopige lokale relevantie; geen automatisch urgentiealarm.','cluster':slug,'activeUntil':None,'audienceNeed':'explanation','audienceReason':'Gecontroleerde gemeentelijke bron met lokale betekenis.'},'evidence':{'checkedAt':'2026-10-11','method':'Broninhoud gelezen, eigen samenvatting','evidenceFile':r['evidenceFile'],'sourceTitle':r['pageTitle'],'paragraphSourceUrls':[r['sourceUrl']]*2},'importBatch':'quarter-2026-10-11'}
  if r['sourceUrl'] in by_url:
   if by_url[r['sourceUrl']].get('importBatch')==item['importBatch']:by_url[r['sourceUrl']].update(item)
  else:articles.append(item);by_url[r['sourceUrl']]=item
  written.append({'sourceUrl':r['sourceUrl'],'slug':by_url[r['sourceUrl']]['slug'],'sourceRecord':r['id'],'municipality':r['municipality']})
 p.write_text(json.dumps(articles,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'data/quarter-processing.json').write_text(json.dumps({'window':['2026-07-11','2026-10-11'],'processedAt':'2026-10-11','autoPublish':False,'written':written,'remainingCandidates':len(candidates)-len(written),'complete':False},ensure_ascii=False,indent=2))
 print('Lokale artikelen verwerkt:',len(written))
if __name__=='__main__':run()
