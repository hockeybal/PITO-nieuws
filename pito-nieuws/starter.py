"""Selected concept: Dit is jouw Utrecht. Uses existing PITO drone preview frames."""
import news,media_library,re
def _render(items,m=""):
 city=next((x["name"] for x in news.read("municipalities") if x["slug"]==m),"Utrecht")
 media=news.read("municipality-images").get(m)
 # Decorative locality banners may use dated city photographs, not event evidence.
 excluded=bool(media and (not media.get('webApproved',True) or media.get('kind')=='generated'))
 image=media["file"] if media else "hero-amersfoort.png"
 credit=media["credit"] if media else ("Nog geen lokaal luchtbeeld · provinciebeeld: Amersfoort" if m else "PITO · AI-bewerkt dronebeeld")
 position=(media or {}).get('positionDesktop','center 54%')
 mobile_position=(media or {}).get('positionMobile',position)
 credit_html=('<span>'+news.e(credit)+'</span> · ' if m and not media else '')+'<a href="/nieuws/beeldverantwoording">Beeldverantwoording</a>' 
 if media and media.get('sourceUrl'):
  credit_html='<a href="'+news.e(media['sourceUrl'])+'">'+news.e(media.get('author',credit))+'</a> · <a href="'+news.e(media['licenseUrl'])+'">Licentie</a> · uitsnede'
 options='<option value="">Heel Utrecht</option>'+''.join('<option value="'+x['slug']+'" '+('selected' if x['slug']==m else '')+'>'+news.e(x['name'])+'</option>' for x in news.read('municipalities'))
 if not m:
  return '<section class="province-opening" aria-label="Dit is jouw Utrecht"><div class="province-opening-photo" role="img" aria-label="Utrecht vanuit de Dom"></div><svg class="province-opening-route" viewBox="0 0 1280 300" preserveAspectRatio="none" aria-hidden="true"><path d="M480 320 C550 230 635 290 710 210 S835 80 1005 120 S1190 80 1320 15"/><circle cx="710" cy="210" r="5"/><circle cx="1005" cy="120" r="5"/></svg><div class="province-opening-copy"><p class="eyebrow">DICHTBIJ BEGINT HIER</p><h1>Dit is jouw<br>Utrecht<span>.</span></h1><p>Groot nieuws. Dicht bij huis.</p><form action="/nieuws/kies" class="province-opening-select"><label class="sr-only" for="starter-gemeente">Kies jouw gemeente</label><select id="starter-gemeente" name="gemeente">'+options+'</select><button type="submit">Ontdek</button></form></div><a class="province-opening-credit" href="/nieuws/beeldverantwoording">Beeldverantwoording</a></section>'
 tiles=''.join('<button type="button" class="drone-tile" data-frame="'+str(n)+'" data-image="hero-'+{10:"amersfoort",15:"rhenen",7:"vinkeveen"}[n]+'.png" data-place="'+name+'" aria-pressed="'+str(n==10).lower()+'"><span class="drone-thumb frame-'+str(n)+'"></span><span><strong>'+name+'</strong><small>'+label+'</small></span></button>' for n,name,label in [(10,'Amersfoort','Koppelpoort'),(15,'Rhenen','Aan de Rijn'),(7,'Vinkeveen','Aan het water')])
 teasers=''.join('<a href="'+news.url(a)+'"><small>'+news.e(news.CATEGORIES[a['category']])+'</small><h2>'+news.e(a['title'])+'</h2><span>Lees het bericht</span></a>' for a in items[:2])
 html='<section class="utrecht-starter '+('long-city' if len(city)>13 else '')+(' local-photo' if media and media['file'].startswith('municipality-') else '')+'" aria-label="Dit is jouw Utrecht"><div class="drone-backdrop" style="background-image:url(/news-static/images/'+image+');--hero-position:'+news.e(position)+';--hero-position-mobile:'+news.e(mobile_position)+'" role="img" aria-label="'+news.e((media or {}).get('alt',(city if media else 'Amersfoort')+' vanuit de lucht'))+'"></div><div class="starter-shade"></div><div class="starter-copy"><p class="eyebrow">UTRECHT IN BEWEGING</p><h1>Dit is jouw<br>'+news.e(city)+'<span>.</span></h1><p class="starter-subtitle">Het nieuws. De mensen. Jouw omgeving.</p><form action="/nieuws/kies" class="starter-select"><button type="submit">Bekijk gemeente</button><label class="sr-only" for="starter-gemeente">Jouw gemeente</label><select id="starter-gemeente" name="gemeente">'+options+'</select></form><a class="starter-jump" href="#nieuwsoverzicht">Direct naar het nieuws</a></div><div class="starter-bottom"><p class="drone-location">'+news.e(city if media else 'Amersfoort · Koppelpoort')+'</p><div class="drone-tiles">'+(tiles if not m else '')+'</div><small class="drone-credit">'+credit_html+'</small></div></section>'
 if excluded:
  start=html.index('<div class="drone-backdrop"');end=html.index('<div class="starter-shade">',start)
  html=html[:start]+'<div class="municipality-image-pending" aria-hidden="true"></div>'+html[end:]
  start=html.index('<small class="drone-credit">');end=html.index('</small>',start)+len('</small>')
  html=html[:start]+'<small class="drone-credit"></small>'+html[end:]
  html=html.replace(' local-photo',' image-pending')
 return html


def render(items,m="",view="nieuws",day="vandaag",filters=None):
 html=_render(items,m)
 if filters and view != "nieuws":
  fields=''.join('<input type="hidden" name="'+news.e(k)+'" value="'+news.e(v)+'">' for k,v in filters.items())
  html=html.replace('<select id="starter-gemeente"',fields+'<select id="starter-gemeente"',1)
 if view!='nieuws':
  hidden='<input type="hidden" name="weergave" value="'+news.e(view)+'"><input type="hidden" name="dag" value="'+news.e(day)+'">'
  html=html.replace('<form action="/nieuws/kies"', '<form action="/nieuws/kies"',1)
  html=html.replace('<select id="starter-gemeente"',hidden+'<select id="starter-gemeente"',1)
  html=html.replace('<h1>','<h2 class="opening-title">').replace('</h1>','</h2>')
  html=html.replace('Het nieuws. De mensen. Jouw omgeving.','Ontdek, ontmoet en doe mee.' if view!='community' else 'De mensen. De verhalen. Jouw buurt.')
  html=html.replace('Groot nieuws. Dicht bij huis.','Alles te beleven. Dicht bij huis.' if view!='community' else 'De verhalen uit jouw buurt.')
  html=html.replace('#nieuwsoverzicht','#lokaaloverzicht').replace('Direct naar het nieuws','Bekijk de agenda' if view!='community' else 'Bekijk de verhalen')
 # Keep the editorial location separate from the municipality action.
 place=next((x['name'] for x in news.read('municipalities') if x['slug']==m),'Provincie Utrecht')
 heading={'adressen':'Handig in ', 'nieuws':'Nieuws uit ','omgeving':'Omgevingszaken in ','vandaag':'Vandaag te doen in ','agenda':'Agenda van ','community':'Verhalen uit '}.get(view,'Ontdek ')+place
 html=re.sub(r'(<h[12](?: class="opening-title")?>).*?(</h[12]>)',lambda match:match.group(1)+'<span class=edition-kicker>'+news.e(heading[:-len(place)].strip())+'</span><span class=edition-name>'+news.e(place)+'</span>'+match.group(2),html,count=1,flags=re.S)
 html=html.replace('UTRECHT IN BEWEGING','ONTDEK JE BUURT').replace('DICHTBIJ BEGINT HIER','ONTDEK JE BUURT')
 # Native details keeps the location chooser keyboard-accessible without a custom widget.
 current=next((x['name'] for x in news.read('municipalities') if x['slug']==m),'Provincie Utrecht · alle gemeenten')
 choices=[{'slug':'','name':'Hele provincie Utrecht'}]+news.read('municipalities')
 menu='<p class="municipality-invite">Jouw lokale editie</p><details class="municipality-picker"><summary aria-label="Kies jouw gemeente"><span class="municipality-cta">Kies jouw gemeente <b aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg></b></span></summary><div class="municipality-options"><div class="municipality-panel-head"><div><strong>Kies jouw gemeente</strong><p>Het nieuws en de activiteiten dichtbij.</p></div><button type="button" class="municipality-close" aria-label="Sluit gemeentekeuze">×</button></div><input type="search" class="municipality-search" placeholder="Zoek jouw gemeente…" aria-label="Zoek jouw gemeente" autocomplete="off"><button type="button" class="municipality-locate" data-location-open><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4"/></svg><span>Gebruik mijn locatie</span></button><div class="municipality-grid">'+''.join('<button type="submit" name="gemeente" value="'+x['slug']+'" '+('aria-current="true"' if x['slug']==m else '')+'>'+news.e(x['name'])+'<span aria-hidden="true">'+('✓' if x['slug']==m else '→')+'</span></button>' for x in choices)+'</div><p class="municipality-empty" hidden>Geen gemeente gevonden. Probeer een andere naam.</p></div></details>'
 html=re.sub(r'<select id="starter-gemeente".*?</select>',menu,html,flags=re.S)
 html=re.sub(r'<button type="submit">(?:Ontdek|Bekijk gemeente)</button>','',html)
 html=re.sub(r'<a class="province-opening-credit"[^>]*>Beeldverantwoording</a>','',html)
 html=html.replace('<a href="/nieuws/beeldverantwoording">Beeldverantwoording</a>','')
 return html


def compact(m='',view='nieuws',day='vandaag',filters=None):
 html=render([],m,view,day,filters)
 html=html.replace('<h1>','<h2 class="opening-title">').replace('</h1>','</h2>')
 html=re.sub(r'<a class="starter-jump".*?</a>','',html)
 return '<div class="edition-continuity">'+html+'</div>'
