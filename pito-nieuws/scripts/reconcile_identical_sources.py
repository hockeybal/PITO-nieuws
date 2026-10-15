"""Link identical source copies only when title, date and complete body match.
No automatic merging of broadcast timestamps, index pages or maintenance text.
"""
import collections,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_source_work_queue import canonical
D=json.loads((ROOT/'data/source-documents.json').read_text());A=json.loads((ROOT/'data/articles.json').read_text());groups=collections.defaultdict(list)
for d in D:
 body=re.sub(r'\s+',' ',' '.join(d.get('sourceParagraphs',[]))).strip()
 title=re.sub(r'\s+',' ',d.get('pageTitle','')).strip().casefold()
 if d.get('readStatus')!='read' or len(body)<400 or not title or re.search(r'onderhoud|maintenance|nieuwscarrousel',title):continue
 key=(title,d.get('sourcePublishedAt'),hashlib.sha256(body.encode()).hexdigest());groups[key].append(d)
links={canonical(u):a for a in A for u in [a.get('sourceUrl','')]+[s['url'] for s in a.get('additionalSources',[])] if u};added=[];pending=[]
for group in groups.values():
 if len(group)<2:continue
 targets={links[canonical(d['sourceUrl'])]['slug'] for d in group if canonical(d['sourceUrl']) in links}
 if len(targets)!=1:
  pending.append([d['sourceUrl'] for d in group]);continue
 target=next(a for a in A if a['slug'] in targets)
 for d in group:
  u=d['sourceUrl']
  if canonical(u) in links:continue
  target.setdefault('additionalSources',[]).append({'name':u.split('/')[2],'url':u,'publishedAt':d.get('sourcePublishedAt'),'role':'duplicate'})
  target.setdefault('corroboratingEvidence',[]).append({'evidenceFile':d.get('evidenceFile'),'checkedAt':d.get('checkedAt'),'method':'Identieke titel, brondatum en volledige brontekst; gekoppeld aan reeds uitgewerkt artikel.'})
  links[canonical(u)]=target;added.append({'url':u,'article':target['slug']})
(ROOT/'data/articles.json').write_text(json.dumps(A,ensure_ascii=False,indent=2));(ROOT/'reports/identical-source-groups.json').write_text(json.dumps({'linked':added,'pendingGroups':pending},ensure_ascii=False,indent=2));print(len(added),'bronkopieën gekoppeld;',len(pending),'groepen inhoudelijk te beoordelen')
if __name__=='__main__':pass
