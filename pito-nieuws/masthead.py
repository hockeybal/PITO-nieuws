"""Compact shared news masthead with contextual search."""
from html import escape

def render(path):
 import news
 municipalities={m['slug'] for m in news.read('municipalities')}
 parts=path.split('?')[0].strip('/').split('/')
 m=next((p for p in parts[2:] if p in municipalities),'')
 if parts==['nieuws','nuttige-adressen']:
  from urllib.parse import urlsplit,parse_qs
  candidate=parse_qs(urlsplit(path).query).get('gemeente',[''])[0]
  if candidate in municipalities:m=candidate
 if 'artikel' in parts:
  a=next((a for a in news.articles() if a['slug']==parts[-1]),{})
  if not a.get('provinceWide') and len(a.get('municipalities',[]))==1:m=a['municipalities'][0]
 action=news.BASE+('/'+m if m else '')
 return '''<header class="news-brandbar"><div class="news-brandbar-inner news-masthead-v2"><a class="news-brand-home" href="/nieuws/utrecht" aria-label="PITO Nieuws — naar het overzicht"><img class="news-official-logo" src="/news-static/pito-nieuws-dichtbij.svg" alt="PITO — Nieuws dichtbij" width="145" height="50"></a><nav class="masthead-main-nav" aria-label="Hoofdnavigatie"><a href="/nieuws/utrecht" aria-current="page">Nieuws</a><a href="https://pito.app/" target="_blank" rel="noopener noreferrer" aria-label="PITO APP (opent in een nieuw tabblad)" title="Opent in een nieuw tabblad">PITO APP</a><a href="https://pito.app/#/collectieven" target="_blank" rel="noopener noreferrer" aria-label="Wijkcollectieven (opent in een nieuw tabblad)" title="Opent in een nieuw tabblad">Wijkcollectieven</a></nav><aside class="masthead-download" aria-label="Download PITO"><strong>Download PITO</strong><div class="header-store-badges"><a href="https://apps.apple.com/nl/app/pito-ontdek-je-buurt/id6762842018" aria-label="Download PITO in de App Store"><img src="/news-static/campaign/app-store-badge.png" alt="App Store"></a><a href="https://play.google.com/store/apps/details?id=pito.app" aria-label="Download PITO via Google Play"><img src="/news-static/campaign/google-play-badge-nl.png" alt="Google Play"></a></div></aside>'''+__import__('weather').header()+'''<details class="masthead-search"><summary aria-label="Zoek nieuws"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg></summary><form class="header-search-panel" role="search" action="'''+escape(action)+'''"><div class="header-search-heading"><label for="header-news-search">Zoeken in het nieuws'''+(' uit '+escape(m.replace('-',' ').title()) if m else '')+'''</label><button class="header-search-close" type="button" aria-label="Sluit zoeken">×</button></div><div class="header-search-field"><input id="header-news-search" name="q" type="search" placeholder="Zoek op onderwerp, plaats of trefwoord" autocomplete="off" required><input type="hidden" name="periode" value="archive"><button class="header-search-submit">Zoeken <span aria-hidden="true">→</span></button></div><p class="header-search-hint">Doorzoek nieuwsberichten, ook uit het archief.</p></form></details></div></header>'''
