"""Editorial dossiers group existing verified-source concepts, without inventing new reporting."""
import news,seo,editorial,community
from urllib.parse import urlencode
DOSSIERS={
 'wonen-en-bouwen':{'title':'Wonen & bouwen','intro':'Van een eerste plan tot een nieuwe woning: volg de besluiten, betaalbaarheid en voortgang van woningbouw in Utrecht.','terms':['woning','wonen','bouwstop','omgevingsplan','bestemmingsplan','vergunning','beekweide','klimrakker','de bleek','woonlast']},
 'wegen-en-openbaar-vervoer':{'title':'Onderweg in Utrecht','intro':'Werk aan wegen, treinverbindingen en buslijnen raakt je dagelijkse route. Hier staan de eerdere berichten en aangekondigde veranderingen bij elkaar.','terms':['a12','a27','a2-','n210','n233','n234','buslijn','spoor','trein','ov-','merwedelijn','onderdoorgang','wegwerk','tram','u-ov','doorfiets']},
 'energie-en-stroomnet':{'title':'Energie & het stroomnet','intro':'Netcapaciteit, windenergie en lokale energieplannen: wat wordt onderzocht, wat is besloten en wat betekent het voor inwoners?','terms':['stroom','energie','wind','netcongestie']},
 'gemeenteraad-en-begroting':{'title':'Besluiten die je raken','intro':'Geld voor voorzieningen, lokale woonlasten en plannen van het gemeentebestuur. Volg de afwegingen en blijf onderscheid maken tussen een voorstel en een vastgesteld besluit.','terms':['begroting','coalitie','wethouder','college','raads','woonlast','gemeenteraad']},
}
def items(key,m=''):
 d=DOSSIERS[key]
 return sorted([a for a in news.articles() if news.selected(a,m) and any(t in a['title'].lower() for t in d['terms'])],key=lambda a:a['sourcePublishedAt'],reverse=True)
def path(key=''):return '/nieuws/dossiers'+('/'+key if key else '')
def teaser(m=''):
 cards=''
 for key,d in DOSSIERS.items():
  rows=items(key,m)
  if not rows:continue
  photo='<span class="dossier-index" aria-hidden="true">0'+str(list(DOSSIERS).index(key)+1)+'</span>'
  cards+='<a href="'+path(key)+('?' +urlencode({'gemeente':m}) if m else '')+'">'+photo+'<div class="dossier-card-copy"><small>'+str(len(rows))+' berichten</small><h3>'+news.e(d['title'])+'</h3><span>Volg het verhaal ›</span></div></a>'
 return '<section id="achtergrond" class="dossier-band"><div class="section-title"><div><p class="eyebrow">DE ACHTERGROND BIJ HET NIEUWS</p><h2>Dit speelt er langer.</h2></div><a href="/nieuws/dossiers">Alle dossiers ›</a></div><div class="dossier-grid">'+cards+'</div></section>'
def page(key='',m=''):
 if not key:
  body=editorial.breadcrumb([('PITO','/'),('Nieuws',news.BASE),('Dossiers',path())])+'<section class="section"><p class="eyebrow">PITO DOSSIERS</p><h1>Het grotere verhaal.<br>Dicht bij jou.</h1><p class="standfirst">Nieuws stopt niet na één bericht. Volg onderwerpen door de tijd, met eerdere berichten en bronnen bij elkaar.</p></section>'+teaser(m)+editorial.city_links(m)
  return news.layout('Nieuwsdossiers provincie Utrecht',body,path(),'Volg lokale dossiers over woningbouw, verkeer, energie en gemeentelijke besluiten in de provincie Utrecht.')
 d=DOSSIERS[key];rows=items(key,m);assigned=news.media_library.assign(rows)
 options='<option value="">Heel Utrecht</option>'+''.join('<option value="'+x['slug']+'" '+('selected' if m==x['slug'] else '')+'>'+news.e(x['name'])+'</option>' for x in news.read('municipalities'))
 body=editorial.breadcrumb([('PITO','/'),('Nieuws',news.BASE),('Dossiers',path()),(d['title'],path(key))])+'<section class="dossier-heading"><p class="eyebrow">DOSSIER · '+str(len(rows))+' BERICHTEN</p><h1>'+news.e(d['title'])+'</h1><p class="standfirst">'+news.e(d['intro'])+'</p><form><label for="dossier-city">Jouw gemeente</label><select id="dossier-city" name="gemeente">'+options+'</select><button>Toon berichten</button></form><p class="edition-count">Van nieuw naar oud. Brondatums blijven zichtbaar; oudere berichten beschrijven niet noodzakelijk de huidige situatie.</p></section><div class="dossier-results more-grid">'+(''.join(news.card(a) for a in assigned) or '<div class="empty"><h2>Nog geen gecontroleerd bericht in deze gemeente.</h2><a href="'+path(key)+'">Bekijk dit dossier in heel Utrecht</a></div>')+'</div>'+editorial.city_links(m)
 url=path(key)+('?' +urlencode({'gemeente':m}) if m else '')
 return news.layout(d['title']+' in '+editorial.city(m),body,url,d['intro'],seo.graph_for_collection(d['title'],url,rows,m))
