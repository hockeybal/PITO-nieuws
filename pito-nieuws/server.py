"""Loopback-only local extension; existing preview routes/assets remain intact."""
import importlib.util,json,os,secrets,threading,datetime
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote,urlencode
from http.server import ThreadingHTTPServer
from xml.sax.saxutils import escape as xml_escape
import news,community,seo
ROOT=Path(__file__).parent
base=Path(os.environ.get('PITO_BASE_PREVIEW') or (json.loads((ROOT/'base.json').read_text())['preview'] if os.environ.get('PITO_STANDALONE')!='1' and (ROOT/'base.json').is_file() else ROOT/'portable-assets'))
if os.environ.get('PITO_STANDALONE')=='1' or not (base/'server.py').is_file():
 import portable_handler as existing
else:
 spec=importlib.util.spec_from_file_location('pito_existing_preview',base/'server.py'); existing=importlib.util.module_from_spec(spec);spec.loader.exec_module(existing)
TOKEN=secrets.token_urlsafe(32);LOCK=threading.Lock()
def save(name,data):
 p=ROOT/'data'/(name+'.json');tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(p)
def inbox_form(x):
 options=''.join(f'<option value="{m["slug"]}">{news.e(m["name"])}</option>' for m in news.read('municipalities'))
 return f'''<article class="editor"><h3>{news.e(x['sourceTitle'])}</h3><p><a href="{news.e(x['sourceUrl'])}" target="_blank" rel="noopener">Open bron</a> · {news.e(x['sourcePublishedAt'])}</p><form data-endpoint="/api/news/create"><input type="hidden" name="signalId" value="{news.e(x['id'])}"><label>Eigen titel<input name="title" required maxlength="240"></label><label>Eigen samenvatting<textarea name="summary" required></textarea></label><label>Eigen artikel<textarea name="body" required></textarea></label><label>Gemeente<select name="municipality">{options}</select></label><label>Onderwerp<select name="category"><option>Bestuur</option><option>Verkeer</option><option>Veiligheid</option><option>Wonen</option><option>Samenleving</option></select></label><label>Gebeurtenisdatum (optioneel)<input type="date" name="eventDate"></label><label>Datumnotitie<input name="dateNote" required placeholder="Onderscheid publicatie en gebeurtenis"></label><button>Maak verborgen concept</button><p role="status" aria-live="polite"></p></form></article>'''
def ranking_form(a):
 r=a.get('ranking',{});parts=news.ranking.breakdown(a)
 audience_fields='<label>Informatiebehoefte<select name=rank_audienceNeed><option value="">Nog niet beoordeeld</option>'+''.join('<option value="'+k+'" '+('selected' if r.get('audienceNeed')==k else '')+'>'+news.e(v)+'</option>' for k,v in news.ranking.NEEDS.items())+'</select></label><label>Waarom helpt dit inwoners?<textarea name=rank_audienceReason>'+news.e(r.get('audienceReason'))+'</textarea></label>'
 audience_fields+=''.join('<label>'+label+'<input type=date name=rank_'+key+' value="'+news.e(r.get(key))+'"></label>' for key,label in [('actionFrom','Begindatum handeling of hinder'),('actionUntil','Einddatum handeling of hinder'),('alertCheckedOn','Waarschuwing gecontroleerd op')])
 audience_fields+='<label><input type=checkbox name=rank_alertConfirmed '+('checked' if r.get('alertConfirmed') else '')+'> Actieve waarschuwing bij bron bevestigd (alleen met goedgekeurd artikel en redacteur)</label>'
 fields=''.join('<label>'+news.e(label)+'<input type="number" min="0" max="5" name="rank_'+k+'" value="'+str(r.get(k,0))+'" required></label>' for k,label in news.ranking.LABELS.items())
 return '<fieldset class="ranking-box"><legend>Impactbeoordeling · '+str(news.ranking.score(a))+'/100 · '+news.e(news.ranking.importance(a))+'</legend><p>Voorlopige redactionele inschatting, geen gemeten bereik. Actualiteit: '+str(parts['freshness'])+'/15. Oude en verlopen meldingen krijgen geen urgentiepunten.</p><div class="score-fields">'+fields+'</div>'+audience_fields+'<label>Motivering<textarea name="rank_reason" required>'+news.e(r.get('reason',''))+'</textarea></label><label>Urgentie vervalt na<input type="date" name="rank_activeUntil" value="'+news.e(r.get('activeUntil',''))+'"></label><label>Dossier / dubbele berichtgeving<input name="rank_cluster" value="'+news.e(r.get('cluster',''))+'"></label><a href="/nieuws/selectie">Uitleg van de selectie</a></fieldset>'
def admin():
 cards=[]
 for a in news.read('articles'):
  options=''.join(f'<option value="{v}" {"selected" if a["reviewStatus"]==v else ""}>{label}</option>' for v,label in [('preview','Concept zichtbaar in lokale preview'),('approved','Menselijk goedgekeurd'),('draft','Concept verborgen'),('rejected','Afgewezen')])
  cards.append(f'''<article class="editor"><h2>{news.e(a['title'])}</h2><p><a target="_blank" rel="noopener" href="{news.e(a['sourceUrl'])}">{news.e(a['sourceName'])}</a> · Bronpublicatie: {news.date(a.get('sourcePublishedAt'))}</p><form><input type="hidden" name="slug" value="{news.e(a['slug'])}"><label>Titel<input name="title" value="{news.e(a['title'])}" required maxlength="240"></label><label>Samenvatting<textarea name="summary" required>{news.e(a['summary'])}</textarea></label><label>Artikel<textarea name="body" required>{news.e(a['body'])}</textarea></label><label>Betekenis voor inwoners<textarea name="impact">{news.e(a.get("impact"))}</textarea></label>{ranking_form(a)}<label>Status<select name="reviewStatus">{options}</select></label><label>Naam redacteur<input name="reviewer" value="{news.e(a.get('reviewer'))}" placeholder="Verplicht bij goedkeuring"></label><label>Controle / correctienotitie<input name="reviewNote" value="{news.e(a.get('reviewNote'))}" placeholder="Leg je controle of wijziging vast"></label><label class="checks"><input type="checkbox" name="confirmed"> Ik heb de bron, feiten, datering, privacy, eigen formulering en beeldrechten gecontroleerd.</label><button>Bewaar redactionele controle</button><p role="status" aria-live="polite"></p></form></article>''')
 inbox=news.read('inbox')
 incoming=''.join(f'<li><a href="{news.e(x["sourceUrl"])}" target="_blank" rel="noopener">{news.e(x["sourceTitle"])}</a> · {news.e(x.get("sourcePublishedAt"))} · {news.e(x["status"])}</li>' for x in inbox)
 incoming += ''.join(inbox_form(x) for x in inbox if x['sourceUrl'] not in {a['sourceUrl'] for a in news.read('articles')})
 reportpath=ROOT/'data/intake-report.json'
 report=json.loads(reportpath.read_text()) if reportpath.exists() else {}
 appitems,appstatus=news.app_content.get()
 content='<p class=notice>Gedeelde PITO-appagenda: '+news.e(appstatus)+' · '+str(len(appitems))+' activiteiten. Configuratie: PITO_APP_CONTENT_URL (server-side; bestaand PITO-contentcontract).</p><section class="section"><p class="eyebrow">LOKALE WERKOMGEVING</p><h1>Redactie.</h1><p class="standfirst">Van signaal naar een gecontroleerd verhaal.</p><p class="notice">Alle wijzigingen worden alleen lokaal opgeslagen. Goedkeuring publiceert niets op internet. De Strapi-import maakt uitsluitend concepten. Voor productie zijn inloggen, rollen en een gedeeld auditlog nodig.</p><p><a href=/nieuws/redactie/aanvoer>Nieuw: bronnen en automatische inname</a> · <a class=button href=/nieuws/redactie/overzicht>Brondekking & archiefopbouw</a> <a href=/nieuws/redactie/signalen>Alle broninboxen</a> <a href=/nieuws/seo-controle>SEO-controle</a></p><h2>Feedinbox</h2><p>'+str(len(inbox))+' signalen · laatste uitvoering: '+news.e(report.get('runAt','Nog niet uitgevoerd'))+'</p><details><summary>Bekijk binnengekomen signalen</summary><ul>'+incoming+'</ul></details><p>Bronkoppen worden hier alleen als redactioneel signaal getoond. Schrijf bij een signaal een eigen artikel. Nieuwe concepten blijven verborgen; herlaad deze pagina om ze onder Artikelcontrole te bekijken.</p><h2>Artikelcontrole</h2>'+''.join(cards)+'</section>'
 return news.layout('Redactie',community.admin()+content,'/nieuws/redactie').replace('</head>',f'<meta name="csrf" content="{TOKEN}"></head>')
class Handler(existing.Handler):
 server_version='PITO Local'
 sys_version=''
 def setup(self):
  super().setup()
  self.connection.settimeout(10)
 def end_headers(self):
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('X-Frame-Options','DENY')
  self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
  self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=(self)')
  self.send_header('Cross-Origin-Resource-Policy','same-origin')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
  if os.environ.get('PITO_SITE_MODE')!='production':
   self.send_header('X-Robots-Tag','noindex, nofollow')
  query=parse_qs(urlsplit(self.path).query)
  if any(query.get(k) for k in ('q','categorie','status','onderwerp')):
   self.send_header('X-Robots-Tag','noindex, follow')
  super().end_headers()

 def allowed(self):return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
 @__import__('strapi_news').coherent_request
 def do_GET(self):
  if not self.allowed():return self.send('Ongeldige host',status=403)
  u=urlsplit(self.path);p=unquote(u.path).rstrip('/') or '/';qs=parse_qs(u.query)
  if os.environ.get('PITO_SITE_MODE')=='production' and p!='/api/weather' and p.startswith(('/nieuws/redactie','/nieuws/onderzoek','/nieuws/beeldbibliotheek','/nieuws/seo-controle','/api/','/news-static/source-audit','/news-static/local-audit')):
   return self.send('Niet gevonden',status=404)
  if p=='/robots.txt':return self.send(__import__('search_visibility').robots_txt(),'text/plain; charset=utf-8')
  if p.startswith('/news-static/'):return self.file(ROOT/'static',p[len('/news-static/'):])
  if p=='/agenda/utrecht' or p.startswith('/agenda/utrecht/'):
   parts=p[len('/agenda/utrecht'):].strip('/').split('/') if p!='/agenda/utrecht' else []
   day=parts.pop() if parts and parts[-1] in ('vandaag','morgen','dit-weekend','binnenkort','deze-week') else ''
   m=parts[0] if len(parts)==1 else ''
   if len(parts)>1 or (m and m not in {x['slug'] for x in news.read('municipalities')}):return self.send('Gemeente niet gevonden',status=404)
   import agenda_views
   return self.send(agenda_views.page(m,'vandaag' if day and day!='deze-week' else 'agenda',day or 'vandaag',qs.get('categorie',[''])[0],qs.get('q',[''])[0],qs.get('pagina',['1'])[0],qs.get('maand',[''])[0]))
  if p.startswith('/activiteiten/'):
   activities,_=news.app_content.get()
   a=next((a for a in activities if seo.activity_path(a)==p),None)
   return self.send(seo.activity_detail(a) if a else news.layout('Activiteit niet gevonden','<section class="section"><h1>Activiteit niet gevonden</h1><a href="/agenda/utrecht">Bekijk de agenda</a></section>',p),status=200 if a else 404)
  if p=='/nieuws':return self.redirect(news.BASE)
  if p=='/nieuws/kies':
   m=qs.get('gemeente',[''])[0]
   if m and m not in {x['slug'] for x in news.read('municipalities')}:return self.send('Gemeente niet gevonden',status=404)
   if qs.get('weergave',[''])[0]=='adressen':
    import useful_addresses
    return self.redirect(useful_addresses.path(m))
   if qs.get('weergave',[''])[0]=='omgeving':return self.redirect(news.BASE+('/'+m if m else '')+'/omgevingszaken')
   if qs.get('weergave',[''])[0]=='wonen':return self.redirect(news.BASE+('/'+m if m else '')+'/wonen')
   if qs.get('weergave',[''])[0] in ('vandaag','agenda'):return self.redirect(seo.view_path(m,qs['weergave'][0],qs.get('dag',['vandaag'])[0])+('?' +urlencode({k:qs[k][0][:120] for k in ('categorie','q') if k in qs}) if any(k in qs for k in ('categorie','q')) else ''))
   query=urlencode({k:qs[k][0][:200] for k in ['periode','maand','sortering','q','onderwerp','weergave'] if k in qs})
   return self.redirect(news.BASE+('/'+m if m else '')+('?' +query if query else ''))
  if p=='/nieuws/redactie/bronnen':
   import source_overview
   return self.send(source_overview.page())
  if p=='/nieuws/redactie/gemeenten':
   import municipal_inventory
   return self.send(municipal_inventory.page())
  if p=='/nieuws/redactie/aanvoer':return self.send((ROOT/'source-intake-report.html').read_text())
  if p=='/nieuws/redactie/signalen':
   import signals
   try:page=int(qs.get('pagina',['1'])[0])
   except ValueError:page=1
   return self.send(signals.page(qs.get('type',['feeds'])[0],qs.get('gemeente',[''])[0],qs.get('q',[''])[0][:200],page))
  if p.startswith(news.BASE) and '/omgevingszaken' in p:
   import environment_notices
   region,tail=p.split('/omgevingszaken',1);m=region[len(news.BASE):].strip('/')
   if m and m not in {x['slug'] for x in news.read('municipalities')}:return self.send('Gemeente niet gevonden',status=404)
   if tail:
    r=next((r for r in environment_notices.records() if environment_notices.detail_path(r)==p),None)
    return self.send(environment_notices.detail(r) if r else 'Bekendmaking niet gevonden',status=200 if r else 404)
   phase=qs.get('status',[''])[0]
   if phase and phase not in environment_notices.STAGES:return self.send('Onbekende selectie',status=400)
   return self.send(environment_notices.page(m,qs.get('q',[''])[0][:200],phase,qs.get('maand',[''])[0][:7],qs.get('pagina',['1'])[0]))
  if p==news.BASE+'/wonen' or (p.startswith(news.BASE+'/') and p.endswith('/wonen')):
   import housing
   m=p[len(news.BASE):].strip('/').removesuffix('wonen').strip('/')
   if m and m not in {x['slug'] for x in news.read('municipalities')}:return self.send('Gemeente niet gevonden',status=404)
   return self.send(housing.page(m))
  if p.startswith('/nieuws/tips/'):
   import frontpage
   result=frontpage.tip_page(p[len('/nieuws/tips/'):])
   return self.send(result or 'Tip niet gevonden',status=200 if result else 404)
  if p.rstrip('/')=='/nieuws/praktisch':
   return self.send('Deze pagina is verwijderd.',status=410)
  if p=='/nieuws/seo-controle':
   import seo_review
   return self.send(seo_review.page())
  if p=='/nieuws/redactie/overzicht':
   import coverage
   return self.send(coverage.page())
  if p=='/api/weather':
   import weather
   return self.send(json.dumps({'html':weather.header()}),'application/json')
  if p=='/nieuws/net-binnen':
   import latest_news
   m=qs.get('gemeente',[''])[0]
   if m and m not in {x['slug'] for x in news.read('municipalities')}:return self.send('Onbekende gemeente',status=404)
   return self.send(latest_news.render(m,page=qs.get('pagina',['1'])[0]))
  if p=='/nieuws/agenda-beeldcredits':
   import agenda_images
   return self.send(agenda_images.credits())
  if p=='/nieuws/nuttige-adressen':
   import useful_addresses
   result=useful_addresses.page(qs.get('gemeente',[''])[0])
   return self.send(result or 'Niet gevonden',status=200 if result else 404)
  if p=='/nieuws/weer':
   import weather
   return self.send(weather.page())
  if p=='/nieuws/verantwoording':
   import legal
   return self.send(legal.page())
  if p=='/nieuws/bronberichten':
   import live_sources
   m=qs.get('gemeente',[''])[0]
   if m and m not in {x['slug'] for x in news.read('municipalities')}:return self.send('Gemeente niet gevonden',status=404)
   return self.send(live_sources.page(m,qs.get('q',[''])[0][:200],qs.get('pagina',['1'])[0]))
  if p=='/nieuws/aanvoerstatus':
   import live_sources
   return self.send(live_sources.status_page())
  if p=='/nieuws/over-de-redactie':return self.send(news.editorial.about())
  if p=='/nieuws/dossiers' or p.startswith('/nieuws/dossiers/'):
   import dossiers
   key=p[len('/nieuws/dossiers'):].strip('/');m=qs.get('gemeente',[''])[0]
   if (key and key not in dossiers.DOSSIERS) or (m and m not in {x['slug'] for x in news.read('municipalities')}):return self.send('Niet gevonden',status=404)
   return self.send(dossiers.page(key,m))
  if p.startswith(news.BASE+'/') and '/onderwerp/' in p:
   region,topic=p.split('/onderwerp/',1);m=region[len(news.BASE):].strip('/')
   category=next((k for k,v in seo.TOPICS.items() if v==topic),None)
   if not category or (m and m not in {x['slug'] for x in news.read('municipalities')}):return self.send('Niet gevonden',status=404)
   return self.send(news.home(m,qs.get('q',[''])[0][:200],category,'archive',qs.get('maand',[''])[0],qs.get('sortering',['latest'])[0],qs.get('pagina',['1'])[0],route_path=p))
  if p=='/nieuws/redactie/beeldonderzoek':
   import photo_research
   return self.send(photo_research.page())
  if p=='/nieuws/beeldbibliotheek':return self.send(news.image_library(qs.get('q',[''])[0][:150],qs.get('gemeente',[''])[0],qs.get('pagina',['1'])[0]))
  if p=='/api/media-library':return self.send(json.dumps({'images':news.read('images'),'scope':'local-preview','noRepeat':'assetId'}),'application/json')
  if p=='/nieuws/selectie':return self.send(news.selection())
  if p=='/nieuws/onderzoek':return self.send(news.research_page())
  if p=='/nieuws/meedoen':return self.send(community.form(qs.get('gemeente',[''])[0]).replace('</head>',f'<meta name="csrf" content="{TOKEN}"></head>'))
  if p.startswith('/nieuws/community/artikel/'):
   a=next((a for a in community.visible() if '/nieuws/community/artikel/'+a['id']==p),None)
   return self.send(community.detail(a) if a else 'Bericht niet gevonden',status=200 if a else 404)
  if p.startswith('/nieuws/weetjes/'):
   import facts
   a=next((a for a in facts.visible() if facts.BASE+a['slug']==p),None)
   return self.send(facts.detail(a) if a else 'Weetje niet gevonden',status=200 if a else 404)
  if p=='/nieuws/bronnen':return self.send(news.sources())
  if p=='/nieuws/redactie':return self.send(admin())
  if p=='/nieuws/gemeenten':
   import municipality_overview
   return self.send(municipality_overview.render())
  if p=='/nieuws/beeldverantwoording':
   import municipality_overview
   return self.send(municipality_overview.credits())
  if p=='/nieuws/feed.xml':
   m=qs.get('gemeente',[''])[0]
   if m and m not in {x['slug'] for x in news.read('municipalities')}:return self.send('Onbekende gemeente',status=404)
   origin=seo.origin()
   items=''.join('<item><title>'+xml_escape(a['title'])+'</title><link>'+origin+news.url(a)+'</link><guid isPermaLink="true">'+origin+news.url(a)+'</guid><description>'+xml_escape(a['summary'])+'</description></item>' for a in news.ranking.order(news.articles(),'latest') if news.selected(a,m) and news.ranking.is_recent(a))
   title='PITO Nieuws — provincie Utrecht' if news.search_visibility.production() else 'PITO Utrecht — lokale concepteditie'
   return self.send('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>'+title+'</title><link>'+origin+news.BASE+'</link><description>Nieuws met bronvermelding. De bronpublicatie en de publicatiedatum van PITO worden afzonderlijk bijgehouden.</description>'+items+'</channel></rss>','application/rss+xml; charset=utf-8')
  if p=='/nieuws/news-sitemap.xml':return self.send(seo.news_sitemap(),'application/xml')
  if p=='/nieuws/sitemap.xml':
   return self.send(seo.sitemap(),'application/xml')
  if p=='/api/news':return self.send(json.dumps({'articles':news.articles(),'municipalities':news.read('municipalities'),'meta':{'mode':'local-research-preview','asOf':'2026-10-10','archiveStart':'2026-04-10','coverage':'curated-not-exhaustive'}}),'application/json')
  if p.startswith(news.BASE+'/artikel/'):
   alias_file=ROOT/'data/article-aliases.json'
   aliases=json.loads(alias_file.read_text()) if alias_file.exists() else {}
   old_slug=p[len(news.BASE+'/artikel/'):]
   import strapi_news
   active={a['slug'] for a in news.articles()}
   target=strapi_news.redirect(old_slug) if strapi_news.enabled() else None
   # Preserve valid historical aliases, but never shadow a current CMS slug.
   if not target and old_slug not in active:
    target=aliases.get(old_slug)
    if target and strapi_news.enabled():target=strapi_news.redirect(target) or target
   if target and target in active:
    return self.redirect(news.BASE+'/artikel/'+target+('?' +u.query if u.query else ''),301)
   a=next((a for a in news.articles() if news.url(a)==p),None)
   key=qs.get('beeld',[''])[0]
   if a and key in news.media_library.candidates(a,news.read('images')):a=dict(a,_displayImageKey=key)
   return self.send(news.detail(a,qs.get('gemeente',[''])[0]) if a else news.layout('Niet gevonden','<section class="section"><h1>Bericht niet gevonden</h1><p>Dit artikel bestaat niet of is ingetrokken.</p></section>',p),status=200 if a else 404)
  if p==news.BASE or p.startswith(news.BASE+'/'):
   m=p[len(news.BASE):].strip('/')
   if m and m not in {x['slug'] for x in news.read('municipalities')}:return self.send('Gemeente niet gevonden',status=404)
   if qs.get('weergave',[''])[0]=='adressen':
    import useful_addresses
    return self.redirect(useful_addresses.path(m))
   if qs.get('weergave',[''])[0]=='omgeving':return self.redirect(news.BASE+('/'+m if m else '')+'/omgevingszaken')
   if qs.get('weergave',[''])[0]=='wonen':return self.redirect(news.BASE+('/'+m if m else '')+'/wonen')
   if qs.get('weergave',[''])[0] in ('vandaag','agenda'):return self.redirect(seo.view_path(m,qs['weergave'][0],qs.get('dag',['vandaag'])[0]),301)
   return self.send(news.home(m,qs.get('q',[''])[0][:200],qs.get('onderwerp',[''])[0],qs.get('periode',['all'])[0],qs.get('maand',[''])[0],qs.get('sortering',['relevance'])[0],qs.get('pagina',['1'])[0],qs.get('weergave',['nieuws'])[0],qs.get('dag',['vandaag'])[0]))
  return super().do_GET()
 def redirect(self,target,status=302):
  self.send_response(status);self.send_header('Location',target);self.end_headers()
 def file(self,basepath,rel):
  if Path(basepath)==ROOT/'static' and rel.endswith('.mp4'):
   target=(Path(basepath)/rel).resolve()
   if not target.is_relative_to((ROOT/'static').resolve()) or not target.is_file():return self.send('Niet gevonden',status=404)
   size=target.stat().st_size;start=0;end=size-1;partial=False
   requested=self.headers.get('Range','')
   if requested:
    import re
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
    if not match or not any(match.groups()):
     self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
    first,last=match.groups()
    if first:start=int(first);end=min(int(last),size-1) if last else size-1
    else:start=max(0,size-int(last))
    if start>end or start>=size:
     self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
    partial=True
   self.send_response(206 if partial else 200);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
   if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   self.end_headers()
   with target.open('rb') as stream:stream.seek(start);self.wfile.write(stream.read(end-start+1))
   return
  if Path(basepath)==base and rel=='index.html':
   html=(base/'index.html').read_text()
   # Add news access to the existing shell without rebuilding or replacing it.
   html=html.replace('<div class="pn-group pn-group--lokaal">','<a class="pn-destination pn-news-link" href="/nieuws/utrecht">Nieuws</a><div class="pn-group pn-group--lokaal">',1)
   return self.send(html)
  return super().file(basepath,rel)
 def do_POST(self):
  # Rejected bodies are deliberately not consumed; close the connection.
  self.close_connection=True
  if not self.allowed():return self.send('Ongeldige host',status=403)
  if os.environ.get('PITO_SITE_MODE')=='production':return self.send(json.dumps({'error':'Lokale bewerking is hier uitgeschakeld.'}),'application/json',403)
  if self.path not in ['/api/news/review','/api/news/create','/api/community/submit','/api/community/review']:return self.send(json.dumps({'error':'Endpoint niet gevonden.'}),'application/json',404)
  origin=self.headers.get('Origin','')
  try:
   if origin!=f'http://{self.headers.get("Host")}' or not secrets.compare_digest(self.headers.get('X-Pito-CSRF',''),TOKEN):return self.send(json.dumps({'error':'Ongeldig lokaal verzoek; herlaad de redactiepagina.'}),'application/json',403)
   if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1:raise ValueError('Ongeldige verzoeklengte')
   if self.headers.get_content_type()!='application/json':return self.send(json.dumps({'error':'Gebruik application/json.'}),'application/json',415)
   size=int(self.headers.get('Content-Length',0))
   if not 0<size<30000:raise ValueError('Ongeldige omvang')
   raw=self.rfile.read(size)
   if len(raw)!=size:raise ValueError('Onvolledig verzoek')
   try:d=json.loads(raw)
   except (ValueError,UnicodeDecodeError):raise ValueError('Ongeldig JSON-verzoek') from None
   if not isinstance(d,dict):raise ValueError('Verwacht een JSON-object')
   for key in ('slug','reviewStatus','reviewer','reviewNote','impact','signalId','municipality','category','dateNote','eventDate'):
    if key in d and not isinstance(d[key],str):raise ValueError('Ongeldig tekstveld: '+key)
   if urlsplit(self.path).path.startswith('/api/community/'):
    with LOCK:message=community.submit(d) if self.path=='/api/community/submit' else community.moderate(d)
    return self.send(json.dumps({'message':message}),'application/json')
   status=d.get('reviewStatus','draft')
   if status not in ['draft','preview','approved','rejected']:raise ValueError('Ongeldige status')
   for k in ['title','summary','body']:
    if not isinstance(d.get(k),str) or not d[k].strip():raise ValueError('Titel, samenvatting en artikel zijn verplicht')
   for key,limit in [('title',240),('summary',4000),('body',20000),('reviewer',120),('reviewNote',3000),('impact',5000)]:
    if len(d.get(key,''))>limit:raise ValueError('Een veld is te lang: '+key)
   if status=='approved' and not (d.get('confirmed') is True and d.get('reviewer','').strip() and d.get('reviewNote','').strip()):raise ValueError('Vul redacteur en controlenotitie in en bevestig de controle.')
   if urlsplit(self.path).path=='/api/news/create':
    with LOCK:
     signal=next((x for x in news.read('inbox') if x['id']==d.get('signalId')),None)
     if not signal:raise ValueError('Signaal niet gevonden')
     if d.get('municipality') not in {m['slug'] for m in news.read('municipalities')}:raise ValueError('Onbekende gemeente')
     if d.get('category') not in ['Bestuur','Verkeer','Veiligheid','Wonen','Samenleving']:raise ValueError('Onbekend onderwerp')
     if not d.get('dateNote','').strip():raise ValueError('Datumnotitie verplicht')
     if d.get('eventDate'):datetime.date.fromisoformat(d['eventDate'])
     data=news.read('articles')
     if any(a['sourceUrl']==signal['sourceUrl'] for a in data):raise ValueError('Voor deze bron bestaat al een artikel')
     source=next(s for s in news.read('sources') if s['id']==signal['sourceId'])
     a={k:d[k].strip() for k in ['title','summary','body','category','dateNote']}
     a.update(slug='bericht-'+signal['id'],municipalities=[d['municipality']],sourceUrl=signal['sourceUrl'],sourceName=source['name'],sourcePublishedAt=signal['sourcePublishedAt'],eventDate=d.get('eventDate') or None,verifiedAt=datetime.date.today().isoformat(),reviewStatus='draft',reviewer='',reviewNote='',priority=3,rights='Eigen samenvatting; rechtencontrole nog nodig.',sensitive=d['category']=='Veiligheid')
     data.append(a);save('articles',data)
     with (ROOT/'data/audit.jsonl').open('a') as f:f.write(json.dumps({'action':'create','after':a},ensure_ascii=False)+'\n')
    return self.send(json.dumps({'message':'Verborgen concept aangemaakt. Herlaad de redactiepagina om verder te controleren.'}),'application/json')
   with LOCK:
    data=news.read('articles');a=next((a for a in data if a['slug']==d.get('slug')),None)
    if not a:raise ValueError('Artikel niet gevonden')
    rank=None
    if any(k.startswith('rank_') for k in d):rank=news.ranking.validate({k[5:]:v for k,v in d.items() if k.startswith('rank_')})
    before=dict(a)
    if rank is not None:a['ranking']=rank
    for k in ['title','summary','body','reviewStatus','reviewer','reviewNote']:a[k]=d.get(k,'').strip()
    if 'impact' in d:a['impact']=d['impact'].strip()
    a['reviewedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    save('articles',data)
    with (ROOT/'data/audit.jsonl').open('a') as f:f.write(json.dumps({'at':a['reviewedAt'],'before':before,'after':a},ensure_ascii=False)+'\n')
   self.send(json.dumps({'message':'Lokaal opgeslagen. Er is niets openbaar gepubliceerd.'}),'application/json')
  except TimeoutError:self.send(json.dumps({'error':'Het verzoek duurde te lang.'}),'application/json',408)
  except (ValueError,TypeError,KeyError) as err:self.send(json.dumps({'error':str(err)}),'application/json',400)
if __name__=='__main__':
 if os.environ.get('PITO_SITE_MODE')=='production':
  raise SystemExit('Deze Python-server is alleen voor lokale preview. Gebruik voor live publicatie de productieapp met authenticatie en HTTPS.')
 port=int(os.environ.get('PORT','4198'));print(f'PITO Nieuws: http://127.0.0.1:{port}/nieuws/utrecht',flush=True)
 with ThreadingHTTPServer(('127.0.0.1',port),Handler) as http:
  try:http.serve_forever()
  except KeyboardInterrupt:print('\nDe lokale PITO-server is gestopt.',flush=True)
