"""Municipality-specific routes to maintained official service information."""
import json
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).parent

def records():return json.loads((ROOT/'data/local-addresses.json').read_text())
def path(m=''):return '/nieuws/nuttige-adressen'+('?'+urlencode({'gemeente':m}) if m else '')
def block(m=''):
 import news
 return '<section class="useful-entry"><div><span>PITO · DICHTBIJ GEREGELD</span><h2>Nuttige adressen</h2><p>Afval ophalen, je gemeente bellen of hulp dichtbij vinden. Alles handig bij elkaar.</p></div><a href="'+path(m)+'">Bekijk nuttige adressen <span aria-hidden="true">→</span></a></section>'
def page(m=''):
 import news,starter,community
 rows=records();local=next((x for x in rows if x['municipality']==m),None)
 if m and not local:return None
 title='Nuttige adressen'+(' in '+local['name'] if local else ' in jouw gemeente')
 body=starter.compact(m,'adressen')+community.tabs(m,'adressen')+'<article class="useful-directory"><header><p class="eyebrow">PITO · DICHTBIJ GEREGELD</p><h1>'+news.e(title)+'</h1><p>Waar kun je terecht? Vind de juiste organisatie en actuele informatie bij de bron.</p></header>'
 body+='<aside class="useful-emergency"><strong>Direct gevaar of een levensbedreigende situatie?</strong><a href="tel:112">Bel 112</a><a href="https://www.rijksoverheid.nl/documenten/vraag-en-antwoord/alarmnummer-112/wanneer-112-bellen">Wanneer bel je 112?</a></aside>'
 if local:
  facts=json.loads((ROOT/'data/local-service-facts.json').read_text())[m]
  body+=local_information(local,facts)
 else:
  body+='<section class="useful-start"><h2>Wat wil je regelen in jouw gemeente?</h2><p>Kies bovenaan je gemeente. Je ziet dan direct wie het afval ophaalt, hoe je grofvuil regelt en hoe je de gemeente bereikt.</p><div><span>Afval & ophalen</span><span>Gemeente & contact</span><span>Hulp dichtbij</span></div></section>'
 shared=[('Wijkagent & politie','Zoek jouw wijkagent op plaatsnaam of postcode. Geen spoed, wel politie: 0900-8844.','https://www.politie.nl/mijn-buurt/','Zoek jouw wijkagent'),('Brandweer','Geen spoed, maar wel brandweer ter plaatse nodig? Bel 0900-0904. Bij brand of acuut gevaar: 112.','https://www.brandweer.nl/onderwerpen/geenspoed/','Bekijk de uitleg van de brandweer'),('Huisarts & huisartsenpost','Bekijk bij je eigen huisarts welke huisartsenpost voor jou geldt. Bel eerst voordat je naar een spoedpost gaat.','https://www.thuisarts.nl/spoed-wie-bel-je','Welke zorg bel je bij spoed?'),('Een huisarts vinden','Zoek een praktijk in je omgeving. Controleer bij de praktijk zelf of je je kunt inschrijven.','https://www.zorgkaartnederland.nl/huisarts','Zoek een huisarts'),('Veiligheid & noodsituaties','Voorbereiding en veiligheidsinformatie van Veiligheidsregio Utrecht, voor alle 26 gemeenten.','https://vru.nl/jouw-veiligheid/','Bekijk veiligheidsinformatie')]
 body+='<h2>Hulp en voorzieningen</h2><div class="useful-grid">'+''.join(card(*c) for c in shared)+'</div><p class="useful-source-note">Informatie gecontroleerd op 14 oktober 2026. Bekijk bij de organisatie de actuele openingstijden en eventuele wijzigingen.</p></article>'
 return news.layout(title,body,path(m),'Afval ophalen, grofvuil, gemeentecontact en hulp dichtbij'+(' in '+local['name'] if local else ' in de provincie Utrecht')+'.')
def card(title,desc,url,cta):
 import news
 return '<section class="useful-card"><h3>'+news.e(title)+'</h3><p>'+news.e(desc)+'</p><a href="'+news.e(url)+'">'+news.e(cta)+' <span aria-hidden="true">↗</span></a></section>'

def local_information(local,f):
 import news,re
 e=news.e
 phone=f['phone'];tel=re.sub(r'[^0-9+]','',phone)
 waste='<section class="service-feature service-waste" id="afval"><header><span class="service-number">01</span><div><p>JE BUURT NETJES</p><h2>Afval & ophalen</h2></div></header><div class="service-body"><h3>'+e(f['wasteLabel'])+'</h3>'+''.join('<p>'+e(p)+'</p>' for p in f['wasteFacts'])
 if f.get('calendarUrl'):
  waste+='<div class="service-calendar"><strong>Wanneer is jouw straat aan de beurt?</strong><p>Je ophaaldagen verschillen per adres. Houd je postcode en huisnummer bij de hand.</p><a href="'+e(f['calendarUrl'])+'">Bekijk jouw afvalkalender →</a></div>'
 waste+='<a class="service-source" href="'+e(f['wasteSource'])+'">Afvalinformatie van de gemeente ↗</a></div></section>'
 contact='<section class="service-feature service-contact" id="gemeente"><header><span class="service-number">02</span><div><p>DICHTBIJ GEREGELD</p><h2>Gemeente '+e(local['name'])+'</h2></div></header><div class="service-body"><span class="service-label">Bel de gemeente</span><a class="service-phone" href="tel:'+tel+'">'+e(phone)+'</a>'
 if f.get('address'):contact+='<h3>Hier kun je terecht</h3><p>'+e(f['address'])+'</p>'
 contact+='<p>Controleer vóór je bezoek of je een afspraak nodig hebt en wanneer de balie open is.</p><a class="service-source" href="'+e(f['contactSource'])+'">Contact & openingstijden ↗</a>'
 report=local['services']['report']
 if report.get('status')=='verified':contact+='<div class="service-report"><h3>Iets kapot of overlast in de buurt?</h3><p>Geef bijvoorbeeld een losse stoeptegel, kapotte verlichting of afval op straat door.</p><a href="'+e(report['url'])+'">Meld het bij de gemeente →</a></div>'
 contact+='</div></section>'
 return '<div class="service-local">'+waste+contact+'</div>'
