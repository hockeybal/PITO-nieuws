"""Chronological, progressively enhanced news archive."""
from urllib.parse import urlencode
import news, seo, media_library, community, starter

SIZE = 24

def render(m='', q='', category='', month='', page='1', path=None):
 path = path or news.BASE + ('/'+m if m else '')
 names = {x['slug']:x['name'] for x in news.read('municipalities')}
 name = names.get(m, 'Provincie Utrecht')
 items = [a for a in news.articles() if news.selected(a,m)
          and '2026-07-11' <= a['sourcePublishedAt'][:10] <= seo.today().isoformat()
          and (not category or a['category']==category)
          and (not month or a['sourcePublishedAt'].startswith(month))
          and (not q or q.casefold() in (a['title']+' '+a['summary']).casefold())]
 items.sort(key=lambda a:(a['sourcePublishedAt'],a['slug']), reverse=True)
 try: page = max(1,min(max(1,(len(items)+SIZE-1)//SIZE),int(page)))
 except (TypeError,ValueError): page=1
 batch = media_library.assign(items[(page-1)*SIZE:page*SIZE],news.read('images'))
 def link(n):
  return path+'?'+urlencode({'periode':'archive','sortering':'latest','q':q,'onderwerp':category,'maand':month,'pagina':n})
 rows=[]
 for a in batch:
  published=a['sourcePublishedAt']; stamp=news.date(published)
  if 'T' in published:
   try:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dt=datetime.fromisoformat(published.replace('Z','+00:00'))
    if dt.tzinfo:dt=dt.astimezone(ZoneInfo('Europe/Amsterdam'))
    stamp += ' · '+dt.strftime('%H:%M')
   except ValueError:pass
  rows.append('<li class="latest-row"><div class="latest-copy"><time datetime="'+news.e(published)+'">'+stamp+'</time><h2><a href="'+news.url(a)+'">'+news.e(a['title'])+'</a></h2></div><div class="latest-thumb">'+news.artwork(a)+'</div></li>')
 nextlink='<a class="latest-more" data-latest-next href="'+news.e(link(page+1))+'">Meer nieuws laden <span aria-hidden="true">↓</span></a>' if page*SIZE<len(items) else '<p class="latest-end">Je bent aan het einde van dit overzicht.</p>'
 previous='<a class="latest-back" href="'+news.e(link(page-1))+'">← Nieuwere berichten</a>' if page>1 else ''
 sidebar=''.join('<li><a href="'+news.url(a)+'">'+news.e(a['title'])+'</a></li>' for a in news.ranking.order(items,'relevance')[:5])
 heading='Zoekresultaten' if q else 'Net binnen'
 context='<p class="latest-context">'+news.e(name)+(' · '+news.e(news.CATEGORIES.get(category,category)) if category else '')+(' · “'+news.e(q)+'”' if q else '')+'</p>'
 body=starter.render(batch,m,filters={'periode':'archive','sortering':'latest','onderwerp':category})+community.tabs(m,category=category)
 body+='<section class="latest-page"><header><h1>'+heading+'</h1>'+context+'</header><div class="latest-layout"><div>'+previous+'<ol class="latest-rows" data-latest-rows>'+(''.join(rows) or '<li class="latest-empty">Geen berichten gevonden voor deze selectie.</li>')+'</ol><div data-latest-pagination>'+nextlink+'</div><p class="latest-status" role="status" aria-live="polite"></p></div><aside class="latest-sidebar"><h2>Meer uit '+news.e(name)+'</h2><ol>'+sidebar+'</ol><a class="latest-overview" href="'+news.BASE+('/'+m if m else '')+'">Naar het nieuwsoverzicht →</a></aside></div></section><script defer src="/news-static/latest-news.js?v=1"></script>'
 return news.layout(heading+' · '+name,body,link(page),'Het laatste lokale nieuws uit '+name,seo.graph_for_collection(heading,link(page),batch,m))
