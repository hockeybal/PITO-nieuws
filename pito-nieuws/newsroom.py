"""Shared editorial components for province, municipality and article pages."""
import news,seo,media_library

def related_items(a,limit=6):
 candidates=[x for x in news.articles() if x['slug']!=a['slug']]
 places=set(a.get('municipalities',[]))
 candidates=[x for x in candidates if x['category']==a['category'] or places.intersection(x.get('municipalities',[]))]
 candidates.sort(key=lambda x:(x['category']==a['category'] and bool(places.intersection(x.get('municipalities',[]))),x['category']==a['category'],x['sourcePublishedAt']),reverse=True)
 return candidates[:limit]
def article_body(a):
 paragraphs=[p.strip() for p in a['body'].split('\n\n') if p.strip()]
 impact=a.get('impact','').strip()
 if impact and impact not in a['body'] and impact!=a.get('dateNote') and impact!=a['summary']:paragraphs.append(impact)
 rows=related_items(a,1)
 result=''
 for i,p in enumerate(paragraphs):
  result+='<p>'+news.e(p)+'</p>'
  if i==1 and len(paragraphs)>2 and rows:
   x=media_library.assign(rows,news.read('images'))[0];result+='<aside class="inline-related article-read-also">'+news.artwork(x)+'<div><span>Lees ook</span><a href="'+news.url(x)+'">'+news.e(x['title'])+'</a></div></aside>'
 return result

def related(a):
 items=related_items(a)
 library=news.read('images');current=media_library.media_for(a,library)
 if current:library={k:v for k,v in library.items() if media_library.identity(v)!=media_library.identity(current)}
 cards=''.join(news.card(x) for x in media_library.assign(items,library))
 m=next(iter(a.get('municipalities',[])),'')
 tags='<a href="'+seo.topic_path(m,a['category'])+'">'+news.e(news.CATEGORIES[a['category']])+'</a>'
 names={x['slug']:x['name'] for x in news.read('municipalities')}
 tags+=''.join('<a href="'+news.BASE+'/'+p+'">'+news.e(names.get(p,p))+'</a>' for p in a.get('municipalities',[]))
 return '<nav class="article-tags" aria-label="Lees meer over"><strong>Lees meer over</strong>'+tags+'</nav>'+('<section class="section related-editorial"><div class="section-title"><h2>Lees ook</h2><a href="'+seo.topic_path('',a['category'])+'">Dit onderwerp in de hele provincie ›</a></div><div class="editorial-cards">'+cards+'</div></section>' if items else '')
