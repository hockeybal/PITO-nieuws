"""Compact municipality-aware PITO activities on the editorial homepage."""
import datetime
import news,seo,community,agenda_images

def select(items,m,today,week=False,end=None):
 end=end or (today+datetime.timedelta(days=6-today.weekday()) if week else today)
 rows=[];seen=set()
 for a in sorted(items,key=lambda a:(a['date'],a.get('startDate') or a.get('timesText',''),a['title'])):
  if (m and a['municipality']!=m) or a.get('cancelled') or not today.isoformat()<=a['date']<=end.isoformat():continue
  if week and not a.get('agendaHighlight',True):continue
  key=a.get('id') or a['url']
  if key in seen:continue
  seen.add(key);rows.append(a)
 # Avoid a homepage dominated by one venue while preserving date order.
 counts={};chosen=[]
 if not m:
  buckets={}
  if not week:today_ids={a.get('id') or a['url'] for a in rows}
  for a in rows:buckets.setdefault(a['municipality'],[]).append(a)
  rows=[b[i] for i in range(max((len(b) for b in buckets.values()),default=0)) for b in buckets.values() if i<len(b)]
 for a in rows:
  venue=(a.get('locationName') or a.get('organizer') or a.get('id') or a['url']).casefold().split(' vergaderen')[0][:24]
  if counts.get(venue,0)>=2:continue
  counts[venue]=counts.get(venue,0)+1;chosen.append(a)
 return chosen[:4]

def block(m=''):
 items,status=news.app_content.get();today=seo.today();city=community.name(m) if m else 'Provincie Utrecht';sections=[];today_ids=set()
 for week,title,key in [(False,'Vandaag te doen','vandaag'),(True,'Agenda deze week','deze-week')]:
  pool=[a for a in items if not week or (a.get('agendaHighlight') is True and (a.get('id') or a['url']) not in today_ids)]
  rows=select(pool,m,today,week);cards=[];context=''
  if not rows:
   rows=select(pool,m,today,False,end=today+datetime.timedelta(days=60))
   if rows:
    title='Binnenkort te doen' if not week else 'Verder in de agenda'
    context='De eerstvolgende activiteiten in '+city+'.'
   elif m:
    rows=select(pool,'',today,week)
    if rows:
     title='Vandaag in de regio' if not week else 'Deze week in de regio'
     context='Nog geen lokale activiteiten bekend. Ontdek ook wat er in de regio te doen is.'

  if not week:today_ids={a.get('id') or a['url'] for a in rows}
  for a in rows:
   d=datetime.date.fromisoformat(a['date']);day=['Ma','Di','Wo','Do','Vr','Za','Zo'][d.weekday()];month=['jan','feb','mrt','apr','mei','jun','jul','aug','sep','okt','nov','dec'][d.month-1]
   meta=' · '.join(x for x in [a.get('timesText'),a.get('locationName')] if x)
   cards.append('<li><a class="invitation-event" href="'+news.e(a['url'])+'" target="_blank" rel="noopener"><time datetime="'+a['date']+'"><span>'+day+'</span><strong>'+str(d.day)+'</strong><span>'+month+'</span></time>'+agenda_images.image(a)+'<div class="invitation-event-copy"><span class="invitation-city">'+news.e(community.name(a['municipality']))+'</span><h3>'+news.e(a['title'])+'</h3>'+('<p>'+news.e(meta)+'</p>' if meta else '')+'</div></a></li>')
  empty_message={'unavailable':'De agenda is tijdelijk niet beschikbaar.','not_configured':'De actuele PITO-agenda is nog niet beschikbaar.'}.get(status,'Voor deze periode staan er nog geen bevestigde activiteiten in '+news.e(city)+'.')
  content='<ul>'+''.join(cards)+'</ul>' if cards else '<div class="invitation-empty"><strong>Wat ga jij ontdekken?</strong><p>'+empty_message+'</p><a href="'+seo.agenda_path(m)+'">Bekijk de volledige agenda →</a></div>'
  sections.append('<section class="invitation-strip '+('week' if week else 'today')+'" id="home-'+key+'"><header><span class="invitation-kicker">'+('MAAK ALVAST PLANNEN' if week else 'GA EROP UIT')+'</span><h2>'+title+'</h2><p>'+news.e(context or ('Iets om naar uit te kijken.' if week else 'Een mooi moment begint dichtbij.'))+'</p><a class="invitation-all" href="'+seo.agenda_path('' if 'in de regio' in title else m,('' if week else 'binnenkort') if title in ('Binnenkort te doen','Verder in de agenda') else key)+'">'+('Bekijk de week' if week else 'Ontdek vandaag')+' <span aria-hidden="true">→</span></a></header><div class="invitation-content">'+content+'</div></section>')
 return '<div class="invitation-agenda" aria-label="Activiteiten in '+news.e(city)+'">'+''.join(sections)+'</div><a class="invitation-photo-credit" href="/nieuws/agenda-beeldcredits">Over de agendafoto’s</a>'
