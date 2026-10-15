"""Legacy municipality route and image provenance."""
import news,media_library

def render():
 import seo
 rows=news.read('municipalities')
 cards=''.join('<section class="sourceitem"><h2><a href="'+news.BASE+'/'+m['slug']+'">'+news.e(m['name'])+'</a></h2><p><a href="'+seo.agenda_path(m['slug'],'vandaag')+'">Vandaag te doen</a> · <a href="'+seo.agenda_path(m['slug'])+'">Agenda</a> · <a href="'+news.BASE+'/'+m['slug']+'/omgevingszaken">Omgevingszaken</a> · <a href="/nieuws/nuttige-adressen?gemeente='+m['slug']+'">Nuttige adressen</a></p></section>' for m in rows)
 return news.layout('Alle 26 gemeenten in Utrecht','<section class="section"><h1>Ontdek jouw gemeente</h1><p>Nieuws, activiteiten en praktische informatie dichtbij.</p><div class="source-grid">'+cards+'</div></section>','/nieuws/gemeenten','Bekijk lokaal nieuws, agenda en nuttige adressen voor alle 26 gemeenten in de provincie Utrecht.')

def credits():
 names={m['slug']:m['name'] for m in news.read('municipalities')}
 cards=''
 for slug,m in news.read('municipality-images').items():
  if not media_library.eligible(m):continue
  detail=news.e(m.get('note') or ('Decoratieve AI-bewerking van een PITO-dronepreview. Details kunnen afwijken van de werkelijke locatie; dit beeld documenteert geen nieuwsgebeurtenis.' if m['kind']=='generated' else ''))
  source=('<p><a href="'+news.e(m['sourceUrl'])+'">Origineel en maker</a> · <a href="'+news.e(m['licenseUrl'])+'">'+news.e(m['license'])+'</a> · '+news.e(m.get('date',''))+' · uitsnede in weergave</p>') if m.get('sourceUrl') else ''
  cards+='<article class="sourceitem"><img class="opening-credit-photo" src="/news-static/images/'+news.e(m['file'])+'" alt="'+news.e(names[slug])+'" loading="lazy"><h2>'+news.e(names[slug])+'</h2><p>'+news.e(m['credit'])+'</p><p>'+detail+'</p>'+source+'</article>'
 return news.layout('Beeldverantwoording openingsbeelden','<section class="section"><p class="eyebrow">PITO BEELDEN</p><h1>De beelden achter jouw omgeving.</h1><p class="standfirst">Onze openingsbeelden geven de pagina sfeer. Hier lees je welke beelden van PITO zijn, welke met AI zijn bewerkt en welke archieffoto’s onder licentie worden gebruikt.</p><p>De provinciale opening toont Amersfoort, Rhenen en Vinkeveen. Echte foto’s worden alleen getoond met een bevestigde opnamedatum vanaf 2022. Waar een passend recent gemeentebeeld ontbreekt, staat tijdelijk een grafische achtergrond.</p><div class="source-grid">'+cards+'</div><p>De achtergrond van het gemeenteoverzicht komt ongewijzigd uit de goedgekeurde PITO-consumentenflyer. Het is een decoratieve, bewerkte collage van Utrechtse plaatsen. De collage is een provinciaal sfeerbeeld, geen registratie van een nieuwsgebeurtenis.</p><a href="/nieuws/beeldbibliotheek">Beeldverantwoording bij de nieuwsartikelen</a></section>','/nieuws/beeldverantwoording')
