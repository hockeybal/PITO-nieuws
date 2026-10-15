"""Server-rendered news extension for the existing PITO local preview."""
from pathlib import Path
from html import escape
from urllib.parse import urlencode
import json, datetime, os
import search_visibility
import app_content, ranking, media_library, seo, promotions, editorial, newsroom, local_features
from source_attribution import public_sources
ROOT=Path(__file__).parent
DATA=ROOT/'data'
BASE='/nieuws/utrecht'
CATEGORIES={'Bestuur':'Politiek & bestuur','Veiligheid':'Veiligheid','Verkeer':'Verkeer & OV','Wonen':'Wonen & omgeving','Samenleving':'Algemeen','Sport':'Sport'}
def read(name):return json.loads((DATA/(name+'.json')).read_text())
def e(s):return escape(str(s or ''),quote=True)
def url(a):return BASE+'/artikel/'+a['slug']+('?'+urlencode({'beeld':a['_displayImageKey']}) if a.get('_displayImageKey') else '')
def date(s):return datetime.date.fromisoformat(s[:10]).strftime('%d-%m-%Y') if s else 'Niet vermeld'
def selected(a,m):return not m or m in a.get('municipalities',[]) or a.get('provinceWide',False)
def articles():return [a for a in read('articles') if (not search_visibility.production() or search_visibility.published(a)) and a['reviewStatus'] in ('preview','approved') and a.get('sourceUrl','').startswith('https://') and a.get('sourcePublishedAt') and a.get('verifiedAt') and a.get('rights') and (a.get('municipalities') or a.get('provinceWide'))]
def layout(title,body,path=BASE,description='Het belangrijkste nieuws, activiteiten en kansen dichtbij. PITO Nieuws in de provincie Utrecht.',structured=None):
 path=search_visibility.canonical_path(path)
 canonical=seo.origin()+path
 robots=search_visibility.robots_meta(path)
 header=''
 footer=(ROOT/'static/news-footer.html').read_text()
 brand=read('news-brand-direction')
 import masthead as header_view
 masthead=header_view.render(path)
 campaign_shell = path.startswith(BASE) and not any(x in path for x in ('/redactie','/beeld'))
 if not structured:
  structured={'@context':'https://schema.org','@type':'WebPage','@id':canonical+'#page','url':canonical,'name':title,'description':description,'inLanguage':'nl-NL','isPartOf':{'@id':seo.origin()+'/#website'}}
 original_structured=structured
 social=seo.social_metadata(title,description,path,structured)
 structured=seo.metadata_graph(structured)
 ld='<script type="application/ld+json">'+json.dumps(structured,ensure_ascii=False).replace('<','\\u003c')+'</script>' if structured else ''
 return f'''<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" type="image/png" sizes="32x32" href="/news-static/pito-icon-32.png?v=1"><link rel="icon" type="image/svg+xml" href="/news-static/pito-icon.svg?v=1"><link rel="apple-touch-icon" sizes="180x180" href="/news-static/pito-icon-180.png?v=1"><meta name="apple-mobile-web-app-title" content="PITO Nieuws"><title>{e(title)} | PITO Nieuws</title><meta name="description" content="{e(description)}"><meta name="robots" content="{robots}"><link rel="canonical" href="{e(canonical)}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{e(canonical)}"><meta property="og:type" content="{'article' if original_structured and original_structured.get('@type')=='NewsArticle' else 'website'}">{social}<link rel="alternate" type="application/rss+xml" title="PITO Utrecht" href="/nieuws/feed.xml"><link rel="stylesheet" href="/style.css?v=7"><link rel="stylesheet" href="/news-static/news.css"><link rel="stylesheet" href="/news-static/environment.css"><link rel="stylesheet" href="/news-static/refresh.css"><link rel="stylesheet" href="/news-static/professional.css"><link rel="stylesheet" href="/news-static/newsroom-layout.css?v=1"><script defer src="/news-static/navigation.js"></script><script defer src="/news-static/news.js?v=6"></script><script defer src="/news-static/location.js?v=2"></script><link rel="stylesheet" href="/news-static/campaign.css?v=1"><link rel="stylesheet" href="/news-static/continuity.css?v=11"><link rel="stylesheet" href="/news-static/mobile.css?v=1"><link rel="stylesheet" href="/news-static/masthead.css?v=26"><link rel="stylesheet" href="/news-static/presentation.css?v=1"><script defer src="/news-static/masthead.js?v=4"></script><script defer src="/news-static/campaign.js?v=3"></script>{ld}</head><body class="news-site{' has-promotions' if campaign_shell else ''}"><a class="skip" href="#main">Naar de inhoud</a>{header}{masthead}{__import__("location_prompt").markup()}{promotions.wings() if campaign_shell else ""}<main id="main" class="pito-news">{body}</main>{footer}</body></html>'''
def selector(m,period='recent',month='',sort='relevance',q='',category='',view='nieuws',day='vandaag'):
 opts='<option value="">Heel Utrecht</option>'+''.join(f'<option value="{x["slug"]}" {"selected" if m==x["slug"] else ""}>{e(x["name"])}</option>' for x in read('municipalities'))
 hidden=''.join('<input type="hidden" name="'+k+'" value="'+e(v)+'">' for k,v in {'periode':period,'maand':month,'sortering':sort,'q':q,'onderwerp':category,'weergave':view,'dag':day}.items())
 return f'<form class="selector" action="/nieuws/kies">{hidden}<label for="municipality">Jouw gemeente</label><div><select id="municipality" name="gemeente">{opts}</select><button aria-label="Toon gemeente">Kies</button></div></form>'
def artwork(a,detail=False):
 media=media_library.media_for(a,read('images'))
 club=__import__('club_identity').for_article(a,media)
 if club:
  image='<img src="/news-static/images/'+e(club['file'])+'" alt="Logo van '+e(club['name'])+'" width="800" height="450" loading="lazy">'
  if not detail:image='<a href="'+url(a)+'" tabindex="-1" aria-hidden="true">'+image+'</a>'
  caption=('<figcaption>Clublogo · <a href="'+e(club['source'])+'">'+e(club['name'])+'</a></figcaption>') if detail else ''
  return '<figure class="news-visual club-identity'+(' club-identity-dark' if club.get('darkBackground') else '')+'"'+(' id="beeldcredit"' if detail else '')+'>'+image+caption+'</figure>'
 if media and media.get('kind')=='generated':
  image='<img src="/news-static/images/'+e(media['file'])+'" alt="'+e(media['alt'])+'" loading="lazy" width="800" height="400">'
  if not detail:image='<a href="'+url(a)+'" tabindex="-1" aria-hidden="true">'+image+'</a>'
  caption=media.get('displayCaption') or 'Illustratie · PITO'
  return '<figure class="news-visual">'+image+'<figcaption>'+e(caption)+' · <a href="/nieuws/beeldbibliotheek">Beeldverantwoording</a></figcaption></figure>'
 if media:
  src='/news-static/images/'+media['file'];alt=media['alt']
  caption=(e(a.get('imageContextLabel'))+' · ' if a.get('imageContextLabel') and media.get('file')==read('images').get(a.get('imageKey'),{}).get('file') else e(media.get('contextLabel','Foto ter illustratie'))+' · ')+'<a href="'+e(media['sourceUrl'])+'">'+e(media['author'])+'</a> · <a href="'+e(media['licenseUrl'])+'">'+e(media['license'])+'</a> · uitsnede'
 else:
  gallery=a.get('sourceImageGallery')
  cover='/news-static/editorial-covers/'+(a['slug'] if (ROOT/'static/editorial-covers'/(a['slug']+'.svg')).is_file() else 'default')+'.svg'
  img='<img src="'+e(cover)+'" alt="Redactionele PITO-cover: '+e(a['title'])+'" width="960" height="540" loading="lazy">'
  if not detail:img='<a href="'+url(a)+'" tabindex="-1" aria-hidden="true">'+img+'</a>'
  placeholder='<figure class="news-visual editorial-cover">'+img+'<figcaption>Redactioneel beeld · PITO</figcaption></figure>'
  return placeholder+('<p class=source-photo-link><a href="'+e(gallery)+'" target="_blank" rel="noopener">Bekijk de clubfoto’s bij Sportlust ’46 ›</a></p>' if detail and gallery else '')
 if not detail:caption='<a href="'+url(a)+'#beeldcredit">© '+e(media['author'])+' · '+e(media['license'])+'</a>'
 image='<img src="'+e(src)+'" alt="'+e(alt)+'" loading="lazy" width="800" height="400">'
 if not detail:image='<a href="'+url(a)+'" tabindex="-1" aria-hidden="true">'+image+'</a>'
 return '<figure class="news-visual"'+(' id="beeldcredit"' if detail else '')+'>'+image+'<figcaption>'+caption+'</figcaption></figure>'

def card(a,large=False):
 heading='h2' if large else 'h3'
 visual=artwork(a)
 return '<article class="story '+('lead' if large else '')+(' text-only' if not visual else '')+'">'+visual+'<div class="story-copy"><'+heading+'><a href="'+url(a)+'">'+e(a['title'])+'</a></'+heading+'></div></article>'
def listings(m):
 appitems,appstatus=app_content.get()
 appitems=[dict(a,url=seo.activity_path(a)) for a in appitems]
 data=[x for x in read('listings') if x['kind']!='activity']+appitems; chunks=[]
 for kind,title,id in [('activity','Er even op uit','activiteiten'),('job','Werk dichtbij','vacatures')]:
  items=[x for x in data if x['kind']==kind and (not m or x['municipality']==m) and x['date']>=seo.today().isoformat()][:6]
  if not items:continue
  cards=''.join(f'<article class="listing"><div class="eyebrow">{e(x["label"])}</div><h3>{e(x["title"])}</h3><p>{e(x["summary"])}</p><a href="{e(x["url"])}" target="_blank" rel="noopener noreferrer">Bekijk bij {e(x["sourceName"])}</a></article>' for x in items)
  chunks.append(f'<section class="section" id="{id}"><div class="section-title"><h2>{title}</h2><span>{"Uit de PITO-app" if kind=="activity" else "Vacatures · gecontroleerd op 10 oktober"}</span></div><div class="listing-grid">{cards or "<p class=empty>De agenda voor deze gemeente volgt binnenkort.</p>"}</div></section>')
 chunks.append('<section class="offers compact-offers"><div><div class="eyebrow">LOKALE ONDERNEMERS</div><h2>Mooi meegenomen.<br>Gewoon in je buurt.</h2><p>Het bestaande PITO-aanbod staat voor je klaar als ontwerp-preview. Actuele partneraanbiedingen moeten nog vanuit Strapi worden aangesloten.</p><a class="button" href="/#/aanbod">Bekijk de aanbod-preview</a></div><span aria-hidden="true">%</span></section>')
 return ''.join(chunks)
def home(m='',q='',category='',period='all',month='',sort='relevance',page='1',view='nieuws',day='vandaag',route_path=None):
 import community, facts, archive_navigation, dossiers, local_services
 if view in ['vandaag','agenda','community']:return community.page(m,view,day)
 if (period=='archive' and not category) or q:
  import latest_news
  return latest_news.render(m,q,category,month,page,route_path)
 names={x['slug']:x['name'] for x in read('municipalities')}; name=names.get(m,'provincie Utrecht'); path=route_path or BASE+('/'+m if m else '')
 period=period if period in ['all','recent','archive'] else 'all'
 sort=sort if sort in ['relevance','impact','latest'] else 'relevance'
 months=['2026-%02d'%v for v in range(7,11)]
 month=month if month in months else ''
 allitems=[a for a in articles() if selected(a,m) and '2026-07-11'<=(a.get('sourcePublishedAt') or '')<=seo.today().isoformat() and (period!='recent' or ranking.is_recent(a)) and (not month or period!='archive' or a['sourcePublishedAt'].startswith(month))]
 items=[a for a in allitems if (not category or a['category']==category) and (not q or q.lower() in (a['title']+' '+a['summary']).lower())]
 items=sorted(items,key=(lambda a:a['sourcePublishedAt']) if sort=='latest' else (lambda a:(ranking.score(a),a['sourcePublishedAt'])),reverse=True) if period=='archive' else ranking.order(items,sort,diversify=not category)
 overview_items=items[:]
 if period in ('all','recent') and not q and not category:
  # The overview owns its card selection and assets; avoid building the legacy
  # archive/listing body which used to be discarded immediately afterwards.
  import frontpage
  overview_body,items=frontpage.overview(overview_items,m,'')
  body=community.tabs(m,category=category)+overview_body
  page=1
 else:
  total=len(items)
  pages=max(1,(total+11)//12)
  try:page=max(1,min(pages,int(page)))
  except (ValueError,TypeError):page=1
  items=items[(page-1)*12:page*12]
  fact=facts.pick(m) if period in ('all','recent') and not q and not category else None
  library=read('images')
  fact_image=library.get(fact.get('imageKey')) if fact else None
  news_library={k:v for k,v in library.items() if not fact_image or media_library.identity(v)!=media_library.identity(fact_image)}
  archive_items=archive_navigation.earlier(m,{a['slug'] for a in items}) if period in ('all','recent') and not q and not category else []
  assigned=media_library.assign(items+archive_items,news_library)
  archive_items=assigned[len(items):];items=assigned[:len(items)]
  archive_block=archive_navigation.block(archive_items,m)
  topic_block=(archive_navigation.topics(m)+archive_navigation.province_more(m)) if period in ('all','recent') and not q and not category else ''
  archive_rail=archive_navigation.rail(m,category)
  fact_block=facts.block(m) if fact else ''
  pagination='<nav class=archive-pages aria-label=Archiefpagina>'+''.join('<a '+('aria-current=page ' if n==page else '')+'href="'+path+'?'+urlencode({'periode':period,'maand':month,'sortering':sort,'q':q,'onderwerp':category,'pagina':n})+'">'+str(n)+'</a>' for n in range(1,pages+1))+'</nav>' if pages>1 else ''
  if pages>1 and page<pages:pagination+='<a class="button archive-next" href="'+path+'?'+urlencode({'periode':period,'maand':month,'sortering':sort,'q':q,'onderwerp':category,'pagina':page+1})+'">Oudere berichten bekijken ›</a>'
  cats=['Alles']+list(CATEGORIES)
  filters=''.join('<a class="chip '+('on' if category==c or (c=='Alles' and not category) else '')+'" '+('aria-current="page" ' if category==c or (c=='Alles' and not category) else '')+'href="'+(BASE+('/'+m if m else '') if c=='Alles' else seo.topic_path(m,c))+'">'+e(CATEGORIES.get(c,c))+'</a>' for c in cats)
  latest=sorted(allitems,key=lambda a:a.get('sourcePublishedAt') or a.get('eventDate') or '',reverse=True)[:4]
  timeline=''.join(f'<li><time>{date(a.get("sourcePublishedAt") or a.get("eventDate"))}</time><a href="{url(a)}">{e(a["title"])}</a></li>' for a in latest)
  stories=card(items[0],True)+('<div class="secondary">'+''.join(card(a) for a in items[1:4])+'</div>' if len(items)>1 else '') if items else '<div class="empty"><h2>Nog geen berichten voor deze selectie.</h2><p>We vullen deze editie pas aan als plaats, datum en bron zijn gecontroleerd.</p><a href="'+BASE+'">Bekijk het provinciale overzicht</a></div>'
  more=''
  if period=='archive' or sort in ['latest','relevance']:
   if items[4:]:more='<section class="section"><div class="section-title"><h2>Meer nieuws</h2></div><div class="more-grid">'+''.join(card(a) for a in items[4:])+'</div></section>'
  else:
   for c,label in CATEGORIES.items():
    group=[a for a in items[4:] if a['category']==c]
    if group:more+='<section class="section"><div class="section-title"><h2>'+e(label)+'</h2></div><div class="more-grid">'+''.join(card(a) for a in group)+'</div></section>'
  if period=='archive':
   stories=''.join(card(a) for a in items) or stories
   more=''
  month_options='<option value="">Alle maanden</option>'+''.join('<option value="'+v+'" '+('selected' if month==v else '')+'>'+n+'</option>' for v,n in zip(months,['Juli (vanaf 11 juli)','Augustus','September','Oktober (t/m 11 oktober)']))
  controls=f'<details class="news-filters"><summary>Filters & archief</summary><form class="archive-controls" action="{path}"><input type="hidden" name="q" value="{e(q)}"><input type="hidden" name="onderwerp" value="{e(category)}"><label>Periode<select name="periode"><option value="all" {"selected" if period=="all" else ""}>Afgelopen drie maanden</option><option value="recent" {"selected" if period=="recent" else ""}>Laatste twee weken</option><option value="archive" {"selected" if period=="archive" else ""}>Archief · drie maanden</option></select></label><label>Maand (archief)<select name="maand">{month_options}</select></label><label>Volgorde<select name="sortering"><option value="relevance" {"selected" if sort=="relevance" else ""}>Relevant voor inwoners</option><option value="impact" {"selected" if sort=="impact" else ""}>Redactionele impact</option><option value="latest" {"selected" if sort=="latest" else ""}>Nieuwste eerst</option></select></label><button>Toon nieuws</button><a href="/nieuws/selectie">Hoe selecteert PITO?</a></form></details>'
  body=f'''<div class="edition"><div><p class="eyebrow">PITO NIEUWS / {"GEMEENTE" if m else "PROVINCIE"}</p><h1>{e(name)}<span>.</span></h1><p>Belangrijke besluiten, veiligheid en bereikbaarheid dichtbij.</p></div>{selector(m,period,month,sort,q,category)}</div>{community.tabs(m,category=category)}<div class="filterbar"><nav aria-label="Onderwerpen">{filters}</nav><form class="search" action="{path}"><input type="hidden" name="onderwerp" value="{e(category)}"><input type="hidden" name="periode" value="archive"><input type="hidden" name="maand" value="{month}"><input type="hidden" name="sortering" value="{sort}"><input name="q" value="{e(q)}" placeholder="Zoek in het nieuws" aria-label="Zoek in het nieuws"><button aria-label="Zoeken">Zoek</button></form></div><div class="edition-tools">{controls}{editorial.heading(m,category,total,period,q)}</div><div class="frontpage {"frontpage-archive" if period=="archive" else ""}"><div class="front-opening"><div class="stories">{stories}</div><section class="front-latest"><h2>Laatste nieuws</h2><ol class="timeline">{timeline or '<li>De lokale redactie wordt opgebouwd.</li>'}</ol><a class="text-link" href="{path}?periode=archive&sortering=latest">Meer nieuws ›</a></section></div>{more}{fact_block}{pagination}{archive_block}</div>{local_features.block(m)}{local_services.strip()}{promotions.ad('wide','collectieven')}{archive_rail if period!='all' else ''}{dossiers.teaser(m) if period=="recent" and not q and not category else ""}{topic_block}{community.recruitment(m)}{listings(m)}<section class="municipalities"><h2>Jouw nieuws begint dichtbij.</h2><p>Van Amersfoort tot Zeist. Kies jouw gemeente.</p><div>{''.join(f'<a href="{archive_navigation.link(x["slug"]) if period=="archive" else BASE+chr(47)+x["slug"]}">{e(x["name"])}</a>' for x in read('municipalities'))}</div></section>'''
 
 if category and not q:
  import frontpage
  label=CATEGORIES.get(category,category)
  heading='<h1 class="sr-only">'+e(label)+' in '+e(name)+'</h1>'
  collection=frontpage.topic_section(items[:9],m,category,label,'selectie',show_heading=False) if items else '<p>Geen berichten in deze selectie.</p>'
  if category=='Sport':
   import club_directory
   collection+=club_directory.block(m)
  pagination=pagination[pagination.index('</nav>')+6:] if '</nav>' in pagination else pagination
  remaining='<div class="topic-archive-list">'+''.join(card(a) for a in items[9:])+'</div>' if len(items)>9 else ''
  body=community.tabs(m,category=category)+'<div class="frontpage editorial-overview filtered-overview">'+heading+collection+remaining+pagination+promotions.ad('leaderboard','aanbod')+'</div>'
 if not q:
  import starter
  body=starter.render(items,m,filters={'periode':period,'maand':month,'sortering':sort,'onderwerp':category})+ '<div id=nieuwsoverzicht>'+body[body.index(community.tabs(m,category=category)):]+'</div>'
 title=(CATEGORIES[category]+' in '+name if category in CATEGORIES else 'Nieuws uit '+name)
 if category and not q:
  body=body.replace('<h1>','<h2 class="opening-title">',1).replace('</h1>','</h2>',1)

 canonical=path
 params={}
 if period=='archive' and not route_path:params['periode']='archive'
 if month:params['maand']=month
 if page>1:params['pagina']=page
 if q:params['q']=q
 if sort!=('latest' if route_path else 'relevance'):params['sortering']=sort
 if category and not route_path:params['onderwerp']=category
 if params:canonical+='?'+urlencode(params)
 body=context_links(body,m)
 return layout(title,body,canonical,'Lokaal nieuws uit '+name+': politiek, veiligheid, verkeer en ontwikkelingen die inwoners raken.',seo.graph_for_collection(title,canonical,items,m))
def detail(a,municipality=""):
 import preferred_source
 structured={'@context':'https://schema.org','@type':'NewsArticle','headline':a['title'],'description':a['summary'],'author':{'@type':'Organization','name':'PITO onderzoeksredactie'},'citation':a['sourceUrl'],'isAccessibleForFree':True,'inLanguage':'nl'}
 structured['mainEntityOfPage']=seo.origin()+BASE+'/artikel/'+a['slug']
 structured['publisher']={'@id':seo.origin()+'/#newsroom'}
 structured['url']=seo.origin()+BASE+'/artikel/'+a['slug']
 structured['articleSection']=CATEGORIES.get(a['category'],a['category'])
 structured['author']['url']=seo.origin()+'/nieuws/over-de-redactie'
 if a.get('authorName'):structured['author']={'@type':'Person','name':a['authorName'],'url':seo.origin()+'/nieuws/over-de-redactie'}
 if a.get('publicationStatus')=='published' and a.get('webPublishedAt'):
  structured['datePublished']=a['webPublishedAt']
  if a.get('webModifiedAt'):structured['dateModified']=a['webModifiedAt']
 media=media_library.media_for(a,read('images'))
 if media:structured['image']=[seo.origin()+'/news-static/images/'+media['file']]
 # Source publication dates are never used as PITO publication dates.
 citations=public_sources(a)
 structured['citation']=[x['url'] for x in citations]
 extras=' · '.join('<a href="'+e(x['url'])+'" target="_blank" rel="noopener noreferrer">'+e(x['name'])+'</a>' for x in citations)
 body=f'''<div class="article-wrap"><p class="eyebrow">{e(CATEGORIES.get(a['category'],a['category']))} · {'Provincie Utrecht' if a.get('provinceWide') else ', '.join(e(x.replace('-',' ').title()) for x in a['municipalities'])}</p><h1>{e(a['title'])}</h1><div class="article-meta">PITO Nieuws · <time datetime="{e(a.get('sourcePublishedAt'))}">{date(a.get('sourcePublishedAt'))}</time></div><p class="standfirst">{e(a['summary'])}</p>{('<p class=notice><strong>Uit het archief</strong> · Dit bericht beschrijft de situatie op '+date(a.get('sourcePublishedAt'))+'. Controleer de bron voor de huidige stand.</p>') if not ranking.is_recent(a) else ''}{preferred_source.block()}{artwork(a,True)}<div class="article-body">{newsroom.article_body(a)}</div><div class="article-sources" aria-label="Bronvermelding"><span>{'Bron' if len(citations)==1 else 'Bronnen'}:</span> {extras}</div>{promotions.article_app_banner()}{editorial.share_tools(a)}<a class="button" href="{BASE}">Terug naar het overzicht</a></div>'''
 local_links=''.join('<a href="'+BASE+'/'+m+'">Nieuws uit '+e(next((x['name'] for x in read('municipalities') if x['slug']==m),m))+'</a> · <a href="'+seo.agenda_path(m)+'">Lokale agenda</a><br>' for m in a.get('municipalities',[]))
 municipality=municipality if municipality in {x["slug"] for x in read("municipalities")} else ""
 navigation,sidebar=promotions.article_navigation(a,municipality)
 import starter,community
 m=municipality or (a.get('municipalities',[''])[0] if a.get('municipalities') and not a.get('provinceWide') else '')
 navigation=starter.compact(m)+community.tabs(m)
 body=body.replace('href="'+BASE+'">Terug naar het overzicht','href="'+BASE+('/'+m if m else '')+'">Terug naar '+e(community.name(m) if m else 'provincie Utrecht'))
 body='<div class=article-page>'+navigation+'<div class=article-layout>'+body+sidebar+'</div>'
 # Municipality navigation is carried by the contextual navigation and tags.
 import archive_navigation
 import preferred_source
 body+=newsroom.related(a)+editorial.trustbar()+'</div>'
 body=context_links(body,m)
 return layout(a['title'],body,BASE+'/artikel/'+a['slug'],a['summary'],structured)
def sources():
 cards=''.join(f'<article class="sourceitem"><span class="eyebrow">{e(s["kind"])}</span><h2><a href="{e(s["url"])}">{e(s["name"])}</a></h2><p>{e(s["status"])}</p><small>{"Alleen signalering; eerst controleren" if s["mode"]=="signal" else "Handmatige broncontrole"}</small></article>' for s in read('sources'))
 return layout('Bronnen en werkwijze','<section class="section"><p class="eyebrow">OPEN OVER ONZE REDACTIE</p><h1>Het begint bij de bron.</h1><p class="standfirst">Nieuws dat je kunt controleren. Met een link naar het origineel en duidelijkheid over wat we weten.</p><div class="notice">We selecteren belangrijke lokale en provinciale besluiten, veiligheid en bereikbaarheid. Buitenlands nieuws, berichten zonder aantoonbaar Utrechts belang en kleine meldingen krijgen geen plaats in de hoofdeditie. Een raadsagenda is geen vastgesteld besluit.</div><div class="principles"><p><b>1. Signaleren</b><br>Feeds en regionale media brengen onderwerpen in beeld.</p><p><b>2. Controleren</b><br>Datum, plaats en feiten bij de oorspronkelijke bron nagaan.</p><p><b>3. Eigen tekst</b><br>Kort uitleggen wat een ontwikkeling voor inwoners betekent.</p><p><b>4. Eindredactie</b><br>Een mens beoordeelt de tekst vóór openbare publicatie.</p></div><div class="source-grid">'+cards+'</div><h2>Beeld en video</h2><p>Deze editie gebruikt herkenbaar aangeduide AI-sfeerbeelden en echte archieffoto’s met een gecontroleerde Creative Commons-licentie. De decoratieve openingsbeelden kunnen AI-bewerkingen van PITO-dronebeelden zijn. Maker en licentie staan bij de foto; op de artikelpagina staan ook de opnameperiode, bron en licentievoorwaarden. Een archieffoto toont niet het actuele nieuwsfeit. Waar passend beeld ontbreekt, tonen we het bericht zonder afbeelding. Foto’s van politie.nl nemen we niet over zonder afzonderlijke toestemming. Video’s worden niet gekopieerd. Voor toekomstige video’s gebruiken we een bronlink of, na controle van rechten en voorwaarden, een toegestane embed.</p></section>','/nieuws/bronnen')

def selection():
 import research
 return layout('Hoe we nieuws selecteren',research.selection(),'/nieuws/selectie')
def research_page():
 import research
 return layout('Onderzoek naar lokale informatiebehoeften',research.page(),'/nieuws/onderzoek')

def image_library(q='', municipality='', page='1'):
 library=read('images');q=q.strip().lower();seen=set();unique={}
 for k,v in library.items():
  identity=media_library.identity(v)
  if media_library.eligible(v) and identity not in seen:unique[k]=v;seen.add(identity)
 library=unique
 visible=[(k,v) for k,v in library.items() if (not municipality or municipality in v.get('municipalities',[])) and (not q or q in (' '.join(v.get('topics',[]))+' '+v.get('collection','')+' '+v.get('alt','')+' '+k).lower())]
 total=len(visible);pages=max(1,(total+35)//36)
 try:page=max(1,min(pages,int(page)))
 except (ValueError,TypeError):page=1
 visible=visible[(page-1)*36:page*36]
 options='<option value="">Alle gemeenten</option>'+''.join('<option value="'+e(m['slug'])+'" '+('selected' if municipality==m['slug'] else '')+'>'+e(m['name'])+'</option>' for m in read('municipalities'))
 pagination='<nav class="archive-rail" aria-label="Bladeren door beelden">'+''.join('<a '+('aria-current="page" ' if n==page else '')+'href="/nieuws/beeldbibliotheek?'+e(urlencode({'q':q,'gemeente':municipality,'pagina':n}))+'">'+str(n)+'</a>' for n in range(max(1,page-3),min(pages,page+3)+1))+'</nav>'
 cards=''
 for key,m in visible:
  if not media_library.eligible(m):continue
  credit=('PITO · AI-sfeerbeeld' if m.get('kind')=='generated' else '<a href="'+e(m['sourceUrl'])+'">'+e(m['author'])+'</a> · <a href="'+e(m['licenseUrl'])+'">'+e(m['license'])+'</a>')
  cards+='<article class="library-card"><img src="/news-static/images/'+e(m['file'])+'" alt="'+e(m['alt'])+'" loading="lazy"><div><p class="eyebrow">'+credit+'</p><h2>'+e(m.get('title',m['alt']))+'</h2><p>'+e(m.get('caption',m.get('alt','')))+'</p><small>'+e(' · '.join(m.get('topics',[]))+' · opname '+m.get('capturedAt',''))+'</small>'+('<details><summary>Bron en gebruik</summary><p>'+e(m['sourceTitle'])+'</p><p>'+e(m.get('changes',''))+'</p><p>Alleen gebruiken bij deze locatie en passende context.</p></details>' if m.get('sourceTitle') else '')+'</div></article>'
 collections='<nav class="archive-rail" aria-label="Beeldonderwerpen">'+''.join('<a href="/nieuws/beeldbibliotheek?q='+key+'">'+label+' ('+str(sum(v.get('collection')==key or key in v.get('collections',[]) for v in library.values()))+')</a>' for key,label in [('bestuur','Politiek & bestuur'),('veiligheid','Veiligheid'),('verkeer','Verkeer & OV'),('wonen','Wonen & omgeving'),('samenleving','Voorzieningen'),('sport','Sport'),('locaties','Gemeenten & locaties')])+'</nav>'
 body='<section class="section"><p class="eyebrow">PITO BEELDBIBLIOTHEEK</p><h1>Beeldbank voor lokaal nieuws.</h1><p class="standfirst">Echte foto’s vanaf 2022 met gecontroleerde bron, maker en licentie. Geselecteerd op onderwerp, zonder herhaling binnen één nieuwspagina.</p>'+collections+'<form class="search library-search"><input name="q" value="'+e(q)+'" aria-label="Zoek beelden" placeholder="Bijvoorbeeld bestuur, rechtspraak of verkeer"><select name="gemeente" aria-label="Gemeente">'+options+'</select><button>Zoek</button></form><p>'+str(total)+' van '+str(len(library))+' beelden · pagina '+str(page)+' van '+str(pages)+'</p><p><a href="/nieuws/redactie/beeldonderzoek">Bekijk het archiefonderzoek en de uitbreiding</a></p><div class="library-grid">'+(cards or '<p>Geen passend beeld gevonden.</p>')+'</div>'+pagination+'<div class="notice"><h2>Zo gebruiken we deze beelden</h2><p>Bronfoto’s worden pas gebruikt na rechten- en inhoudelijke controle. Herkenbare clubs, partijen en gebouwen mogen niet voor andere organisaties worden ingezet. Archiefbeelden behouden hun plaats, datum, maker en licentie. Bij een tekort aan passende beelden blijft een bericht zonder beeld; een andere uitsnede telt niet als een nieuw beeld.</p><p>De selectie werkt in deze lokale nieuwswebsite. Aansluiting op de volledige PITO-app en Strapi volgt via dezelfde bibliotheek; die is nog niet live aangesloten.</p></div></section>'
 import media_coverage
 coverage=media_coverage.audit(articles(),library)
 gaps=''.join('<li>'+e(k)+' · '+str(v)+' berichten zonder passend beeld</li>' for k,v in list(coverage['missingTopics'].items())[:12])
 body+='<section class=section><h2>Nog aan te vullen</h2><p>'+str(coverage['articlesWithCandidate'])+' van '+str(coverage['articlesChecked'])+' berichten hebben nu een passende fotokandidaat. Dit is nog geen volledige beelddekking.</p><ul>'+gaps+'</ul><p>Prioriteit: lokale sportverenigingen en sportparken, raadzalen en politieke partijen, woningbouwprojecten en lokale geschiedenis.</p></section>'
 return layout('Beeldbibliotheek',body,'/nieuws/beeldbibliotheek')


def context_links(body,m):
 if not m:return body
 import re
 from urllib.parse import urlsplit,parse_qsl,urlencode
 def rewrite(match):
  value=match.group(1).replace('&amp;','&');u=urlsplit(value)
  query=dict(parse_qsl(u.query));query['gemeente']=m
  return 'href="'+e(u.path+'?'+urlencode(query))+'"'
 return re.sub(r'href="('+re.escape(BASE)+r'/artikel/[^" ]+)"',rewrite,body)
