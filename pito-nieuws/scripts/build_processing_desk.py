"""Expose processing status without exposing cached full article text."""
import json,html,collections
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
def read(n):return json.loads((ROOT/'data'/n).read_text())
def e(t):return html.escape(str(t))
def main():
 inbox=read('inbox.json');docs={x['sourceUrl']:x for x in read('source-documents.json')};articles=read('articles.json');links={}
 for a in articles:
  for u in [a['sourceUrl']]+[x['url'] for x in a.get('additionalSources',[])]:links.setdefault(u,[]).append(a)
 groups=collections.defaultdict(list)
 for r in inbox:groups[urlsplit(r['sourceUrl']).netloc].append(r)
 body='<h1>Van bron naar artikel</h1><p>Actuele lokale werkvoorraad. “Tekst uitgelezen” is nog geen gecontroleerd artikel. Meerdere bronnen kunnen dezelfde gebeurtenis beschrijven.</p><p><a href="index.html">Bronnenonderzoek</a> · <a href="/nieuws/utrecht/woerden/onderwerp/sport">Sport in Woerden</a></p><p><a href="volledige-verwerking.html">Volledige wachtrij met concrete reden per bronlink</a></p><h2>Directe sportbronnen</h2>'
 for c in read('sports-sources.json'):body+='<p><a href="'+e(c['url'])+'">'+e(c['name'])+'</a> · '+e(c['municipality'])+' · '+e(c['sport'])+' — '+e(c.get('feedStatus') or c['status'])+' · '+str(c.get('received',0))+' signalen'+(' · <a href="'+e(c['feed'])+'">Feed</a>' if c.get('feed') else '')+'</p>'
 body+='<p>Clubverslagen → lokale sportrubriek. Open dagen en toernooien → agenda na datumcontrole. Vrijwilligersvragen → buurtoproepen. Interne teammededelingen krijgen geen provinciale nieuwspositie. Nieuwe clubs worden pas als gekoppeld geteld na een geslaagde inname.</p><h2>Nieuwsfeeds per website</h2><table><tr><th>Website</th><th>Unieke links</th><th>Artikel gekoppeld</th><th>Nieuwe lezer: tekst gevonden</th><th>Niet uitleesbaar / fout</th></tr>'
 counts=[]
 for host,rows in sorted(groups.items(),key=lambda kv:-len(kv[1])):
  linked=sum(r['sourceUrl'] in links for r in rows);readcount=sum(docs.get(r['sourceUrl'],{}).get('extractionVersion')=='article-body-v2' and docs[r['sourceUrl']]['readStatus']=='read' for r in rows);failed=sum(docs.get(r['sourceUrl'],{}).get('extractionVersion')=='article-body-v2' and docs[r['sourceUrl']]['readStatus']!='read' for r in rows)
  body+=f'<tr><td>{e(host)}</td><td>{len(rows)}</td><td>{linked}</td><td>{readcount}</td><td>{failed}</td></tr>';counts.append(dict(host=host,signals=len(rows),linked=linked,extracted=readcount,unreadable=failed))
 body+='</table><h2>Artikelen uit deze verwerkingsronde</h2><ul>'
 for a in articles:
  if a.get('importBatch')=='source-processing-2026-10-13':body+='<li><a href="/nieuws/utrecht/artikel/'+e(a['slug'])+'">'+e(a['title'])+'</a> · '+e(a['sourceName'])+' · '+e(', '.join(a['municipalities']))+'</li>'
 body+='</ul><h2>Leeswachtrij</h2><p>Een ontbrekende artikeltekst kan komen door een betaalmuur, toegangsscherm, JavaScript of een nog niet ondersteunde paginaopbouw. De fout is niet automatisch bewijs van een betaalmuur. Geen kop automatisch als volledig artikel publiceren.</p>'
 for host,rows in sorted(groups.items()):
  body+='<details><summary>'+e(host)+' · '+str(len(rows))+'</summary><ul>'
  for r in sorted(rows,key=lambda r:r.get('sourcePublishedAt',''),reverse=True):
   d=docs.get(r['sourceUrl'],{});status='Artikel voorbereid' if r['sourceUrl'] in links else ('Tekst uitgelezen; redactionele verwerking nodig' if d.get('extractionVersion')=='article-body-v2' and d.get('readStatus')=='read' else 'Niet uitleesbaar; bronroute beoordelen' if d.get('extractionVersion')=='article-body-v2' else 'Nog in leeswachtrij')
   body+='<li><a href="'+e(r['sourceUrl'])+'">'+e(r.get('sourceTitle','Bron'))+'</a> — '+e(status)+'</li>'
  body+='</ul></details>'
 out=ROOT/'static/source-audit/verwerking.html';out.write_text('<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta name="robots" content="noindex,nofollow"><title>PITO verwerking</title><style>body{font:16px/1.6 system-ui;color:#2C2C2C;max-width:1100px;margin:40px auto;padding:24px}a{color:#1050C2}h2{margin-top:36px}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #ddd;text-align:left}details{padding:12px 0;border-bottom:1px solid #ddd}summary{cursor:pointer}li{margin:10px 0}</style>'+body+'</html>')
 (ROOT/'data/processing-desk.json').write_text(json.dumps(counts,indent=2));print('Signals',len(inbox),'article records',len(articles),'hosts',len(groups))
if __name__=='__main__':main()
