"""Build a local rights-review desk from discovery; never approve candidates."""
import json
from html import escape as e
from pathlib import Path
R=Path(__file__).resolve().parents[1]
rows=json.loads((R/'reports/club-photo-discovery.json').read_text())
names={m['slug']:m['name'] for m in json.loads((R/'data/municipalities.json').read_text())}
priorities={(r['municipality'],r['club']):r for r in json.loads((R/'reports/club-photo-queue.json').read_text())}
coverage=json.loads((R/'reports/image-coverage.json').read_text())
blocks=[]
for slug,name in sorted(names.items(),key=lambda x:x[1]):
 clubs=[]
 for row in sorted(rows,key=lambda r:-priorities.get((r['municipality'],r['club']),{}).get('articleCount',0)):
  if row['municipality']!=slug:continue
  priority=priorities.get((slug,row['club']),{})
  articles=''.join('<li><a href="/nieuws/utrecht/artikel/'+e(a,quote=True)+'">'+e(a.replace('-',' '))+'</a></li>' for a in priority.get('articleSlugs',[]))
  need='<p>'+str(priority.get('articleCount',0))+' gekoppelde artikelen · '+str(len(priority.get('candidateImageKeys',[])))+' beeldbankkandidaten met clubherkenning</p><ul>'+articles+'</ul>'
  links=''.join('<li><a rel="noopener" target="_blank" href="'+e(c['imageUrl'],quote=True)+'">'+e(c['alt'] or 'Fotokandidaat')+'</a></li>' for c in row['candidates'])
  clubs.append('<details><summary>'+e(row['club'])+' · '+str(len(row['candidates']))+' kandidaten</summary><p><a href="'+e(row['pageUrl'],quote=True)+'">Clubbron</a> · '+e(row['status'])+'</p>'+need+'<ul>'+links+'</ul></details>')
 missing=[a for a in coverage['missing'] if slug in a['municipalities']]
 blocks.append('<section id="'+slug+'"><h2>'+e(name)+'</h2><p>'+str(len(missing))+' artikelen zonder passende beeldbankkandidaat</p>'+''.join(clubs)+'</section>')
html='''<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Clubfoto’s controleren | PITO</title><style>*{box-sizing:border-box}body{margin:0;background:#F5F1ED;color:#2C2C2C;font:16px/1.6 system-ui}main{max-width:1120px;margin:auto;padding:32px 20px}h1{line-height:1.15;color:#1050C2}section{background:white;padding:20px;margin:20px 0;border-radius:12px}summary{padding:12px 0;cursor:pointer;font-weight:700}details+details{border-top:1px solid #EDE8DF}a{color:#1050C2;overflow-wrap:anywhere}li{padding:6px 0}.notice{border-left:4px solid #FF5400;padding:12px 20px;background:white}</style><main><a href="/nieuws/utrecht">Naar PITO Nieuws</a><h1>Echte clubfoto’s, per gemeente.</h1><p class="notice">Interne broninventaris. Deze foto's zijn niet goedgekeurd voor publicatie. Controleer de exacte club, fotograaf, gebruikslicentie en opnamedatum vanaf 2022. Een wedstrijdfoto is geen beeld van een andere wedstrijd.</p>'''+'<nav aria-label="Gemeenten">'+' · '.join('<a href="#'+slug+'">'+e(name)+'</a>' for slug,name in names.items())+'</nav>'+''.join(blocks)+'</main></html>'
(R/'static/source-audit/clubfotos.html').write_text(html)
print(f'{len(rows)} clubs, {sum(len(r["candidates"]) for r in rows)} kandidaten, {len(names)} gemeenten')
