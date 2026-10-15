"""Venue images are context, never represented as photographs of the event."""
import json
from pathlib import Path
ROOT=Path(__file__).parent

def venues():return json.loads((ROOT/'data/agenda-venue-images.json').read_text())
def image(a):
 import news
 text=(a['title']+' '+a.get('locationName','')).casefold()
 v=next((v for v in venues() if a['municipality']==v['municipality'] and any(t in text for t in v['terms'])),None)
 if v:return '<img class="invitation-event-photo" src="/news-static/images/'+news.e(v['file'])+'" alt="'+news.e(v['alt'])+'" title="Locatiebeeld; geen foto van de activiteit" loading="lazy" width="76" height="86">'
 for v in a.get('images',[]):
  if v.get('url','').startswith('/news-static/images/') and v.get('credit'):
   return '<img class="invitation-event-photo" src="'+news.e(v['url'])+'" alt="'+news.e(v.get('alt',''))+'" title="'+news.e(v['credit'])+'" loading="lazy" width="76" height="86">'
 return ''
def credits():
 import news
 body='<article class="article-wrap"><h1>Beelden bij de agenda</h1><p>Deze foto’s tonen de locatie. Ze zijn geen verslag van het aangekondigde evenement. Foto’s worden bijgesneden voor de kaarten; de oorspronkelijke licentie blijft van toepassing.</p>'
 for v in venues():body+='<section><h2>'+news.e(v['alt'])+'</h2><p>'+news.e(v['capturedAt'])+' · <a href="'+news.e(v['sourceUrl'])+'">'+news.e(v['author'])+'</a> · <a href="'+news.e(v['licenseUrl'])+'">'+news.e(v['license'])+'</a></p></section>'
 return news.layout('Agendafoto’s',body+'</article>','/nieuws/agenda-beeldcredits')
