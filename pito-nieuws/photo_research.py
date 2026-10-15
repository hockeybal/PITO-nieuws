"""Local editorial overview: discovered candidates are never counted as approved photos."""
import json,collections
from pathlib import Path
import news,media_library
R=Path(__file__).parent
def read(path,default):
 try:return json.loads((R/path).read_text())
 except (OSError,ValueError):return default
def page():
 data=read('data/archive-image-demand.json',{});sources=data.get('sources',[])
 for evidence in read('data/archive-browser-evidence.json',[]):
  for source in sources:
   if source['name']==evidence['name']:
    source['pages']=list(dict.fromkeys(source['pages']+evidence['pages']));source['categories']=evidence['categories'];source['browserNote']=evidence['note']
 rows=read('work/photo-scale/candidates.json',[]);library=media_library.load();approved={media_library.identity(x) for x in library.values() if media_library.eligible(x)}
 new=[x for x in library.values() if x.get('batch')=='archive-expansion-2026-10-12' and media_library.eligible(x)];downloaded=sum((R/'work/photo-scale/photos'/(x['id']+'.jpg')).exists() for x in rows)
 e=news.e
 body='<section class="section"><p class="eyebrow">REDACTIE · BEELDONDERZOEK</p><h1>Van nieuwsarchief naar passende fotografie.</h1><p class="standfirst">Het doel is 1.000–2.000 extra bruikbare foto’s. Zoekresultaten tellen pas mee na controle van datum, licentie, onderwerp, locatie en beeldkwaliteit.</p><div class="research-metrics">'
 for n,label in [(len(sources),'bronpagina’s gecontroleerd'),(len(rows),'recente fotokandidaten'),(downloaded,'bestanden ter beoordeling'),(len(new),'extra goedgekeurde foto’s'),(len(approved),'unieke foto’s in de beeldbank')]:body+='<div><strong>'+str(n)+'</strong><span>'+label+'</span></div>'
 body+='</div>'
 state=read('work/photo-scale/download-state.json',{})
 if state:
  label={'running':'Foto’s worden opgehaald voor beoordeling','cooldown':'Inname wacht op de toegestane hervattingstijd van de bron','finished':'Deze ophaalronde is afgerond','stopped_network_errors':'Inname onderbroken door herhaalde verbindingsfouten; wachtrij bewaard'}.get(state.get('status'),'Innamestatus beschikbaar')
  body+='<p class=notice><strong>'+e(label)+'</strong><br>Laatst bijgewerkt: '+e(state.get('updatedAt',''))+'. Dit is een momentopname; de pagina vernieuwen toont de nieuwste stand. Ophalen betekent nog niet goedkeuren.</p>'
 body+='<p><a href="/nieuws/beeldbibliotheek">Open de doorzoekbare beeldbank ›</a></p><h2>Wat de archieven laten zien</h2><div class="research-findings">'
 findings=[('Niet alleen incidenten','De lokale nieuwsstructuur vraagt ook beeld van winkels, horeca, verenigingen, cultuur, scholen, zorg, woonprojecten en herkenbare straten. Dit is een redactionele conclusie uit de onderzochte rubrieken, geen gemeten populariteitsranglijst.'),('Een archief is niet altijd een artikelfeed','Bij Woerdense Courant bevat /archive digitale krantenedities. Rubrieken en zoekresultaten leveren andere toegangspaden. Een RSS-feed alleen dekt het verleden niet.'),('Dossiers hebben eigen beelden nodig','De Stad Amersfoort toont onder meer verkiezingen, historie en zorgdossiers. Voor PITO leggen we gebouwen, organisaties en locaties afzonderlijk vast; een willekeurige raadzaal of sportfoto is geen vervanger.'),('AD en indebuurt: meer dan één tijdlijn','AD Woerden combineert Net Binnen, 112, uit-tips, eten en drinken, regiosport, lezersbijdragen en dossiers. Indebuurt groepeert nieuws, doen, bewoners, winkels en wonen. Voor onze beeldbank zijn daarom ook lokale zaken, voorzieningen, seizoenen en evenementen nodig. De AD-regiostroom bevat bovendien berichten buiten Woerden: bronselectie alleen is geen gemeentefilter.'),('De collectie blijft plaatsgebonden','Een foto van een specifiek station, sportpark of gemeentehuis blijft aan die plek gekoppeld. Nieuwe archiefbeelden worden eerst als handmatige redactionele keuze toegevoegd; ze worden niet breed aan willekeurige nieuwsberichten gekoppeld.')]
 for title,text in findings:body+='<article><h3>'+title+'</h3><p>'+text+'</p></article>'
 body+='</div>'
 demand=read('data/photo-demand-topics.json',{})
 body+='<h2>Onderwerpen uit de broninventaris</h2><p>'+str(demand.get('signalCount',0))+' unieke bronlinks onderzocht op titel. Categorieën overlappen; dit is een onvolledige steekproef en geen bezoekers- of populariteitsmeting.</p><div class="research-table"><table><thead><tr><th>Onderwerp</th><th>Aangetroffen signalen</th></tr></thead><tbody>'+''.join('<tr><td>'+e(t['name'])+'</td><td>'+str(t['observedSignals'])+'</td></tr>' for t in demand.get('topics',[]))+'</tbody></table></div>'
 body+='<h2>Opbouw van de uitbreiding</h2><p>Werkverdeling voor 1.500 nieuwe beelden, nog geen gerealiseerde aantallen en geen wetenschappelijk berekende quota.</p><div class="research-table"><table><thead><tr><th>Collectie</th><th>Streefgetal</th><th>Wat erin hoort</th></tr></thead><tbody>'
 for label,n,detail in [('Gemeenten en dorpen',650,'Gemiddeld 25 verschillende plekken per gemeente: centrum, station, wijk, openbare voorziening, park en landschap.'),('Nieuws en dagelijks leven',650,'Verkeer, hulpdiensten, wonen, onderwijs, zorg, economie, natuur, weer, sport en cultuur. Geen tientallen vrijwel gelijke uitsneden.'),('Herkenbare organisaties',200,'Sportclubs, overheidsgebouwen, ziekenhuizen, bibliotheken en andere instellingen; alleen exact passende en bruikbaar gelicentieerde foto’s.')]:body+='<tr><td>'+label+'</td><td>'+str(n)+'</td><td>'+detail+'</td></tr>'
 body+='</tbody></table></div><h2>Dekking per gemeente</h2><div class="research-table"><table><thead><tr><th>Gemeente</th><th>Kandidaten</th><th>Nieuw goedgekeurd</th><th>Bronpagina’s</th></tr></thead><tbody>'
 for m in news.read('municipalities'):
  slug=m['slug'];body+='<tr><td><a href="/nieuws/beeldbibliotheek?gemeente='+slug+'">'+e(m['name'])+'</a></td><td>'+str(sum(r['municipality']==slug for r in rows))+'</td><td>'+str(sum(slug in r.get('municipalities',[]) for r in new))+'</td><td>'+str(sum(slug in s.get('municipalities',[]) or '*' in s.get('municipalities',[]) for s in sources))+'</td></tr>'
 body+='</tbody></table></div><h2>Bron voor bron</h2><p>Deze inventaris betreft de geregistreerde Utrechtse bronnen. Een bereikbare homepage is geen bewijs van een volledig doorzocht archief. De zelfstandige crawler wordt bij AD en indebuurt doorverwezen. Hun gemeentepagina’s zijn aanvullend in de browser gecontroleerd; de uitkomst en eventuele redirects staan hieronder. Dat is geen werkende automatische archiefkoppeling voor alle edities.</p>'
 deep={x['name']:x for x in read('data/regional-all-crawl-report.json',[])}
 for s in sources:
  body+='<details class="research-source"><summary>'+e(s['name'])+' · '+str(len(s['pages']))+' pagina’s bekeken · '+('gedeeltelijk onderzocht' if s['pages'] else 'niet inhoudelijk onderzocht')+'</summary><p><a href="'+e(s['url'])+'">Open bron</a></p>'
  if s.get('browserNote'):body+='<p>'+e(s['browserNote'])+'</p>'
  detail=deep.get(s['name'],{})
  if detail:body+='<p>Rubriekcrawl: '+str(detail.get('pages',0))+' pagina’s, '+str(detail.get('discovered',0))+' signalen. Volledig archief: nee.</p>'
  cats=s.get('categories',[])[:18]
  body+='<p>'+(' · '.join('<a href="'+e(x['url'])+'">'+e(x['label'])+'</a>' for x in cats) or 'Geen rubrieknavigatie vastgesteld.')+'</p>'
  if s.get('archiveLinks'):body+='<ul>'+''.join('<li><a href="'+e(u)+'">'+e(u)+'</a></li>' for u in s['archiveLinks'][:8])+'</ul>'
  if s.get('errors'):body+='<p>'+e('; '.join(s['errors']))+'</p>'
  body+='</details>'
 body+='<h2>Aanvullende beeldbronnen</h2><div class=research-findings>'+''.join('<article><h3><a href="'+e(x['url'])+'">'+e(x['name'])+'</a></h3><p>'+e(x.get('rights',''))+'</p><p>'+e(x.get('action',x.get('limitation','')))+'</p></article>' for x in read('data/photo-source-alternatives.json',[]))+'</div>'
 body+='<h2>Publicatievoorwaarden</h2><p>Foto’s van nieuwssites dienen hier als aanwijzing voor het benodigde onderwerp. We downloaden ze niet voor herpublicatie zonder een passende licentie. Commons-kandidaten blijven buiten de publieke beeldbank totdat de controle is afgerond. Vastgelegd worden: oorspronkelijke vindplaats, maker, licentie, opnamedatum, gemeente, onderwerp, wijzigingen en controles. Bij herkenbare personen of kunstwerken volgt een aanvullende beoordeling.</p></section>'
 body+='<style>.research-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin:28px 0}.research-metrics>div{background:#F5F1ED;padding:20px}.research-metrics strong{display:block;font-size:32px;color:#1050C2}.research-metrics span{font-size:14px}.research-findings{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}.research-findings article{border-top:1px solid #EDE8DF;padding-top:16px}.research-table{overflow:auto}.research-table table{width:100%;border-collapse:collapse;margin:20px 0}.research-table th,.research-table td{text-align:left;padding:12px;border-bottom:1px solid #EDE8DF}.research-source{padding:16px 0;border-bottom:1px solid #EDE8DF}.research-source summary{cursor:pointer;font-weight:700}.library-search{flex-wrap:wrap}.library-search select{min-height:44px;max-width:100%;padding:8px;border:1px solid #EDE8DF}</style>'
 return news.layout('Archiefonderzoek en beeldbankuitbreiding',body,'/nieuws/redactie/beeldonderzoek')
