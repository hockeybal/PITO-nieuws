"""Local editorial coverage dashboard. Missing coverage is explicit, not zero news."""
import json,datetime
import news,seo,editorial

def optional(name,default):
 try:return news.read(name)
 except (FileNotFoundError,ValueError):return default

def page():
 rows=optional('municipal-source-discovery',[]);koop=optional('koop-report',{});feed=optional('intake-report',{});council=optional('council-report',{});ndw=optional('ndw-report',{})
 articles=news.articles();months=['2026-%02d'%i for i in range(4,11)];trs=[]
 for m in news.read('municipalities'):
  row=next((r for r in rows if r['municipality']==m['slug']),{})
  health=next(iter(row.get('openBesluitvorming',[])),{}).get('health',{})
  direct=[a for a in articles if m['slug'] in a.get('municipalities',[])]
  cells=''.join('<td><a href="'+news.BASE+'/'+m['slug']+'?periode=archive&amp;maand='+month+'">'+str(sum(a['sourcePublishedAt'].startswith(month) for a in direct))+'</a></td>' for month in months)
  council_url=row.get('councilFinalUrl') or row.get('homepage','#')
  state='Inname gemeld' if health.get('state')=='ok' else 'Directe raad nodig'
  trs.append('<tr><th scope="row"><a href="'+news.BASE+'/'+m['slug']+'">'+news.e(m['name'])+'</a></th>'+cells+'<td><a href="'+news.e(council_url)+'">'+state+'</a></td></tr>')
 stats=[('26','gemeentelijke websites onderzocht'),(str(sum(next(iter(r.get('openBesluitvorming',[])),{}).get('health',{}).get('state')=='ok' for r in rows)),'gemeenten met recente ORI-inname'),(str(len(optional('inbox',[]))),'RSS-signalen in de inbox'),(str(len(articles)),'zichtbare nieuwsconcepten')]
 stathtml='<div class="coverage-stats">'+''.join('<div><strong>'+n+'</strong><span>'+label+'</span></div>' for n,label in stats)+'</div>'
 feedhtml=''.join('<tr><td>'+news.e(s['source'])+'</td><td>'+news.e(s['status'])+'</td><td>'+str(s.get('receivedInWindow','—'))+'</td><td><a href="'+news.e(s['url'])+'">Feed bekijken</a></td></tr>' for s in feed.get('sources',[]))
 familyhtml=''.join('<article class="sourceitem"><span class="eyebrow">'+news.e(s['priority'])+' · '+news.e(s['state'])+'</span><h3>'+news.e(s['name'])+'</h3><p>'+news.e(s['purpose'])+'</p><p>'+news.e(s['next'])+'</p><a href="'+news.e(s['url'])+'">Bron en documentatie</a></article>' for s in optional('source-families',[]))
 body=editorial.breadcrumb([('PITO','/'),('Redactie','/nieuws/redactie'),('Dekking','/nieuws/redactie/overzicht')])+'<section class="section coverage"><p class="eyebrow">LOKALE REDACTIEWERKPLAATS</p><h1>Weten wat we missen.</h1><p class="standfirst">Bronnen, gemeentelijke dekking en archiefopbouw op één plek. Laatste inventarisatie: 10 oktober 2026.</p>'+stathtml+'<p class="notice">Dit is een momentopname, geen continue bewaking. Een succesvolle inname bewijst niet dat alle documenten aanwezig zijn. Signalen zijn geen gepubliceerde artikelen. Het zesmaandenarchief is nog onvolledig.</p><h2>Nieuws per gemeente en maand</h2><p>Alleen berichten die rechtstreeks aan de gemeente zijn gekoppeld. Provinciebrede berichten zijn niet 26 keer meegeteld. April begint op 10 april; oktober loopt tot 10 oktober.</p><div class="table-scroll"><table><thead><tr><th>Gemeente</th>'+''.join('<th>'+m+'</th>' for m in ['Apr','Mei','Jun','Jul','Aug','Sep','Okt'])+'<th>Raadsinformatie</th></tr></thead><tbody>'+''.join(trs)+'</tbody></table></div><h2>Werkende RSS-inname</h2><p>Uitvoering: '+news.e(feed.get('runAt','Nog niet uitgevoerd'))+'. Alleen titel, bronlink en datum komen in de inbox.</p><div class="table-scroll"><table><thead><tr><th>Bron</th><th>Resultaat</th><th>Signalen in periode</th><th>Controle</th></tr></thead><tbody>'+feedhtml+'</tbody></table></div><div class="editorial-principles"><section><h2>Raadsvergaderingen</h2><p>'+str(len(optional('council-inbox',[])))+' vergaderingen als onderzoekssignaal opgehaald. Maximaal 24 per aangesloten gemeente: een steekproef, geen volledig archief. Vergaderdatum en publicatiedatum blijven gescheiden.</p></section><section><h2>Verkeer van NDW</h2><p>'+str(ndw.get('candidates',0))+' geografische kandidaten uit de DATEX II v3-momentopname. De ruime gebiedsselectie bevat ook aangrenzende regio’s. Wegvak, richting en lokale impact moeten worden bevestigd voordat een bericht ontstaat.</p><p>Er zijn geen automatische verkeerswaarschuwingen gepubliceerd.</p></section></div><h2>Officiële bekendmakingen</h2><p>Ook de KOOP-collectie officiële publicaties is aangesloten als beperkte onderzoeksteekproef. Kleine individuele vergunningen en parkeerbesluiten worden waar herkenbaar uitgefilterd; de redactie beoordeelt de resterende lokale betekenis.</p><p><a class="button" href="/nieuws/redactie/signalen?type=bekendmakingen">Bekijk de broninboxen</a></p><h2>De volgende bronnenlaag</h2><div class="source-grid">'+familyhtml+'</div><a class="button" href="/nieuws/redactie">Naar artikelcontrole</a></section>'
 return news.layout('Brondekking en archiefopbouw',body,'/nieuws/redactie/overzicht')
