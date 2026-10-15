"""Public local directory of official metadata, distinct from reported news."""
import json,re,math
from pathlib import Path
from urllib.parse import urlencode
import news,community,seo,starter,official_content
ROOT=Path(__file__).parent
STAGES={'vergunningvrij':'Vergunningvrij','procedure':'Procedure / termijn','aanvraag':'Aanvraag','ontwerp':'Ontwerp / inspraak','verleend':'Verleend','geweigerd':'Geweigerd','ingetrokken':'Ingetrokken','besluit':'Besluit','melding':'Melding','overig':'Bekendmaking'}
def path(m=''):return news.BASE+('/'+m if m else '')+'/omgevingszaken'
def stage(title):
 t=title.casefold()
 # Do not infer legal effect, deadlines or irreversibility from metadata.
 if re.search(r'verleng.*(?:termijn|beslis)|buiten behandeling|opschort',t):return 'procedure'
 if re.search(r'ingetrokken|intrekking',t):return 'ingetrokken'
 if re.search(r'geweigerd|weigering',t):return 'geweigerd'
 if re.search(r'ontwerp|voornemen|inspraak|zienswijz',t):return 'ontwerp'
 if re.search(r'verleend|verlening',t):return 'verleend'
 if re.search(r'vastgesteld|vaststelling|besluit',t):return 'besluit'
 if re.search(r'aanvraag|aangevraagd',t):return 'aanvraag'
 if re.search(r'melding|gemeld',t):return 'melding'
 return 'overig'
def records():
 municipalities={m['slug']:m['name'] for m in news.read('municipalities')};unique={}
 for r in news.read('koop-inbox'):
  if r.get('municipality') not in municipalities or r.get('authority','').casefold()!=municipalities[r['municipality']].casefold():continue
  if not re.fullmatch(r'https://zoek\.officielebekendmakingen\.nl/[a-z]+-\d{4}-\d+\.html',r.get('sourceUrl','')):continue
  if not '2026-07-13'<=r.get('sourcePublishedAt','')<=seo.today().isoformat():continue
  text=(r.get('type','')+' '+r.get('sourceTitle','')).casefold()
  if not re.search(r'omgevingsvergunning|omgevingsplan|omgevingsdocument|bestemmingsplan|ruimtelijk plan|bouwvergunning|sloopmelding|milieumelding',text):continue
  enriched=official_content.read(r)
  title,_,decision=official_content.presentation(r,enriched) if enriched else (r['sourceTitle'],'','')
  unique[r['sourceUrl']]={**r,'originalTitle':r['sourceTitle'],'sourceTitle':title,'stage':decision if decision in STAGES else stage(r['sourceTitle'])}
 return sorted(unique.values(),key=lambda r:(r['sourcePublishedAt'],r['id']),reverse=True)
def detail_path(r):return path(r['municipality'])+'/bekendmaking/'+r['id']
def card(r):
 return '<article class="environment-row"><div class="notice-date" aria-label="Publicatiedatum"><strong>'+r['sourcePublishedAt'][8:10]+'</strong><span>'+['jan','feb','mrt','apr','mei','jun','jul','aug','sep','okt','nov','dec'][int(r['sourcePublishedAt'][5:7])-1]+'</span></div><div class="notice-copy"><div class="environment-meta"><span class="environment-badge stage-'+news.e(r['stage'])+'">'+news.e(STAGES[r['stage']])+'</span><time datetime="'+news.e(r['sourcePublishedAt'])+'">'+news.date(r['sourcePublishedAt'])+'</time><span>'+news.e(r['authority'])+'</span></div><h3><a href="'+detail_path(r)+'">'+news.e(r['sourceTitle'])+'</a></h3><a class="environment-source" href="'+news.e(r['sourceUrl'])+'" target="_blank" rel="noopener">Officiële publicatie · Gemeente '+news.e(r['authority'])+' ›</a></div></article>'
def block(m=''):
 rows=[r for r in records() if not m or r['municipality']==m][:4]
 return '<section class="environment-home"><header class="desk-heading"><h2>Omgevingszaken</h2><a href="'+path(m)+'">Alle vergunningen & plannen ›</a></header><p>Bouwen, verbouwen en plannen in '+news.e(community.name(m) if m else 'de provincie Utrecht')+'. Rechtstreeks uit de officiële bekendmakingen.</p><div class="environment-grid">'+''.join(card(r) for r in rows)+'</div></section>'
def page(m='',q='',phase='',month='',page_number='1'):
 rows=[r for r in records() if (not m or r['municipality']==m) and (not q or q.casefold() in r['sourceTitle'].casefold()) and (not phase or r['stage']==phase) and (not month or r['sourcePublishedAt'].startswith(month))]
 try:n=max(1,int(page_number))
 except (ValueError,TypeError):n=1
 pages=max(1,math.ceil(len(rows)/24));n=min(n,pages);shown=rows[(n-1)*24:n*24];city=community.name(m) if m else 'provincie Utrecht'
 chips='<a '+('aria-current="page"' if not m else '')+' href="'+path()+'">Heel Utrecht</a>'+''.join('<a '+('aria-current="page"' if m==x['slug'] else '')+' href="'+path(x['slug'])+'">'+news.e(x['name'])+'</a>' for x in news.read('municipalities'))
 options='<option value="">Alle publicaties</option>'+''.join('<option value="'+k+'" '+('selected' if k==phase else '')+'>'+v+'</option>' for k,v in STAGES.items())
 months=sorted({r['sourcePublishedAt'][:7] for r in records()},reverse=True)
 monthopts='<option value="">Alle maanden</option>'+''.join('<option '+('selected' if v==month else '')+' value="'+v+'">'+{'07':'Juli','08':'Augustus','09':'September','10':'Oktober'}.get(v[5:],v[5:])+' '+v[:4]+'</option>' for v in months)
 form='<form class="environment-filters" action="'+path(m)+'"><label>Straat, buurt of onderwerp<input name="q" value="'+news.e(q)+'" placeholder="Bijvoorbeeld verbouwen of een straatnaam"></label><label>Soort publicatie<select name="status">'+options+'</select></label><label>Periode<select name="maand">'+monthopts+'</select></label><button>Zoeken</button><a href="'+path(m)+'">Wis filters</a></form>'
 nav=''.join('<a href="'+path(m)+'?'+news.e(urlencode({'q':q,'status':phase,'maand':month,'pagina':pn}))+'">'+label+'</a>' for pn,label in [(n-1,'‹ Vorige'),(n+1,'Volgende ›')] if 1<=pn<=pages)
 body=starter.compact(m,'omgeving')+community.tabs(m,'omgeving')+'<section class="environment-page"><p class="eyebrow">IN JOUW OMGEVING</p><h1>Omgevingszaken in '+news.e(city)+'</h1><p class="standfirst">Vergunningen, bouwplannen en inspraak. Bekijk wat er bij jou in de buurt is gepubliceerd.</p><details class="environment-municipalities"><summary>Kies je gemeente · '+news.e(city)+'</summary><nav aria-label="Gemeente voor omgevingszaken">'+chips+'</nav></details>'+form+'<p class="environment-explanation">Een aanvraag is nog geen toestemming. Het label volgt het expliciete besluit in de publicatie, of anders de titel. Bekijk het officiële document voor de actuele status, voorwaarden en eventuele reactie- of bezwaartermijn.</p><div class="environment-list">'+(''.join(card(r) for r in shown) or '<p>Geen bekendmakingen gevonden voor deze selectie. Pas je filters aan.</p>')+'</div><nav class="environment-pagination" aria-label="Meer bekendmakingen">'+nav+'</nav><p class="environment-explanation">Bron: Officiële bekendmakingen (KOOP). Gemeentelijke publicaties vanaf 13 juli 2026. Deze bronselectie is geen garantie op volledige dekking; enkele kleine routinemeldingen zijn bij de inname uitgefilterd.</p></section>'
 structured={'@context':'https://schema.org','@type':'CollectionPage','name':'Omgevingszaken in '+city,'url':seo.origin()+path(m),'mainEntity':{'@type':'ItemList','itemListElement':[{'@type':'ListItem','position':i,'url':seo.origin()+detail_path(r),'name':r['sourceTitle']} for i,r in enumerate(shown,1)]}}
 return news.layout('Omgevingszaken in '+city,body,path(m),'Officiële vergunningen, bouwplannen en omgevingspublicaties in '+city+'.',structured)
def detail(r):
 data=official_content.read(r,fetch=True)
 title,intro,decision=official_content.presentation(r,data) if data else (r['sourceTitle'],'','')
 phase=decision if decision in STAGES else r['stage']
 content=''
 if data:
  blocks=data['blocks']
  if blocks and blocks[0]['text']==r.get('originalTitle',r['sourceTitle']):blocks=blocks[1:]
  # Put the concrete project before reference numbers and procedural details.
  sections=[]
  for b in blocks:
   if b['kind']=='heading' or not sections:sections.append([])
   sections[-1].append(b)
  priority={'omschrijving van het verzoek':0,'genomen besluit op het verzoek':1,'locatie':2}
  sections=sorted(enumerate(sections),key=lambda pair:(priority.get(pair[1][0]['text'].rstrip(':').casefold(),3),pair[0]))
  blocks=[b for _,section in sections for b in section]
  for b in blocks:
   tag='h2' if b['kind']=='heading' else 'p'
   content+='<'+tag+'>'+news.e(b['text'].rstrip(':') if tag=='h2' else b['text'])+'</'+tag+'>'
 else:
  content='<p>De inhoud van deze bekendmaking is momenteel niet beschikbaar op PITO Nieuws. Bekijk het volledige bericht bij de gemeente via de bron hieronder.</p>'
 body=starter.compact(r['municipality'],'omgeving')+community.tabs(r['municipality'],'omgeving')+'<article class="article-wrap official-detail"><a href="'+path(r['municipality'])+'">Omgevingszaken '+news.e(r['authority'])+' ›</a><p class="eyebrow">OMGEVINGSZAKEN</p><p><span class="environment-badge stage-'+news.e(phase)+'">'+news.e(STAGES[phase])+'</span></p><h1>'+news.e(title)+'</h1><p class="article-meta">Gemeente '+news.e(r['authority'])+' · Gepubliceerd op '+news.date(r['sourcePublishedAt'])+'</p>'+('<p class="standfirst">'+news.e(intro)+'</p>' if intro else '')+'<div class="official-publication-body">'+content+'</div><p class="article-sources">Bron: <a href="'+news.e(r['sourceUrl'])+'" target="_blank" rel="noopener">Gemeente '+news.e(r['authority'])+' · officiële bekendmaking '+news.e(r['upstreamId'])+' ↗</a></p></article>'
 return news.layout(title,body,detail_path(r),intro or 'Officiële bekendmaking van gemeente '+r['authority']+'.')
