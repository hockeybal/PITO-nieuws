"""Local community prototype; submissions stay private until editorial approval."""
import json,re,secrets,datetime
from pathlib import Path
import news, seo, search_visibility
ROOT=Path(__file__).parent
VIEWS={'nieuws':'Nieuws','vandaag':'Vandaag te doen','agenda':'Gemeenteagenda','community':'Communitynieuws'}
def records():
 p=ROOT/'data/community.json'
 return json.loads(p.read_text()) if p.exists() else []
def store(data):
 p=ROOT/'data/community.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(p)
def tabs(m='',view='nieuws',category=''):
 path=news.BASE+('/'+m if m else '')
 links=[(path,'Overzicht',view=='nieuws' and not category)]+[(seo.view_path(m,'vandaag'),'Vandaag te doen',view=='vandaag'),(seo.view_path(m,'agenda'),'Agenda',view=='agenda')]+[(seo.topic_path(m,c),label,category==c) for c,label in [('Bestuur','Politiek'),('Veiligheid','Veiligheid'),('Verkeer','Verkeer & OV'),('Wonen','Wonen & bouwen')]]+[(seo.topic_path(m,c),label,category==c) for c,label in [('Samenleving','Algemeen'),('Sport','Sport')]]+[(path+'/omgevingszaken','Omgevingszaken',view=='omgeving'),(seo.view_path(m,'community'),'Community',view=='community')]
 return '<nav class="local-tabs" aria-label="Nieuwsrubrieken">'+''.join('<a '+('aria-current="page" ' if active else '')+'href="'+url+'">'+label+'</a>' for url,label,active in links)+'</nav>'

def name(m):return next((x['name'] for x in news.read('municipalities') if x['slug']==m),'Utrecht')
def recruitment(m):
 return '<section class="community-call"><div><p class="eyebrow">SAMEN WETEN WE MEER</p><h2>Jouw gemeente. Jouw verhaal.</h2><p>Wil jij helpen aan de lokale informatievoorziening? Word een van de lokale redacteurs in '+news.e(name(m))+'. Deel wat er speelt, geef initiatieven een gezicht en schrijf onder je eigen naam.</p><p>Meerdere schrijvers per gemeente · ruimte voor jouw kennis · controle door de redactie</p><a class="button" href="/nieuws/meedoen?gemeente='+news.e(m)+'">Ik wil meedoen</a></div><div class="community-join"><p>Ken jij jouw buurt<br>als geen ander?</p><span>Schrijf mee met PITO.</span></div></section>'
def visible(m=''):
 return [a for a in records() if a['kind']=='story' and a['status']=='approved' and a.get('reviewer') and a.get('confirmed') and (not m or a['municipality']==m) and (not search_visibility.public_facing() or search_visibility.published(dict(a,reviewStatus=a.get('status'))))]
def byline(a):return 'Door '+news.e(a['authorName'])+' · '+news.e(name(a['municipality']))
def card(a):
 return '<article class="listing"><p class="eyebrow">COMMUNITYNIEUWS</p><h3><a href="/nieuws/community/artikel/'+a['id']+'">'+news.e(a['title'])+'</a></h3><p>'+news.e(a['summary'])+'</p><small>'+byline(a)+'</small></article>'
def detail(a):
 source='<p><a href="'+news.e(a['sourceUrl'])+'">Bekijk de bron</a></p>' if a.get('sourceUrl') else ''
 return news.layout(a['title'],'<article class="article-wrap"><a href="'+news.BASE+'/'+a['municipality']+'?weergave=community">Communitynieuws</a><p class="eyebrow">COMMUNITYNIEUWS</p><h1>'+news.e(a['title'])+'</h1><p class="standfirst">'+news.e(a['summary'])+'</p><p class="article-meta">'+byline(a)+' · Lokaal beoordeeld door '+news.e(a['reviewer'])+'</p><div class="article-body">'+''.join('<p>'+news.e(p)+'</p>' for p in a['body'].split('\n\n'))+'</div>'+source+'<p>Bijdrage uit de gemeenschap. Dit is een lokale preview.</p></article>','/nieuws/community/artikel/'+a['id'])
def page(m,view,day='vandaag',category='',q=''):
 if view in ('vandaag','agenda'):
  import agenda_views
  return agenda_views.page(m,view,day,category,q)
 import starter
 city=name(m);heading='Communitynieuws uit '+city
 top=starter.render([],m,view,day)+tabs(m,view)+'<div id="lokaaloverzicht" class="local-page-heading"><h1>'+news.e(heading)+'</h1></div>'
 items=visible(m)
 content='<section class="section"><h2>Verhalen van mensen uit de buurt</h2><p>Lokale initiatieven, verenigingen en ontwikkelingen. Met een naam bij ieder verhaal en beoordeling vóór plaatsing.</p><div class="listing-grid">'+(''.join(card(a) for a in items) or '<p class="empty">De eerste verhalen mogen nog geschreven worden. Vertel wat er speelt in jouw gemeente.</p>')+'</div></section>'+recruitment(m)
 return news.layout(heading,top+content+news.editorial.trustbar(),seo.view_path(m,view,day))
def activity(a,view):
 from urllib.parse import urlsplit
 link=a.get('url','');u=urlsplit(link)
 if u.scheme!='https' or not u.hostname or u.username or u.password:return ''
 url=news.e(link);title=news.e(a['title'])
 meta=' · '.join(str(x) for x in [a.get('timesText') or a.get('label'),a.get('locationName'),a.get('priceText')] if x)
 if view=='vandaag':
  return '<a class="activity-row" href="'+url+'"><span class="activity-day">'+a['date'][8:10]+'<small>'+a['date'][5:7]+'</small></span><span class="activity-row-copy"><span class="event-city">'+news.e(name(a['municipality']))+'</span><strong>'+title+'</strong><small>'+news.e(meta)+'</small><small>'+news.e(a.get('category',''))+' · '+news.e(name(a['municipality']))+'</small></span><span class="activity-open">Meer informatie ›</span></a>'
 images=a.get('images',[])[:1]
 gallery='<figure class="agenda-thumb">'+''.join('<a href="'+url+'" tabindex="-1" aria-hidden="true"><img src="'+news.e(i['url'])+'" alt="'+news.e(i['alt'])+'" loading="lazy" width="240" height="160"></a><figcaption>'+news.e(i['credit'])+'</figcaption>' for i in images)+'</figure>' if images else ''
 return '<article class="agenda-card app-agenda-card compact-agenda'+(' no-photo' if not images else '')+'">'+gallery+'<div class="agenda-item-copy"><span class="event-city">'+news.e(name(a['municipality']))+'</span><time datetime="'+news.e(a['date'])+'">'+news.date(a['date'])+'</time><h3><a href="'+url+'">'+title+'</a></h3><p>'+news.e(a['summary'])+'</p><a class="text-link" href="'+url+'">Meer informatie ›</a></div></article>'

def civic(x):
 return '<article class="agenda-card civic-card"><div class="calendar-date"><strong>'+x['date'][8:10]+'</strong><span>'+dict(zip(range(1,13),['JAN','FEB','MRT','APR','MEI','JUN','JUL','AUG','SEP','OKT','NOV','DEC']))[int(x['date'][5:7])]+'</span></div><div><p class="eyebrow">'+news.e(" / ".join(name(m) for m in x['municipalities']))+' · '+news.e(x['time'])+'</p><h3><a href="'+news.e(x['sourceUrl'])+'">'+news.e(x['title'])+'</a></h3><p>'+news.e(x['description'])+'</p><a class="button outline" href="'+news.e(x['sourceUrl'])+'">Bekijk bij de gemeente</a></div></article>'
def form(m=''):
 if search_visibility.public_facing():
  return news.layout('Meedoen met PITO Nieuws','<section class="article-wrap"><p class="eyebrow">PITO COMMUNITY</p><h1>Deel wat er speelt in jouw gemeente.</h1><p class="standfirst">Wil je bijdragen of een onderwerp onder de aandacht brengen? Neem contact op met PITO.</p><p>Vermeld je gemeente, het onderwerp en waar de informatie gecontroleerd kan worden. Publicatie volgt pas na beoordeling.</p><a class="button" href="https://pito.app/?page=contact">Contact met PITO</a></section>','/nieuws/meedoen')
 opts='<option value="">Kies jouw gemeente</option>'+''.join('<option value="'+x['slug']+'" '+('selected' if m==x['slug'] else '')+'>'+news.e(x['name'])+'</option>' for x in news.read('municipalities'))
 return news.layout('Word lokale redacteur','<section class="article-wrap"><p class="eyebrow">PITO COMMUNITY</p><h1>Maak jouw gemeente zichtbaar.</h1><p class="standfirst">Je hoeft geen beroepsjournalist te zijn. Nieuwsgierigheid, lokale kennis en zorgvuldigheid zijn een goed begin.</p><p>Iedere gemeente kan meerdere redacteurs hebben. Je naam verschijnt bij je goedgekeurde bijdrage; je e-mailadres blijft bij de redactie. De redactie controleert feiten, toon en rechten vóór plaatsing.</p><div class="editor"><form data-endpoint="/api/community/submit"><label>Ik wil<select name="kind"><option value="join">Meedoen als lokale redacteur</option><option value="story">Een communitybericht voorstellen</option></select></label><label>Gemeente<select name="municipality" required>'+opts+'</select></label><label>Jouw auteursnaam<input name="authorName" required maxlength="80" autocomplete="name"></label><label>E-mailadres voor contact<input name="email" type="email" required maxlength="200" autocomplete="email"></label><div data-community-join><label>Waarover wil je schrijven?<textarea name="motivation" maxlength="3000"></textarea></label></div><div data-community-story hidden><label>Titel<input name="title" maxlength="180"></label><label>Korte introductie<textarea name="summary" maxlength="500"></textarea></label><label>Jouw verhaal<textarea name="body" maxlength="12000"></textarea></label><label>Bronlink (optioneel)<input name="sourceUrl" type="url" placeholder="https://"></label><label>Hoe heb je dit gecontroleerd?<textarea name="evidence" maxlength="3000"></textarea></label></div><label class="checks"><input type="checkbox" name="confirmed" required> Ik stuur mijn eigen tekst in, mag die delen en begrijp dat mijn auteursnaam bij een goedgekeurd bericht wordt getoond.</label><p class="notice">Lokale proefomgeving: je inzending wordt alleen op deze computer opgeslagen. Er wordt geen e-mail verstuurd en niets direct openbaar geplaatst.</p><button>Bewaar aanmelding lokaal</button><p role="status" aria-live="polite"></p></form></div></section>','/nieuws/meedoen')
def submit(d):
 kind=d.get('kind');m=d.get('municipality')
 if kind not in ['join','story'] or m not in {x['slug'] for x in news.read('municipalities')}:raise ValueError('Kies een gemeente en type inzending')
 author=str(d.get('authorName','')).strip();email=str(d.get('email','')).strip()
 if not 1<=len(author)<=80 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>200 or d.get('confirmed') is not True:raise ValueError('Vul naam en e-mailadres in en bevestig je toestemming')
 a={'id':secrets.token_hex(12),'kind':kind,'municipality':m,'authorName':author,'email':email,'confirmed':True,'status':'pending','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'','reviewNote':''}
 for k,n in [('title',180),('summary',500),('body',12000),('evidence',3000),('motivation',3000),('sourceUrl',2000)]:
  value=str(d.get(k,'')).strip()
  if len(value)>n:raise ValueError('Een veld is te lang')
  a[k]=value
 if kind=='story' and not all(a[k] for k in ['title','summary','body','evidence']):raise ValueError('Vul titel, introductie, verhaal en broncontrole in')
 if kind=='join' and not a['motivation']:raise ValueError('Vertel kort waarover je wilt schrijven')
 if a['sourceUrl']:
  from urllib.parse import urlsplit
  u=urlsplit(a['sourceUrl'])
  if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Gebruik een openbare HTTPS-bronlink')
 data=records();data.append(a);store(data)
 return 'Lokaal ontvangen. Je inzending wacht op beoordeling; er is geen e-mail verstuurd.'
def moderate(d):
 data=records();a=next((a for a in data if a['id']==d.get('id')),None)
 if not a:raise ValueError('Inzending niet gevonden')
 if d.get('status') not in ['pending','approved','rejected']:raise ValueError('Onbekende status')
 if not str(d.get('reviewer','')).strip() or not str(d.get('reviewNote','')).strip() or d.get('confirmed') is not True:raise ValueError('Vul beoordelaar en motivering in en bevestig de controle')
 a.update(status=d['status'],reviewer=d['reviewer'].strip()[:100],reviewNote=d['reviewNote'].strip()[:2000],reviewedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 a.setdefault('reviews',[]).append({k:a[k] for k in ['status','reviewer','reviewNote','reviewedAt']});store(data)
 return 'Beoordeling lokaal opgeslagen. Alleen goedgekeurde verhalen zijn zichtbaar in Communitynieuws.'
def admin():
 cards=''
 for a in records():
  options=''.join('<option value="'+k+'" '+('selected' if a['status']==k else '')+'>'+v+'</option>' for k,v in [('pending','Te beoordelen'),('approved','Goedgekeurd'),('rejected','Afgewezen')])
  cards+='<article class="editor"><h3>'+news.e(a['title'] or 'Aanmelding lokale redacteur')+'</h3><p>'+byline(a)+' · '+news.e(a['email'])+'</p><p>'+news.e(a['summary'])+'</p><p style="white-space:pre-wrap">'+news.e(a['body'] or a['motivation'])+'</p><p>Broncontrole: '+news.e(a['evidence'])+'</p><p>'+news.e(a['sourceUrl'])+'</p><form data-endpoint="/api/community/review"><input type="hidden" name="id" value="'+a['id']+'"><label>Status<select name="status">'+options+'</select></label><label>Beoordelaar<input name="reviewer" required value="'+news.e(a['reviewer'])+'"></label><label>Motivering<textarea name="reviewNote" required>'+news.e(a['reviewNote'])+'</textarea></label><label class="checks"><input type="checkbox" name="confirmed" required> Feiten, rechten, privacy en auteursnaam gecontroleerd.</label><button>Bewaar beoordeling</button><p role="status" aria-live="polite"></p></form></article>'
 return '<section class="section"><h2>Community-inzendingen</h2><p>Aanmeldingen en verhalen zijn gescheiden. Een goedgekeurde aanmelding publiceert geen verhaal. Contactgegevens staan alleen hier, in deze lokale redactieomgeving.</p>'+ (cards or '<p>Nog geen aanmeldingen of verhalen.</p>')+'</section>'
