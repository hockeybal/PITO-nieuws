"""PITO activity list and three-image agenda, backed by shared app data."""
import datetime,json
from urllib.parse import urlencode,urlsplit
import news,seo,community,starter,promotions

def categories():return news.read('app-activity-categories')
def label(c):return 'Naar buiten gaan / ontdekken' if c=='Naaar buiten gaan/ ontdekken' else c

def page(m,view,day='vandaag',category='',q='',page_number='1',month=''):
 day=day if day in ('vandaag','morgen','binnenkort','dit-weekend','deze-week') else 'vandaag'
 city=community.name(m) if m else 'provincie Utrecht';base=seo.agenda_path(m,day if view=='vandaag' or day=='deze-week' else '')
 category=category if view=='vandaag' and category in categories() else '';q=q.strip()[:120] if view=='vandaag' else ''
 app,status=news.app_content.get();today=seo.today()
 horizon=today+datetime.timedelta(days=59)
 local=[a for a in app if (not m or a['municipality']==m) and not a.get('cancelled') and today.isoformat()<=a['date']<=horizon.isoformat()]
 if view=='agenda' or day=='deze-week':local=[a for a in local if a.get('agendaHighlight') is True]
 chosen=[a for a in local if (not category or a.get('category')==category) and (not q or q.casefold() in (a['title']+' '+a.get('locationName','')).casefold()) and seo.matches(a,day if view=='vandaag' or day=='deze-week' else '')]
 chosen.sort(key=lambda a:(a['date'],a.get('startDate') or '',a['title']))
 heading=(('Gemeenteagenda van ' if m else 'Agenda van de ') if view=='agenda' else {'vandaag':'Vandaag te doen in ','morgen':'Morgen te doen in ','dit-weekend':'Dit weekend te doen in ','binnenkort':'Activiteiten in ','deze-week':'Agenda deze week in '}[day])+city
 top=starter.compact(m,view,day,{'categorie':category,'q':q})+community.tabs(m,view)
 pills='<nav class="day-pills" aria-label="Wanneer">'+''.join('<a '+('aria-current="page" ' if day==d else '')+'href="'+seo.agenda_path(m,d)+('?' +urlencode({'categorie':category,'q':q}) if category or q else '')+'">'+s+'</a>' for d,s in [('vandaag','Vandaag'),('morgen','Morgen'),('binnenkort','Komende 60 dagen'),('dit-weekend','Dit weekend')])+'</nav>' if view=='vandaag' else ''
 filters='<form class="app-event-filters" action="'+base+'"><label>Categorie<select name="categorie"><option value="">Alle categorieën</option>'+''.join('<option value="'+news.e(c)+'" '+('selected' if category==c else '')+'>'+news.e(label(c))+'</option>' for c in categories())+'</select></label><label>Zoeken<input name="q" value="'+news.e(q)+'" placeholder="Activiteit of locatie"></label><button>Toon resultaten</button><a href="'+base+'">Wis filters</a></form>'
 note='<p class="agenda-snapshot-note">Controleer actuele tijden en beschikbaarheid bij de organisator.</p>' if status=='local_preview' else ''
 months=['Januari','Februari','Maart','April','Mei','Juni','Juli','Augustus','September','Oktober','November','December']
 groups={};seen=set()
 limit=horizon
 available_months=sorted({a['date'][:7] for a in chosen})
 month=month if month in available_months else ''
 if month:chosen=[a for a in chosen if a['date'].startswith(month)]
 try:page_number=max(1,int(page_number))
 except (ValueError,TypeError):page_number=1
 page_count=max(1,(len(chosen)+23)//24);page_number=min(page_number,page_count)
 chosen=chosen[(page_number-1)*24:page_number*24]
 monthnav='<nav class="agenda-month-nav" aria-label="Kies een maand">'+''.join('<a '+('aria-current="page" ' if key==month else '')+'href="'+base+'?'+news.e(urlencode({'maand':key,'categorie':category,'q':q}))+'">'+title+'</a>' for key,title in [('', 'Deze week' if view=='agenda' and day=='deze-week' else 'Alle 60 dagen')]+[(key,months[int(key[5:])-1]+' '+key[:4]) for key in available_months])+'</nav>'
 pagination='<nav class="agenda-pagination" aria-label="Meer activiteiten">'+''.join('<a href="'+base+'?'+news.e(urlencode({'pagina':n,'maand':month,'categorie':category,'q':q}))+'">'+title+'</a>' for n,title in [(page_number-1,'‹ Vorige'),(page_number+1,'Meer agendapunten ›' if view=='agenda' else 'Meer activiteiten ›')] if 1<=n<=page_count)+'</nav>'
 for a in chosen:
  if view=='vandaag' and day=='binnenkort' and a['date']>limit.isoformat():continue
  key=a['date'][:7] if view=='agenda' else a['date']
  groups.setdefault(key,[]).append(a)
 if view!='agenda' and day!='binnenkort':monthnav=''
 if view=='agenda':
  filters=''
 else:
  filters=filters.replace('<label>Categorie','<input type="hidden" name="maand" value="'+news.e(month)+'"><label>Categorie',1)

 body=''
 for date,rows in sorted(groups.items()):
  d=datetime.date.fromisoformat(date+'-01' if view=='agenda' else date)
  daylabel=(months[d.month-1]+' '+str(d.year)) if view=='agenda' else ('Vandaag' if d==today else 'Morgen' if d==today+datetime.timedelta(days=1) else news.date(date))
  css='app-month-group' if view=='agenda' else 'app-day-group'
  body+='<section class="'+css+'" id="maand-'+date+'"><h2>'+daylabel+'</h2>'+(''.join(community.activity(a,view) for a in rows) or '<p class="month-empty">Nog geen agendapunten voor deze selectie.</p>')+'</section>'
 if not body:
  body='<div class="agenda-empty"><h2>'+('Nog geen agendapunten voor deze selectie' if view=='agenda' else 'Nog geen activiteiten voor deze selectie')+'</h2><p>'+('Er zijn nog geen agendapunten beschikbaar voor deze gemeente en periode.' if view=='agenda' else 'Probeer een andere dag of categorie.')+'</p><a href="'+(seo.agenda_path() if view=='agenda' else seo.agenda_path(m,'binnenkort'))+'">'+('Bekijk de provinciale agenda' if view=='agenda' else 'Bekijk komende activiteiten')+'</a></div>'
 intro=('Evenementen en bijzondere momenten in je gemeente.' if m else 'Evenementen uit alle 26 gemeenten. Kies bovenaan een gemeente voor jouw lokale agenda.') if view=='agenda' else 'Ontdek wat je kunt doen, op volgorde van dag en tijd.'
 intro+=(' Bekijk de agendapunten van deze week.' if day=='deze-week' and view=='agenda' else ' Bekijk de komende 60 dagen, op datum.')+' Per pagina tonen we maximaal 24 '+('agendapunten.' if view=='agenda' else 'activiteiten.')
 content='<div id="lokaaloverzicht" class="app-events"><header><p class="eyebrow">ONTDEK DE BUURT</p><h1>'+news.e(heading)+'</h1><p>'+intro+'</p></header>'+pills+filters+monthnav+note+'<div class="app-events-layout"><div>'+body+pagination+'</div><aside>'+promotions.ad('rail','app')+'</aside></div></div>'
 return news.layout(heading,top+content,base,intro,seo.breadcrumbs([('PITO','/'),('Nieuws',news.BASE),(heading,base)]))
