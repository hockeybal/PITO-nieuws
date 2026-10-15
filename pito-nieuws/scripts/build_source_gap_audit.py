"""Reproducible local source coverage audit; never publishes articles."""
import json,csv,re,html,datetime
from pathlib import Path
from collections import Counter
if __package__:
 from .source_security import safe_external_url
else:
 from source_security import safe_external_url
ROOT=Path(__file__).resolve().parents[1]
def read(n):return json.loads((ROOT/n).read_text())
def esc(x):return html.escape(str(x))
def link(u,t):
 # Relative destinations are fixed report navigation, never source data.
 if u=='bronnen.csv' or safe_external_url(u):return '<a href="'+esc(u)+'">'+esc(t)+'</a>'
 return esc(t)
def urls(a):
 return [a.get('sourceUrl','')]+[s.get('url','') for s in a.get('additionalSources',[]) if isinstance(s,dict)]
def identity(u):
 m=re.search(r'rtvutrecht.nl/(?:nieuws|sport)/(\d+)',u or '')
 return 'rtv:'+m[1] if m else (u or '').split('#')[0].rstrip('/')
def main():
 articles=read('data/articles.json');media=read('data/regional-media-sources.json');cities=read('data/municipal-source-inventory.json');sources=read('data/sources.json');run=read('data/intake-report.json');docs=read('data/source-documents.json')
 allin=[]
 for p in (ROOT/'data').glob('*inbox.json'):
  if p.name.startswith('image'):continue
  data=json.loads(p.read_text())
  if isinstance(data,list):allin.extend(x for x in data if isinstance(x,dict))
 inboxids={identity(x.get('sourceUrl')) for x in allin};docids={identity(x.get('sourceUrl')) for x in docs};articleids={identity(u) for a in articles for u in urls(a) if u}
 sample=[];seen=set()
 for x in read('work/rtv-frontpage-audit.json'):
  k=identity(x['url'])
  if k in seen:continue
  seen.add(k);sample.append({**x,'inbox':k in inboxids,'document':k in docids,'article':k in articleids,'reason':'Artikelrecord aanwezig; redactionele status afzonderlijk controleren' if k in articleids else 'Signaal aanwezig; nog geen gekoppeld artikel' if k in inboxids else 'Niet in verzamelde inboxen; feedbereik, sportrubriek of archief onderzoeken'})
 checks={x['source']:x for x in run['sources']};rows=[]
 for s in sources:
  c=checks.get(s.get('id'),{});rows.append({'name':s['name'],'url':s.get('feed') or s.get('url'),'kind':'feed' if s.get('feed') else 'bronroute','status':c.get('status','niet in deze feedrun getest'),'checkedAt':run['runAt'] if c else '', 'items':c.get('receivedInWindow',''),'oldest':c.get('oldestReceived',''),'newest':c.get('newestReceived','')})
 for m in media:
  if not any(r['url']==m['url'] for r in rows):rows.append({'name':m['name'],'url':m['url'],'kind':'website','status':'geïnventariseerd; geen bewijs van compleet archief','checkedAt':m.get('checkedAt',''),'items':'','oldest':'','newest':''})
 discoveries=read('data/source-gap-discoveries.json')
 for d in discoveries:rows.append({'name':d['name'],'url':d['url'],'kind':'aanvulling','status':d['status'],'checkedAt':'2026-10-13','items':'','oldest':'','newest':''})
 report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'feedRun':run['runAt'],'feedCount':len(checks),'feedStatuses':dict(Counter(x['status'] for x in checks.values())),'newSignals':sum(x.get('added',0) for x in checks.values()),'articleStatuses':dict(Counter(a.get('reviewStatus','unknown') for a in articles)),'rtvSample':sample,'sources':rows,'limitations':['Voorpaginasteekproef, geen volledige publicatietelling.','Exacte bronlinks en RTV-artikel-ID’s; een onafhankelijk geschreven bericht over dezelfde gebeurtenis kan alsnog bestaan.','Niet alle geïnventariseerde media-archieven zijn volledig gelezen.','Geen automatisch publicerende redactie; geen volledige driemaandsdekking aangetoond.']}
 (ROOT/'data/source-gap-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 out=ROOT/'static/source-audit';out.mkdir(exist_ok=True)
 with (out/'bronnen.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 body='<p class="eyebrow">PITO · REDACTIONELE DEKKING · 13 OKTOBER 2026</p><h1>Waarom ontbreekt het nieuws?</h1><p><a href="verwerking.html">Bekijk de actuele verwerking, nieuwe artikelen en clubfeeds</a></p><p class="lead">De grootste achterstand zit tussen het binnengekomen signaal en het gecontroleerde artikel. Meer feeds alleen lossen dat niet op.</p>'
 body+=f'<div class="metrics"><p><b>{len(checks)}</b> feeds getest</p><p><b>{report["newSignals"]}</b> nieuwe signalen</p><p><b>{sum(x["inbox"] for x in sample)}/{len(sample)}</b> RTV-links in inboxen</p><p><b>{sum(x["article"] for x in sample)}</b> gekoppelde artikelen</p></div><p>Feedrun: {esc(run["runAt"])}. RTV-steekproef: unieke nieuws- en sportlinks op de voorpagina, inclusief oudere uitgelichte verhalen. Bronkoppeling is geen meting van journalistieke volledigheid.</p>'
 body+='<nav><a href="#oorzaken">Oorzaken</a><a href="#sporen">Bronnen teruggevonden</a><a href="#gemeenten">26 gemeenten</a><a href="#lijst">Bronnenlijst</a><a href="#steekproef">RTV-steekproef</a></nav>'
 causes=[('Geen automatische redactionele verwerking','De pipeline verzamelt metadata. Er is geen doorlopende stap die alle relevante signalen leest, feiten controleert en eigen artikelen voorbereidt. Handmatig aangeleverde links kregen die behandeling wél.'),('RSS is geen archief','De actuele RTV-feed bevat 50 items van 11 tot 13 oktober. Oudere publicaties verdwijnen uit een feed; een datumbereik van drie maanden haalt ze niet terug.'),('Bronlezer sluit kanalen uit','Gevonden en inmiddels hersteld: vaste einddatum, overslaan van RTV en NS en ontbreken van de regionale archiefinbox. De nieuwe lezer verwerkt deze bronnen, bewaart eerder werk en rapporteert fouten. Inhoudelijke eindredactie blijft een aparte stap.'),('Archiefcrawler is beperkt','Paginering volgt zichtbare links; dynamisch Meer laden, ontbrekende datums en redirects geven hiaten. Eerdere crawls zijn gedeeltelijk. Het krantenarchief van Woerdense Courant bestaat bovendien uit digitale edities, niet dezelfde artikelindex.'),('Broninventaris is geen aansluiting','Een website of raadsportaal in het register betekent niet dat alle documenten worden opgehaald. Raadsbrieven, bijlagen, sportclubs, musea, zorgorganisaties en ondernemers vragen eigen routes.'),('Eigen journalistiek is geen openbare feed','Media krijgen tips, interviewen betrokkenen, bezoeken zittingen en werken met fotografen. Een politiefeed bevat niet elk ongeval; een fotograafcredit bewijst niet dat de tekst uit een politiebericht komt.'),('Veel signalen zijn procedures','De bestaande wachtrij wordt gedomineerd door ruim 20.000 officiële publicaties. Dat zijn geen 20.000 zelfstandige nieuwsverhalen; dezelfde gebeurtenis kan meerdere bronnen en updates hebben.')]
 body+='<h2 id="oorzaken">Zeven concrete oorzaken</h2>'+''.join('<h3>'+esc(t)+'</h3><p>'+esc(d)+'</p>' for t,d in causes)
 body+='<h2 id="sporen">Van nieuwsartikel terug naar de bron</h2>'
 for d in discoveries:body+='<article><h3>'+link(d['url'],d['name'])+'</h3><p>'+esc(d['finding'])+'</p><p><strong>Huidige status:</strong> '+esc(d['status'])+'</p>'+(' <p>'+link(d['evidence'],'Gecontroleerde aanleiding / bewijs')+'</p>' if d.get('evidence') else '')+'</article>'
 body+='<h2>Nu technisch aangepast</h2><p>De centrale aanvoer heeft nu een optionele regionale archiefadapter. De wachtrij koppelt ook aanvullende artikelbronnen. De nieuwe feedrun is verwerkt in de wachtrij. Dit activeert geen automatische publicatie of periodieke planning.</p><h2>Wat moet concreet anders?</h2><ol><li><strong>Nieuwe signalen verwerken:</strong> iedere bronrun opvolgen met lokale toewijzing, gebeurtenisgroepering en een leeswachtrij. Per item reden vastleggen: ongelezen, bron ontbreekt, achter betaalmuur, duplicaat, niet lokaal, verouderd, controle nodig of artikel voorbereid.</li><li><strong>Archieven herstellen:</strong> per domein een toegestane route, voortgangscursor, oudste bereikte datum en ontbrekende perioden. Pas compleet noemen als alle pagina’s in het tijdvak aantoonbaar bereikt zijn.</li><li><strong>Primaire bronnen uitbreiden:</strong> gemeenteraad inclusief schriftelijke vragen, collegebrieven en bijlagen; Stedin, vervoerders, waterschappen, woningcorporaties, projectsites, cultuur, sport en wijkorganisaties.</li><li><strong>Eigen redactie aanvullen:</strong> tips en persberichten verzamelen, interviews en wederhoor waar nodig. Niet aannemen dat ieder journalistiek verhaal ergens als gratis persbericht beschikbaar is.</li><li><strong>Dekking bewaken:</strong> dagelijks een onafhankelijke steekproef van lokale voorpagina’s vergelijken met onze inbox én artikelen. Meet gemiste relevante gebeurtenissen, niet alleen het aantal feeds.</li></ol><p>Automatische publicatie is niet geactiveerd. De 389 huidige artikelrecords bestaan uit preview- en conceptmateriaal; bronbereik is geen redactionele goedkeuring.</p>'
 body+='<h2 id="gemeenten">Bronkaart per gemeente</h2><p>Bestaande routes zijn opnieuw samengebracht; dit is geen claim dat elke route vandaag technisch is getest. Alle gemeenten delen provinciale bronnen, politie, VRU en officiële publicaties. Per gemeente ontbreken nog structurele club-, cultuur-, ondernemers- en corporatiekoppelingen.</p>'
 for c in cities:
  mm=[m for m in media if c['municipality'] in m['municipalities'] or '*' in m['municipalities']]
  body+='<details><summary>'+esc(c['name'])+'</summary><h3>Lokale media</h3><p>'+ ' · '.join(link(m['url'],m['name']) for m in mm)+'</p><h3>Officiële en lokale routes</h3><ul>'+''.join('<li>'+link(s['url'],s['name'])+' — '+esc(s.get('state','onbekend'))+'</li>' for s in c['sources'])+'</ul></details>'
 body+='<h2 id="lijst">Actuele technische lijst</h2><p>'+link('bronnen.csv','Download bronnenlijst (CSV)')+'</p><div class="scroll"><table><tr><th>Bron</th><th>Type</th><th>Status</th><th>Controle</th><th>Feedbereik</th></tr>'+''.join('<tr><td>'+link(r['url'],r['name'])+'</td><td>'+esc(r['kind'])+'</td><td>'+esc(r['status'])+'</td><td>'+esc(r['checkedAt'])+'</td><td>'+esc(str(r['oldest'])+' – '+str(r['newest']))+'</td></tr>' for r in rows)+'</table></div>'
 body+='<h2 id="steekproef">RTV: elk aangetroffen artikel verklaard</h2><p>“Geen artikel” betekent geen koppeling via hoofd- of aanvullende bron of RTV-ID. Geen automatische conclusie dat de gebeurtenis nergens op PITO staat.</p><div class="scroll"><table><tr><th>Artikel</th><th>In inbox</th><th>Gekoppeld artikel</th><th>Uitkomst</th></tr>'+''.join('<tr><td>'+link(x['url'],x['title'])+'</td><td>'+('Ja' if x['inbox'] else 'Nee')+'</td><td>'+('Ja' if x['article'] else 'Nee')+'</td><td>'+esc(x['reason'])+'</td></tr>' for x in sample)+'</table></div><p><strong>Onderzoeksgrens:</strong> geen volledige lezing van alle artikelen van alle uitgevers. Dit rapport combineert een actuele technische feedcontrole, code-audit, bestaande bronkaart en inhoudelijke steekproeven. Archiefvolledigheid en dagelijkse monitoring zijn nog niet gerealiseerd.</p>'
 css='body{margin:0;background:#F5F1ED;color:#2C2C2C;font:16px/1.6 system-ui}main{max-width:1140px;margin:40px auto;padding:40px;background:white}h1{font-size:42px;line-height:1.15}h2{margin-top:48px}h3{margin-bottom:6px}a{color:#1050C2}nav,.metrics{display:flex;gap:24px;flex-wrap:wrap}.metrics p{flex:1;background:#F5F1ED;padding:18px}.metrics b{display:block;font-size:32px;color:#1050C2}.eyebrow{color:#1050C2;font-weight:700}.lead{font-size:21px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}.scroll{overflow:auto}details,article{padding:18px 0;border-bottom:1px solid #ddd}summary{cursor:pointer;font-weight:700}@media(max-width:700px){main{padding:20px;margin:0}h1{font-size:32px}}'
 (out/'index.html').write_text('<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta name="robots" content="noindex,nofollow"><title>PITO bronnenonderzoek</title><style>'+css+'</style><main>'+body+'</main></html>')
 print(json.dumps({k:v for k,v in report.items() if k not in ['sources','rtvSample']},ensure_ascii=False))
if __name__=='__main__':main()
