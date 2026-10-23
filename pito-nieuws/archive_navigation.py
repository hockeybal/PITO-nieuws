"""Visible paths through the local archive; no invented coverage or popularity."""
from urllib.parse import urlencode
import datetime
import news,seo

def in_archive(a):
 # Keep the complete retained archive; only current selections have an age
 # window. An explicit PITO_EDITION_DATE still controls historical previews.
 value=news.article_date(a)
 if not isinstance(value,str):return False
 value=value[:10]
 try:day=datetime.date.fromisoformat(value)
 except (ValueError,TypeError):return False
 return value==day.isoformat() and day<=seo.today()

def link(m='',category='',month=''):
 if category in seo.TOPICS:return seo.topic_path(m,category)+('?' +urlencode({'maand':month}) if month else '')
 return news.BASE+('/'+m if m else '')+'?'+urlencode({k:v for k,v in {'periode':'archive','sortering':'latest','maand':month}.items() if v})
def rail(m='',category=''):
 items=[a for a in news.articles() if in_archive(a) and news.selected(a,m) and (not category or a['category']==category)]
 months=sorted({news.article_date(a)[:7] for a in items},reverse=True)
 labels=['jan','feb','mrt','apr','mei','jun','jul','aug','sep','okt','nov','dec']
 return '<nav class="archive-rail" aria-label="Nieuwsarchief"><a class="archive-all" href="'+link(m,category)+'">Alle berichten</a>'+''.join('<a href="'+link(m,category,v)+'">'+labels[int(v[5:])-1]+' '+v[:4]+'</a>' for v in months)+'</nav>'
def earlier(m='',exclude=()):
 items=[a for a in news.articles() if in_archive(a) and a['slug'] not in exclude and not news.ranking.is_recent(a) and (m in a.get('municipalities',[]) if m else True)]
 return news.ranking.order(items,'latest',diversify=False)[:6]
def block(items,m=''):
 if not items:return ''
 city=next((x['name'] for x in news.read('municipalities') if x['slug']==m),'Utrecht')
 return '<section class="section earlier-news"><div class="section-title"><div><p class="eyebrow">HET VERHAAL GAAT VERDER</p><h2>Eerder in '+news.e(city)+'</h2></div><a href="'+link(m)+'">Alle eerdere berichten ›</a></div><p>Uit het archief, met de oorspronkelijke brondatum.</p><div class="more-grid">'+''.join(news.card(a) for a in items)+'</div></section>'
def topics(m=''):
 cards=''
 for c,label in news.CATEGORIES.items():
  items=[a for a in news.articles() if in_archive(a) and news.selected(a,m) and a['category']==c]
  if items:cards+='<a href="'+link(m,c)+'"><span>'+news.e(label)+'</span><b aria-hidden="true">›</b></a>'
 return '<section class="topic-directory"><div><p class="eyebrow">JOUW INTERESSE</p><h2>Volg jouw onderwerpen</h2></div><nav aria-label="Nieuws per onderwerp">'+cards+'</nav></section>'
def related(a):
 candidates=[x for x in news.articles() if in_archive(x) and x['slug']!=a['slug']]
 local=set(a.get('municipalities',[]));same=[x for x in candidates if x['category']==a['category']]
 same.sort(key=lambda x:(bool(local.intersection(x.get('municipalities',[]))),news.article_date(x)),reverse=True)
 ids={x['slug'] for x in same[:4]}
 earlier_local=sorted([x for x in candidates if x['slug'] not in ids and local.intersection(x.get('municipalities',[]))],key=lambda x:news.article_date(x),reverse=True)[:4]
 def rows(title,items):
  if not items:return ''
  return '<section class="topic-desk"><h2>'+title+'</h2><ol>'+''.join('<li><time>'+news.date(news.article_date(x))+'</time><a href="'+news.url(x)+'">'+news.e(x['title'])+'</a></li>' for x in items)+'</ol></section>'
 return '<div class="topic-desks related-news">'+rows('Meer over '+news.CATEGORIES[a['category']].lower(),same[:4])+rows('Meer uit jouw gemeente',earlier_local)+'</div><p><a href="'+link('',a['category'])+'">Dit onderwerp in de hele provincie ›</a></p>'

def province_more(m=''):
 if not m:return ''
 items=[a for a in news.articles() if in_archive(a) and m not in a.get('municipalities',[]) and not a.get('provinceWide')]
 items=news.ranking.order(items,'latest',diversify=False)[:5]
 return '<section class="section province-digest"><div class="section-title"><h2>Ook in de provincie Utrecht</h2><a href="'+link()+'">Alle gemeenten ›</a></div><ol>'+''.join('<li><time>'+news.date(news.article_date(a))+' · '+news.e(', '.join(next((x['name'] for x in news.read('municipalities') if x['slug']==m),m) for m in a.get('municipalities',[])))+'</time><a href="'+news.url(a)+'">'+news.e(a['title'])+'</a></li>' for a in items)+'</ol></section>'
