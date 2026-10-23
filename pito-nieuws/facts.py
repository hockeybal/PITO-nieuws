"""Separate evergreen local stories, deliberately excluded from breaking-news ranking/RSS."""
import datetime,json
from pathlib import Path
import news,ranking,media_library,search_visibility
ROOT=Path(__file__).parent
BASE='/nieuws/weetjes/'
def records():
 return json.loads((ROOT/'data/facts.json').read_text())
def visible():
 result=[]
 for a in records():
  try:
   valid=(a.get('status') in ('preview','approved') and a.get('municipality') in {m['slug'] for m in news.read('municipalities')}
     and a.get('title') and a.get('summary') and a.get('body') and a.get('sourceUrl','').startswith('https://')
     and datetime.date.fromisoformat(a['verifiedAt'])<=ranking.today()<=datetime.date.fromisoformat(a['reviewBy']))
   if search_visibility.public_facing():valid=valid and search_visibility.published(dict(a,reviewStatus=a.get('status')))
   if valid:result.append(a)
  except (ValueError,KeyError,TypeError):continue
 return sorted(result,key=lambda a:a['slug'])
def pick(m='',items=None,day=None):
 pool=[a for a in (visible() if items is None else items) if not m or a['municipality']==m]
 if not pool:return None
 day=day or ranking.today()
 week=(day-datetime.date(2026,10,5)).days//7
 return sorted(pool,key=lambda a:a['slug'])[week%len(pool)]
def creative():
 return '<figure class="fact-photo fact-creative"><img src="/news-static/campaign/pito-lamp-cutout.png" alt="PITO houdt een lichtgevend lampje vast: wist je dat?" loading="lazy"></figure>'

def photo(a,used=()):
 library=news.read('images');key=a.get('imageKey');image=library.get(key)
 if not media_library.eligible(image) or media_library.identity(image) in used:return ''
 return '<figure class="fact-photo"><img src="/news-static/images/'+news.e(image['file'])+'" alt="'+news.e(image['alt'])+'" loading="lazy"><figcaption>'+news.e(a.get('imageNote','Contextbeeld'))+' · '+news.e(image['author'])+' · <a href="'+news.e(image['sourceUrl'])+'">'+news.e(image['license'])+'</a> · <a href="'+news.e(image['licenseUrl'])+'">Licentie</a> · uitsnede</figcaption></figure>'
def block(m='',used=()):
 a=pick(m)
 if not a:return ''
 municipality=next(x['name'] for x in news.read('municipalities') if x['slug']==a['municipality'])
 visual=photo(a,used) or creative()
 image=news.read('images').get(a.get('imageKey'),{})
 if 'fact-creative' not in visual:
  import re
  visual=re.sub(r'<figcaption>.*?</figcaption>',lambda _: '<figcaption><a href="'+BASE+a['slug']+'">© '+news.e(image.get('author',''))+' · '+news.e(image.get('license',''))+'</a></figcaption>',visual,flags=re.S)
 return '<section id="weetje-van-de-week" class="weekly-feature" aria-labelledby="weekly-fact-title"><div class="weekly-feature-copy"><div class="weekly-title"><img src="/news-static/campaign/pito-lamp-cutout.png" alt="" loading="lazy"><h2 id="weekly-fact-title">Weetje van de week</h2></div><span class="weekly-feature-place">'+news.e(municipality)+'</span><h3>'+news.e(a['title'])+'</h3><p>'+news.e(a['summary'])+'</p><a class="weekly-feature-link" href="'+BASE+a['slug']+'">Ontdek het verhaal <span aria-hidden="true">→</span></a></div><div class="weekly-feature-visual">'+visual+'</div></section>'

def detail(a):
 name=next(x['name'] for x in news.read('municipalities') if x['slug']==a['municipality'])
 body='<article class="article-wrap"><a href="'+news.BASE+'/'+a['municipality']+'">Nieuws uit '+news.e(name)+'</a><p class="eyebrow">WIST JE DAT? · '+news.e(name)+'</p><h1>'+news.e(a['title'])+'</h1><p class="standfirst">'+news.e(a['summary'])+'</p>'+(photo(a) or creative())+'<div class="article-body">'+''.join('<p>'+news.e(p)+'</p>' for p in a['body'].split('\n\n'))+'</div><aside class="sourcebox"><h2>Het verhaal achter het weetje</h2><p>Eigen tekst op basis van '+news.e(a['sourceName'])+'. Bron gecontroleerd op '+news.date(a['verifiedAt'])+'.</p><a href="'+news.e(a['sourceUrl'])+'">Bekijk de oorspronkelijke bron</a><p>Dit is een tijdloos achtergrondverhaal, geen actueel nieuwsbericht. '+('Lokale concepteditie; menselijke eindredactie volgt.' if a['status']=='preview' else 'Redactioneel beoordeeld.')+'</p></aside><a class="button" href="'+news.BASE+'/'+a['municipality']+'">Meer uit '+news.e(name)+'</a></article>'
 return news.layout(a['title'],body,BASE+a['slug'],a['summary'])
