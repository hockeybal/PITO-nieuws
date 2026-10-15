"""Reproducible, evidence-linked disposition of every collected source URL.
A successful download is deliberately never a publication approval.
"""
import collections, datetime, hashlib, html, json, re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
ROOT=Path(__file__).resolve().parents[1]
START='2026-07-13'; END='2026-10-13'
def read(name,default):
 p=ROOT/'data'/name
 return json.loads(p.read_text()) if p.exists() else default
def canonical(url):
 p=urlsplit(url);return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/'),p.query,''))
def disposition(row,doc,links,decisions):
 u=canonical(row['sourceUrl']); day=(doc.get('sourcePublishedAt') or row.get('sourcePublishedAt') or '')[:10]
 text=' '.join(doc.get('sourceParagraphs',[]));title=doc.get('pageTitle') or row.get('sourceTitle') or ''
 if u in links:return 'local_article','Gekoppeld aan een eigen artikel in de lokale editie.',links[u]
 if u in decisions:
  x=decisions[u];return x['status'],x['reason'],x.get('articleSlugs',[])
 if len(text)<600 and re.search(r'onderhoud|maintenance|tijdelijk niet beschikbaar',text,re.I):return 'source_unavailable','De opgehaalde tekst is een onderhoudsmelding, geen artikel.',[]
 if title.strip().lower() in ('home','nieuws','nieuws | gemeente bunschoten','nieuwsoverzicht') and urlsplit(u).path.rstrip('/') in ('','/nieuws','/nieuwsoverzicht'):return 'not_article','Overzichts- of startpagina; geen zelfstandig nieuwsbericht.',[]
 if day and not START<=day<=END:return 'outside_window','Bevestigde brondatum valt buiten het gevraagde kwartaal.',[]
 if doc.get('readStatus')=='error':return 'fetch_error',doc.get('error','Ophalen mislukt.'),[]
 if doc.get('readStatus')!='read':return 'source_unavailable','Geen volledige bruikbare artikeltekst uitgelezen; bronroute moet worden hersteld.',[]
 if not day:return 'date_unconfirmed','Tekst gevonden, maar geen bevestigde publicatiedatum.',[]
 return 'ready_for_writing','Brontekst beschikbaar; inhoudelijke controle, geografische selectie en eigen artikel nog nodig.',[]
def main():
 docs={canonical(d['sourceUrl']):d for d in read('source-documents.json',[])};records={}
 for name in ('municipal-archive-inbox.json','regional-archive-inbox.json','inbox.json','sports-inbox.json'):
  for r in read(name,[]):
   if r.get('sourceUrl'):records.setdefault(canonical(r['sourceUrl']),r)
 articles=read('articles.json',[]);links=collections.defaultdict(list)
 for a in articles:
  for u in [a.get('sourceUrl','')]+[s['url'] for s in a.get('additionalSources',[])]:
   if u:links[canonical(u)].append(a['slug'])
 decisions={canonical(u): d for u,d in read('source-decisions.json',{}).items()};out=[];fingerprints={}
 for u,r in records.items():
  d=docs.get(u,{});status,reason,slugs=disposition(r,d,links,decisions)
  item=dict(sourceUrl=r['sourceUrl'],sourceTitle=d.get('pageTitle') or r.get('sourceTitle',''),sourcePublishedAt=d.get('sourcePublishedAt') or r.get('sourcePublishedAt'),municipality=r.get('municipality') or r.get('sourceMunicipality') or d.get('municipality'),status=status,reason=reason,articleSlugs=slugs,evidenceFile=d.get('evidenceFile'),checkedAt=d.get('checkedAt'))
  decision=decisions.get(u,{})
  if decision.get('evidenceFile'):item['evidenceFile']=decision['evidenceFile']
  if decision.get('checkedAt'):item['checkedAt']=decision['checkedAt']
  if decision.get('relatedArticleSlugs'):item['relatedArticleSlugs']=[slug for slug in decision['relatedArticleSlugs'] if any(a['slug']==slug for a in articles)]
  # Exact body identity is a review hint, not authority to merge unrelated stories.
  text='\n'.join(d.get('sourceParagraphs',[]))
  if status=='ready_for_writing' and text:
   key=hashlib.sha256(text.encode()).hexdigest()
   if key in fingerprints:item['sameBodyAs']=fingerprints[key];item['reason']+=' Identieke brontekst gevonden; dubbele gebeurtenis controleren.'
   else:fingerprints[key]=r['sourceUrl']
  out.append(item)
 counts=dict(collections.Counter(x['status'] for x in out));report=dict(generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),window=[START,END],total=len(out),counts=counts,complete=not any(x['status'] in ('ready_for_writing','date_unconfirmed','fetch_error','source_unavailable','needs_fact_check') for x in out),records=out)
 (ROOT/'data/source-work-queue.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 labels={'local_article':'Lokaal artikel','ready_for_writing':'Uitwerken','date_unconfirmed':'Datum controleren','fetch_error':'Ophaalfout','source_unavailable':'Brontekst ontbreekt','outside_window':'Buiten periode','not_article':'Geen artikel','excluded':'Niet geselecteerd','merged':'Samengevoegd','needs_fact_check':'Feiten controleren'}
 e=lambda x:html.escape(str(x or ''))
 parts=['<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width"><title>PITO volledige bronverwerking</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:32px auto;padding:24px;color:#2c2c2c}a{color:#1050c2}article{padding:16px 0;border-bottom:1px solid #ddd}summary{cursor:pointer;font-weight:700;padding:16px;background:#f5f1ed}small{color:#555}input{padding:12px;width:95%;margin:16px 0}</style><h1>Volledige bronverwerking</h1><p>Iedere gevonden link heeft een status. Uitgelezen tekst is nog geen publiceerbaar artikel. Dit overzicht toont ook de concrete hiaten.</p><p><a href="/nieuws/redactie/aanvoer">Terug naar aanvoer</a> · <a href="basisarchief.html">Basisarchief</a></p><input type="search" placeholder="Zoek gemeente, bron of onderwerp" aria-label="Zoeken">']
 for status,n in counts.items():
  parts.append(f'<details><summary>{e(labels.get(status,status))} · {n}</summary>')
  for r in out:
   if r['status']!=status:continue
   parts.append('<article><a href="'+e(r['sourceUrl'])+'">'+e(r['sourceTitle'])+'</a><br><small>'+e(r['municipality'] or urlsplit(r['sourceUrl']).netloc)+' · '+e(r['sourcePublishedAt'] or 'Datum onbekend')+'</small><p>'+e(r['reason'])+'</p>'+''.join('<a href="/nieuws/utrecht/artikel/'+e(s)+'">Eigen artikel bekijken</a> ' for s in r['articleSlugs'])+''.join('<p><a href="/nieuws/utrecht/artikel/'+e(s)+'">Gerelateerd eigen bericht via andere bronnen</a> — het oorspronkelijke verslag blijft onvolledig gecontroleerd.</p>' for s in r.get('relatedArticleSlugs',[]) if s not in r['articleSlugs'])+'</article>')
  parts.append('</details>')
 parts.append('<script>document.querySelector("input").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();document.querySelectorAll("details").forEach(d=>{let visible=false;d.querySelectorAll("article").forEach(a=>{a.hidden=!a.textContent.toLocaleLowerCase().includes(q);visible ||= !a.hidden});d.hidden=!visible;if(q)d.open=visible})})</script></html>')
 (ROOT/'static/source-audit/volledige-verwerking.html').write_text(''.join(parts));print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False))
if __name__=='__main__':main()
