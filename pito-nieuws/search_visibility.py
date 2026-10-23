"""Shared sitemap/indexing policy. Preview is private by default; never promotes drafts."""
import datetime, os
from urllib.parse import urlsplit, parse_qsl, urlencode


def production():
 import seo
 u=urlsplit(seo.origin())
 return os.environ.get('PITO_SITE_MODE')=='production' and u.scheme=='https' and u.hostname in ('pitonieuws.nl','www.pitonieuws.nl')

def public_facing():return production() or os.environ.get('PITO_PUBLIC_PREVIEW')=='1'


def published(a):
 if a.get('reviewStatus')!='approved' or a.get('publicationStatus')!='published':return False
 try:
  d=datetime.datetime.fromisoformat(a.get('webPublishedAt','').replace('Z','+00:00'))
  return d.tzinfo is not None and d<=datetime.datetime.now(datetime.timezone.utc)
 except (ValueError,TypeError):return False


def canonical_path(path):
 u=urlsplit(path)
 # Only presentation/tracking parameters are disposable. Keep genuine pagination/locality.
 remove={'beeld','sortering','utm_source','utm_medium','utm_campaign','utm_term','utm_content','gclid','fbclid'}
 query=sorted((k,v) for k,v in parse_qsl(u.query) if k not in remove)
 return (u.path.rstrip('/') or '/')+('?' +urlencode(query) if query else '')


def catalogue():
 import news,seo
 paths=set();articles=[a for a in news.articles() if published(a)]
 cities={x['slug'] for x in news.read('municipalities')}
 for a in articles:
  paths.add(news.BASE+'/artikel/'+a['slug'])
  for m in ['']+sorted(cities if a.get('provinceWide') else set(a.get('municipalities',[]))&cities):
   paths.add(news.BASE+('/'+m if m else ''))
   if a.get('category') in seo.TOPICS:paths.add(seo.topic_path(m,a['category']))
 activities,status=news.app_content.get()
 if status=='connected':
  for a in activities:
   if a.get('municipality') not in cities:continue
   paths.add(seo.activity_path(a))
   if a['date']<seo.today().isoformat():continue
   for m in ('',a['municipality']):
    paths.add(news.BASE+('/'+m if m else ''))
    if a.get('agendaHighlight') is True:paths.add(seo.agenda_path(m))
    for day in ('vandaag','morgen','dit-weekend','binnenkort'):
     if seo.matches(a,day):paths.add(seo.agenda_path(m,day))
 if production():
  import useful_addresses,official_content,environment_notices
  facts=news.read('local-service-facts')
  for m in cities:
   f=facts.get(m,{})
   if f.get('phone') and f.get('wasteFacts'):
    paths.update((useful_addresses.path(m),news.BASE+'/'+m))
  for r in environment_notices.records():
   data=official_content.read(r)
   if not data or len(data.get('blocks',[]))<2:continue
   paths.update((environment_notices.detail_path(r),environment_notices.path(r['municipality']),environment_notices.path()))
  paths.update((news.BASE,'/nieuws/gemeenten','/nieuws/nuttige-adressen','/nieuws/over-de-redactie'))
 return paths


def robots_meta(path):
 if not production():return 'noindex,nofollow'
 return 'index,follow,max-image-preview:large' if canonical_path(path) in catalogue() else 'noindex,follow'


def robots_txt():
 import seo
 if not production():return 'User-agent: *\nDisallow: /\n'
 # Search access is independent of the operator's GPTBot training preference.
 return ('User-agent: *\nAllow: /\nDisallow: /nieuws/redactie\nDisallow: /api/\nDisallow: /news-static/source-audit/\n'
         'Sitemap: '+seo.origin()+'/nieuws/sitemap.xml\nSitemap: '+seo.origin()+'/nieuws/news-sitemap.xml\n')
