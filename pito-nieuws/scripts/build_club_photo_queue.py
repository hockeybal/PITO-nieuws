"""Prioritize exact club photography without granting automatic reuse rights."""
import json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import media_library
articles=json.loads((R/'data/articles.json').read_text());bank=media_library.load();rows=[]
for c in media_library.football_clubs():
 matches=[a for a in articles if c in media_library.matching_football_clubs(a)]
 terms=[c['name']]+c.get('aliases',[])
 images=[k for k,m in bank.items() if media_library.eligible(m) and m.get('kind') in ('photo','commons-photo') and c['municipality'] in m.get('municipalities',[]) and media_library.club_mentions(' '.join(m.get('subjectTerms',[]))+' '+m.get('alt',''),c)]
 rows.append(dict(club=c['name'],municipality=c['municipality'],source=c['url'],articleCount=len(matches),articleSlugs=[a['slug'] for a in matches],candidateImageKeys=images,status='check_exact_subject' if images else 'photo_needed',required=['Sportpark / clubgebouw vanaf 2022','Opnamedatum, maker en licentie','Wedstrijdfoto alleen aan exacte wedstrijd koppelen'],automaticPhotoReuse=False))
rows.sort(key=lambda r:(bool(r['candidateImageKeys']),-r['articleCount'],r['municipality'],r['club']))
(R/'reports/club-photo-queue.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'clubs':len(rows),'municipalities':len({r['municipality'] for r in rows}),'clubsWithPhotoCandidate':sum(bool(r['candidateImageKeys']) for r in rows),'matchedArticles':sum(r['articleCount'] for r in rows)}))
