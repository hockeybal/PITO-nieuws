"""Canonical local content routes; public sitemap entries require explicit publication."""
import datetime, hashlib, os
from urllib.parse import quote
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

def today():
 override=os.environ.get('PITO_EDITION_DATE')
 return datetime.date.fromisoformat(override) if override else datetime.datetime.now(ZoneInfo('Europe/Amsterdam')).date()
def origin():return os.environ.get('PITO_PUBLIC_URL','http://127.0.0.1:4198').rstrip('/')
def agenda_path(m='',day=''):
 return '/agenda/utrecht'+('/'+m if m else '')+('/'+day if day in ('vandaag','morgen','dit-weekend','binnenkort','deze-week') else '')
def view_path(m='',view='nieuws',day='vandaag'):
 base='/nieuws/utrecht'+('/'+m if m else '')
 return agenda_path(m,day if view=='vandaag' else '') if view in ('agenda','vandaag') else base+('?weergave=community' if view=='community' else '')
def matches(a,day):
 d=datetime.date.fromisoformat(a['date']);now=today()
 if day=='vandaag':return d==now
 if day=='morgen':return d==now+datetime.timedelta(days=1)
 if day=='deze-week':return now<=d<=now+datetime.timedelta(days=6-now.weekday())
 if day=='dit-weekend':
  saturday=now+datetime.timedelta(days=(5-now.weekday()) if now.weekday()<6 else -1)
  return max(now,saturday)<=d<=saturday+datetime.timedelta(days=1)
 return d>=now
def activity_path(a):
 # Stable occurrence identity, independent of a later title edit.
 occurrence=a.get('occurrenceId') or (a['date']+'|'+a.get('occurrenceKey',''))
 key=hashlib.sha256((str(a.get('id') or a['url'])+'|'+occurrence).encode()).hexdigest()[:20]
 return '/activiteiten/'+key

def breadcrumbs(parts):
 return {'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[{'@type':'ListItem','position':i,'name':name,'item':origin()+path} for i,(name,path) in enumerate(parts,1)]}
def activity_detail(a):
 import news,community,starter
 city=community.name(a['municipality']);path=activity_path(a)
 fields=[('Wanneer',a['label']),('Waar',a.get('locationName') or city),('Adres',a.get('address')),('Organisator',a.get('organizer')),('Prijs',a.get('priceText'))]
 details=''.join('<p><strong>'+news.e(k)+'</strong><br>'+news.e(v)+'</p>' for k,v in fields if v)
 body='<article class="article-wrap"><a href="'+agenda_path(a['municipality'])+'">Agenda '+news.e(city)+'</a><h1>'+news.e(a['title'])+'</h1><p class="standfirst">'+news.e(a['summary'])+'</p>'+details+('<p class=notice>Deze activiteit is afgelopen. Bekijk de agenda voor nieuwe activiteiten.</p>' if a['date']<today().isoformat() else '')+('<p>Deze activiteit is afgelast.</p>' if a.get('cancelled') else '')+'<a class="button" href="'+news.e(a['url'])+'">Bekijk bij de organisator in PITO</a></article>'
 graph=[breadcrumbs([('PITO','/'),('Agenda '+city,agenda_path(a['municipality'])),(a['title'],path)])]
 try:
  start=datetime.datetime.fromisoformat(a.get('startDate','').replace('Z','+00:00'))
  complete=start.tzinfo is not None and start.date().isoformat()==a['date']
 except (ValueError,AttributeError):complete=False
 if complete and a.get('locationName') and a.get('address'):
  event={'@type':'Event','name':a['title'],'description':a['summary'],'url':origin()+path,'startDate':a['startDate'],'location':{'@type':'Place','name':a['locationName'],'address':a['address']},'eventStatus':'https://schema.org/EventCancelled' if a.get('cancelled') else 'https://schema.org/EventScheduled'}
  if a.get('endDate'):event['endDate']=a['endDate']
  if a.get('images'):event['image']=[i['url'] for i in a['images']]
  if a.get('organizer'):event['organizer']={'@type':'Organization','name':a['organizer']}
  graph.append(event)
 return news.layout(a['title']+' in '+city,starter.compact(a['municipality'],'agenda')+community.tabs(a['municipality'],'agenda')+body,path,a['summary'],{'@context':'https://schema.org','@graph':graph})

def sitemap():
 import search_visibility
 paths=search_visibility.catalogue()
 return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(origin()+p)+'</loc></url>' for p in sorted(paths))+'</urlset>'

def news_sitemap():
 import news
 now=datetime.datetime.now(datetime.timezone.utc);entries=[]
 for a in news.articles():
  if a.get('reviewStatus')!='approved' or a.get('publicationStatus')!='published':continue
  try:
   published=datetime.datetime.fromisoformat(a.get('webPublishedAt','').replace('Z','+00:00'))
   if published.tzinfo is None or not datetime.timedelta(0)<=now-published<=datetime.timedelta(days=2):continue
  except ValueError:continue
  entries.append('<url><loc>'+escape(origin()+news.BASE+'/artikel/'+a['slug'])+'</loc><news:news><news:publication><news:name>PITO Nieuws</news:name><news:language>nl</news:language></news:publication><news:publication_date>'+escape(a['webPublishedAt'])+'</news:publication_date><news:title>'+escape(a['title'])+'</news:title></news:news></url>')
 return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">'+''.join(entries[:1000])+'</urlset>'

TOPICS={'Bestuur':'politiek-bestuur','Veiligheid':'veiligheid','Verkeer':'verkeer-ov','Wonen':'wonen-omgeving','Samenleving':'voorzieningen','Sport':'sport'}
def topic_path(m='',category='Bestuur'):
 return '/nieuws/utrecht'+('/'+m if m else '')+'/onderwerp/'+TOPICS[category]
def graph_for_collection(title,path,items,m=''):
 import news
 city=next((x['name'] for x in news.read('municipalities') if x['slug']==m),'provincie Utrecht')
 parts=[('PITO','/'),('Nieuws provincie Utrecht',news.BASE)]
 if m:parts.append(('Nieuws '+city,news.BASE+'/'+m))
 if path not in [p for _,p in parts]:parts.append((title,path))
 return {'@context':'https://schema.org','@graph':[breadcrumbs(parts),{'@type':'CollectionPage','@id':origin()+path+'#page','name':title,'url':origin()+path,'inLanguage':'nl-NL','isPartOf':{'@id':origin()+'/#website'},'about':{'@type':'Place','name':city},'mainEntity':{'@type':'ItemList','itemListElement':[{'@type':'ListItem','position':i,'url':origin()+news.BASE+'/artikel/'+a['slug'],'name':a['title']} for i,a in enumerate(items,1)]}}]}

def metadata_graph(structured):
 org={'@type':'NewsMediaOrganization','@id':origin()+'/#newsroom','name':'PITO Nieuws','url':origin()+'/nieuws/utrecht','publishingPrinciples':origin()+'/nieuws/over-de-redactie'}
 site={'@type':'WebSite','@id':origin()+'/#website','name':'PITO Nieuws','url':origin()+'/','inLanguage':'nl-NL','publisher':{'@id':origin()+'/#newsroom'}}
 nodes=([structured] if structured and '@graph' not in structured else structured.get('@graph',[]) if structured else [])
 if structured and structured.get('@type')=='NewsArticle':
  nodes.append({'@type':'WebPage','@id':structured['mainEntityOfPage'],'url':structured['mainEntityOfPage'],'mainEntity':{'@id':structured['mainEntityOfPage']+'#article'},'breadcrumb':breadcrumbs([('PITO','/'),('Nieuws provincie Utrecht','/nieuws/utrecht'),(structured['headline'],structured['mainEntityOfPage'].removeprefix(origin()))])})
  structured['@id']=structured['mainEntityOfPage']+'#article'
 return {'@context':'https://schema.org','@graph':[org,site]+nodes}


def social_metadata(title,description,path,structured=None):
 from html import escape as esc
 image=(structured or {}).get('image')
 if not image:
  import news
  from urllib.parse import urlsplit,parse_qs
  u=urlsplit(path);m=parse_qs(u.query).get('gemeente',[''])[0]
  names={x['slug'] for x in news.read('municipalities')}
  m=m or next((v for v in u.path.split('/') if v in names),'')
  photo=news.read('municipality-images').get(m,{})
  if photo.get('file'):image=origin()+'/news-static/images/'+photo['file']
 if isinstance(image,list):image=image[0] if image else None
 if not isinstance(image,str):image=origin()+'/news-static/images/utrecht-flyer-background.png'
 return ''.join('<meta '+kind+'="'+key+'" content="'+esc(str(value),quote=True)+'">' for kind,key,value in [('property','og:site_name','PITO Nieuws'),('property','og:locale','nl_NL'),('property','og:image',image),('property','og:image:alt',title),('name','twitter:card','summary_large_image'),('name','twitter:title',title),('name','twitter:description',description),('name','twitter:image',image)])
