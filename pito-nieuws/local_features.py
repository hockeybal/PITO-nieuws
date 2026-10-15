"""Source-checked editorial outings, separate from the connected PITO agenda."""
import news,datetime

def block(m=''):
 items=[x for x in news.read('local-tips') if (not m or m==x['municipality']) and x['date']>=news.ranking.today().isoformat()]
 if not items:return ''
 rows=''.join('<article><time datetime="'+x['date']+'">'+news.date(x['date'])+' · '+news.e(x['time'])+'</time><h3><a href="'+news.e(x['sourceUrl'])+'">'+news.e(x['title'])+'</a></h3><p>'+news.e(x['summary'])+'</p><small>'+news.e(x['sourceName'])+' · broncontrole '+news.date(x['verifiedAt'])+'</small></article>' for x in items)
 return '<section class="section local-outings"><div class="section-title"><h2>Uit in '+('Woerden' if m else 'de provincie')+'</h2><a href="'+news.seo.agenda_path(m)+'">PITO-agenda ›</a></div><p class="coverage-note">Redactionele tips uit de agenda van de organisator. Bekijk daar de actuele beschikbaarheid.</p><div class="editorial-cards">'+rows+'</div></section>'
