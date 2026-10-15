"""Woerden pilot: sourced project context; no scraped property inventory."""
import datetime
import news, community, starter, promotions
PATH='/nieuws/utrecht/woerden/wonen'
SOURCES=[
 ('Politiek & begroting','Gemeenteraad Woerden','https://gemeenteraad.woerden.nl/','Besluiten, vergaderstukken en inspraak'),
 ('Bouwen & vergunningen','Gemeente Woerden','https://www.woerden.nl/Gemeente/Bekendmakingen','Publicaties en termijnen per locatie'),
 ('Nieuwe buurten','Gemeentelijke projecten','https://www.woerden.nl/Stadsontwikkeling/Nieuwbouwprojecten','Ook ontwikkelingen in Harmelen, Kamerik en Zegveld'),
 ('Meedenken','Denk mee Woerden','https://www.woerden.nl/Denk_mee','Participatie en plannen in voorbereiding'),
 ('Cultuur & uitgaan','Cultuuragenda Woerden','https://www.cultuuragendawoerden.nl/agenda','Activiteiten bij de organisator controleren'),
 ('Wonen & zorg','Cazas Wonen','https://cazaswonen.nl/over-ons/actueel/laatste-nieuws/','Huurwoningen, renovatie en buurtvoorzieningen')]
OFFERS=[('Funda','https://www.funda.nl/zoeken/koop?construction_type=newly_built&object_type=house&selected_area=gemeente-woerden&type=group','Nieuwbouw in de gemeente'),('Woerden Makelaardij','https://www.woerdenmakelaardij.nl/','Aanbod bij de makelaar'),('Linda Makelaardij','https://www.lindamakelaardij.nl/','Aanbod bij de makelaar'),('De Koning Nieuwbouw','https://www.dekoningnieuwbouw.nl/','Projecten in de regio')]
def deadline_label(p,today=None):
 if not p.get('deadline'):return 'Geen actuele inschrijfdeadline vastgesteld'
 today=today or news.ranking.today()
 return ('Inschrijfronde gesloten · ' if datetime.date.fromisoformat(p['deadline'])<today else 'Inschrijven tot · ')+news.date(p['deadline'])
def property_cards(m=''):
 items=[p for p in news.read('properties') if not m or p['municipality']==m]
 if not items:return '<p class="coverage-note">Voor deze gemeente zijn nog geen individuele woningen gecontroleerd.</p>'
 out='<p class="coverage-note">Selectie gecontroleerd op 11 oktober 2026. Geen volledig of live aanbod. De eerste aanbiedingsdatum is niet vastgesteld; daarom noemen we deze woningen niet “nieuw”. Foto’s en actuele beschikbaarheid staan bij de makelaar.</p><div class="property-grid">'
 for p in items:
  out+='<article class="property-item"><p class="eyebrow">'+news.e(p['place'])+'</p><h3><a href="'+news.e(p['sourceUrl'])+'">'+news.e(p['address'])+'</a></h3><strong class="property-price">€ '+format(p['price'],',').replace(',','.')+' k.k.</strong><p>'+str(p['area'])+' m² · '+str(p['rooms'])+' kamers'+(' · '+news.e(p['type']) if p.get('type') else '')+'</p><p>'+news.e(p['sourceName'])+'</p><a href="'+news.e(p['sourceUrl'])+'">Bekijk woning en foto’s ›</a><details><summary>Broncontrole</summary><p>'+news.e(p['evidence'])+' · '+news.date(p['checkedAt'])+'</p></details></article>'
 return out+'</div>'
def project_image(project,library):
 import media_library
 media=media_library.media_for(project,library)
 if not media:return ''
 return '<figure class="housing-project-image"><a href="'+news.e(project['sourceUrl'])+'" tabindex="-1" aria-hidden="true"><img src="/news-static/images/'+news.e(media['file'])+'" alt="'+news.e(media['alt'])+'" loading="lazy" width="800" height="500"></a><figcaption>Illustratie · PITO · <a href="/nieuws/beeldbibliotheek">Beeldverantwoording</a></figcaption></figure>'

def page(m=''):
 import media_library,seo
 e=news.e;city=community.name(m) if m else 'provincie Utrecht';path=news.BASE+('/'+m if m else '')+'/wonen'
 items=sorted([a for a in news.articles() if news.selected(a,m) and a['category']=='Wonen'],key=lambda a:a['sourcePublishedAt'],reverse=True)
 projects=[p for p in news.read('housing-projects') if not m or p['municipality']==m]
 topics={'plan':['woningbouw','ruimtelijk-plan'],'snellerpoort':['wonen','woningbouw'],'molenvliet':['participatie','ruimtelijk-plan'],'zegveld':['zorg','wonen']}
 library={k:v for k,v in news.read('images').items() if k!='stock-20261010-wonen-2'}
 all_media=media_library.assign(items[:12]+[dict(p,slug='project-'+p['id'],imageTopics=topics.get(p['id'],['wonen','ruimtelijk-plan'])) for p in projects],library)
 assigned=all_media[:len(items[:12])]
 projects=all_media[len(items[:12]):]
 lead=('<div class="stories">'+news.card(assigned[0],True)+'<div class="secondary">'+''.join(news.card(a) for a in assigned[1:3])+'</div></div>') if assigned else '<p>Er zijn nog geen gecontroleerde woonberichten voor deze gemeente.</p>'
 more='<div class="editorial-cards">'+''.join(news.card(a) for a in assigned[3:])+'</div>' if len(assigned)>3 else ''
 project_html=''.join('<article class="project-brief">'+project_image(p,library)+'<p class="eyebrow">'+e(p['place'])+' · '+e(p['phase'])+'</p><h3>'+e(p['name'])+'</h3><p>'+e(p['summary'])+'</p><p>'+e(p['action'])+'</p><small>'+e(deadline_label(p))+'</small><p><a href="'+e(p['sourceUrl'])+'">'+e(p['sourceName'])+' ›</a></p></article>' for p in projects)
 if not project_html:project_html='<p>Nog geen afzonderlijke projectfasen en inschrijfdata gecontroleerd voor deze gemeente. De beschikbare woonberichten staan hierboven.</p>'
 hero=starter.render([],m,'wonen').replace('Bekijk de agenda','Bekijk het woonnieuws').replace('Ontdek, ontmoet en doe mee.','Het woonnieuws uit jouw omgeving.')
 if 'municipality-image-pending' in hero:
  hero=hero.replace('<div class="municipality-image-pending" aria-hidden="true"></div>','<div class="drone-backdrop housing-opening-image" style="background-image:url(/news-static/images/stock-20261010-wonen-2.png)" role="img" aria-label="Illustratief beeld van wonen; geen locatiebeeld van '+e(city)+'"></div>').replace('Nieuw gemeentebeeld volgt','Illustratie · PITO').replace(' image-pending','')
 nav='<nav class="housing-subnav" aria-label="Woonrubrieken"><a href="#lokaaloverzicht">Woonnieuws</a><a href="#te-koop">Te koop</a><a href="#nieuwbouw">Nieuwbouw & inschrijven</a><a href="#bouwplannen">Bouwplannen</a><a href="#omgeving">Omgeving & meedenken</a></nav>'
 heading='<header class="section-title" id="lokaaloverzicht"><h1>Wonen & bouwen in '+e(city)+'</h1></header>'
 sections='<section id="te-koop" class="section"><div class="section-title"><h2>Te koop in '+e(city)+'</h2></div>'+property_cards(m)+'</section>'
 sections+='<section id="nieuwbouw" class="section"><div class="section-title"><h2>Nieuwbouw & inschrijven</h2></div><div class="project-briefs">'+project_html+'</div></section>'
 sections+='<section id="bouwplannen" class="section"><div class="section-title"><h2>Bouwplannen in jouw buurt</h2><a href="'+seo.topic_path(m,'Wonen')+'">Alle woonberichten ›</a></div>'+(more or '<p>Alle gecontroleerde woonberichten uit deze gemeente staan bovenaan deze pagina.</p>')+'</section>'
 sections+='<section id="omgeving" class="section"><div class="section-title"><h2>Omgeving & meedenken</h2></div><p>Besluitvorming, openbare ruimte en plannen voor de buurt.</p><a href="'+seo.topic_path(m,'Bestuur')+'">Politiek & bestuur in '+e(city)+' ›</a>'
 if m=='woerden' or not m:sections+='<div class="housing-links">'+''.join('<a class="housing-source" href="'+e(u)+'"><small>'+e(t)+'</small><strong>'+e(n)+'</strong><span>'+e(d)+' ›</span></a>' for t,n,u,d in SOURCES[:4])+'</div>'
 sections+='</section>'
 body=hero+community.tabs(m,'wonen')+nav+heading+'<div class="housing-layout"><div>'+lead+sections+'</div><aside>'+promotions.ad('rail','plek')+'<section class="housing-note"><h2>Meer uit '+e(city)+'</h2><a href="'+news.BASE+('/'+m if m else '')+'">Alle nieuws ›</a><p><a href="'+seo.agenda_path(m)+'">Gemeenteagenda ›</a></p></section></aside></div>'
 return news.layout('Wonen & bouwen in '+city,body,path,'Woonnieuws, bouwplannen, nieuwbouw en gecontroleerde woningverwijzingen in '+city+'.',seo.graph_for_collection('Wonen & bouwen in '+city,path,items[:12],m))
