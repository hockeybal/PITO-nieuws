"""PITO house ads: no trackers, paid targeting or external ad network."""
import news

CAMPAIGNS = {
 'vacatures': ('WERK DICHTBIJ', 'Jouw volgende stap.<br>Gewoon in de buurt.', 'Ontdek lokaal werk en de ondernemers achter de vacatures in PITO.', 'Bekijk lokale vacatures', '/#/vacatures', 'Minder reizen. Meer buurt.'),
 'aanbod': ('LOKAAL AANBOD', 'Om de hoek.<br>Voor jou.', 'Van een fijne winkel tot een nieuwe favoriet. Ontdek wat lokale ondernemers te bieden hebben.', 'Bekijk lokaal aanbod', '/#/aanbod', 'Koop dichtbij. Ontdek meer.'),
 'app': ('PITO APP', 'Meer buurt.<br>Meer beleven.', 'Een activiteit, een nieuwe ontmoeting of een fijne plek dichtbij. Jouw omgeving begint in PITO.', 'Ontdek de app', '/?page=download', 'Dichtbij begint hier.'),
 'collectieven': ('VOOR COLLECTIEVEN', 'Een buurt maak<br>je samen.', 'Breng buurtgenoten bij elkaar. Geef jullie activiteiten en initiatieven een plek in PITO.', 'Ontdek de mogelijkheden', '/organisaties', 'Samen in de buurt.'),
 'ondernemers': ('VOOR ONDERNEMERS', 'Jouw zaak.<br>In hun buurt.', 'Laat mensen uit de omgeving ontdekken wat jij te bieden hebt. Van winkel tot lokale dienst.', 'Bekijk PITO voor organisaties', '/organisaties', 'Lokaal gezien.'),
 'plek': ('LOKAAL ZICHTBAAR', 'Wil jij<br>hier staan?', 'Een plek voor ondernemers, collectieven en initiatieven uit de buurt.', 'Ontdek de mogelijkheden', '/organisaties', 'Jouw plek in PITO.'),
}

def ad(format='wide', campaign='app'):
 if campaign=='app':return app_display(format)
 label,title,description,cta,href,tagline=CAMPAIGNS[campaign]
 visual='<div class="campaign-landscape"></div><div class="campaign-phone"><div class="campaign-app-screen"></div></div><span class="campaign-sticker">Ontdek<br>je buurt.</span>'
 return ('<aside class="pito-house-ad ad-'+format+' campaign-'+campaign+'" aria-label="PITO advertentie: '+label.lower()+'">'
  '<div class="ad-copy"><small class="promotion-disclosure">Advertentie</small><span class="campaign-label">'+label+'</span><strong>'+title+'</strong><p>'+description+'</p><a href="'+href+'">'+cta+' <span aria-hidden="true">›</span></a></div>'
  '<div class="ad-visual" aria-hidden="true">'+visual+'<b>'+tagline+'</b></div></aside>').replace('ADVERTENTENTIERUIMTE','ADVERTENTIERUIMTE')

def display_rail():
 return '<div class="display-rail">'+ad('rail','ondernemers')+'<div class="display-follow">'+ad('rail','plek')+'</div></div>'

def article_navigation(a,municipality=""):
 import archive_navigation
 names={m['slug']:m['name'] for m in news.read('municipalities')}
 places=a.get('municipalities',[])
 m=municipality or (places[0] if places and not a.get('provinceWide') else '')
 city=names.get(m,'provincie Utrecht')
 nav='<nav class="article-context" aria-label="Navigatie bij dit artikel"><a class="context-home" href="'+news.BASE+('/'+m if m else '')+'">'+news.e(city)+' <span>Nieuws</span></a><a href="'+archive_navigation.link(m)+'">Alle berichten</a><a href="'+archive_navigation.link(m,a['category'])+'">'+news.e(news.CATEGORIES[a['category']])+'</a><a href="'+news.seo.agenda_path(m)+'">Agenda</a><a href="'+news.seo.agenda_path(m,'vandaag')+'">Vandaag te doen</a></nav>'
 local=sorted([x for x in news.articles() if x['slug']!=a['slug'] and (m in x.get('municipalities',[]) if m else True)],key=lambda x:x['sourcePublishedAt'],reverse=True)[:4]
 rows=''.join('<li><time>'+news.date(x['sourcePublishedAt'])+'</time><a href="'+news.url(x)+'">'+news.e(x['title'])+'</a></li>' for x in local)
 extra=''.join('<a href="'+news.BASE+'/'+p+'">'+news.e(names.get(p,p))+' ›</a>' for p in places if p!=m)
 sidebar='<aside class="article-rail"><section class="article-local"><h2>Net binnen</h2><p class="rail-location">'+news.e(city)+'</p><ol class="article-latest-timeline">'+rows+'</ol>'+extra+'<a class="rail-all" href="'+archive_navigation.link(m)+'">Meer net binnen →</a></section>'+ad('rail','plek')+'</aside>'
 return nav,sidebar


def store_links():
 return '<div class="pito-store-links"><a href="https://apps.apple.com/nl/app/pito-ontdek-je-buurt/id6762842018" aria-label="Download PITO in de App Store"><img src="/news-static/campaign/app-store-badge.png" alt="Download in de App Store"></a><a href="https://play.google.com/store/apps/details?id=pito.app" aria-label="Download PITO via Google Play"><img src="/news-static/campaign/google-play-badge-nl.png" alt="Ontdek het op Google Play"></a></div>'

def app_display(format='leaderboard'):
 return '<aside class="pito-house-ad app-campaign app-campaign-'+format+'" aria-label="Advertentie voor de PITO app"><div class="app-campaign-copy"><small class="promotion-disclosure">Advertentie</small><h2>Jouw buurt.<br>Op z’n best.</h2><p>Ontmoet je buren. Ontdek wat er speelt.</p><strong>Download de PITO app</strong>'+store_links()+'</div><img class="app-campaign-bird" src="/news-static/campaign/pito-wink-cutout-v1.png" alt="PITO, jouw buurtvogel"><img class="app-campaign-logo" src="/news-static/campaign/pito-logo.png" alt="PITO"></aside>'

def video_display(scene='kat',wing=False):
 asset='bordspel-v23' if scene=='kat' else scene
 film='pito-buurt-v23.mp4' if scene=='kat' else 'pito-complete-18s.mp4'
 headline='Een kleine hulp.<br>Een groot verschil.' if scene=='oppas' else 'Er gebeurt veel<br>in de buurt.'
 return '<aside class="pito-video-display '+('campaign-wing wing-'+scene if wing else 'campaign-inline-video')+'" aria-label="PITO app advertentie"><small class="promotion-disclosure">Advertentie</small><h2>'+headline+'</h2><div class="campaign-film"><video autoplay muted loop playsinline preload="metadata" poster="/news-static/campaign/'+asset+'.jpg" data-campaign-video src="/news-static/campaign/'+film+'" aria-label="PITO campagne: '+('buren vinden een oppas' if scene=='oppas' else 'bordspel en hulp van buurtgenoten')+'"></video><button type="button" class="campaign-play" aria-label="Video afspelen">Afspelen</button></div><a class="campaign-download" href="/?page=download">Ontdek de PITO app</a><span>Dichtbij begint met elkaar.</span></aside>'

def proposition(kind):
 items={
 'warmtepomp':('PITO WIJKCOLLECTIEVEN','Samen voor een<br>warmtepomp.','PITO bundelt aanvragen uit de buurt. HeatTransformers bekijkt wat bij jouw woning past.','Plan gratis advies','/#/collectieven/warmtepompcollectief','c9440ef71f7605f9968e.webp','Productvisualisatie warmtepomp bij een woning','Gratis en vrijblijvend. Jij beslist.'),
 'thuisbatterij':('PITO WIJKCOLLECTIEVEN','Samen voor een<br>thuisbatterij.','Via het PITO-wijkcollectief onderzoekt Domogo wat een thuisbatterij voor jouw woning kan betekenen.','Plan gratis advies','/#/collectieven/thuisbatterijcollectief','b9ca60aa9a0e3a462819.webp','Productvisualisatie thuisbatterij bij een woning','Gratis en vrijblijvend. Jij beslist.'),
 'stichtingen':('GRATIS VOOR STICHTINGEN','Zet jouw activiteit<br>op de kaart.','Informeer mensen uit de buurt. Vind deelnemers en vrijwilligers met PITO.','Maak gratis een account','/?page=account-stichting','f0110d8291b315cb7f0f.webp','Buurtbewoners ontmoeten elkaar tijdens het PITO-event','Ook voor verenigingen.'),
 'bedrijven':('PITO VOOR ONDERNEMERS','Jouw bedrijf.<br>Hier zichtbaar.','Laat buurtbewoners ontdekken wat jij te bieden hebt.','Ontdek de mogelijkheden','/organisaties?groep=bedrijven','8a89e376d5d97f2022e2.svg','Het team van Pompier begroet de buurt vanaf het terras','Dichtbij gevonden. Lokaal verbonden.')}
 label,title,body,cta,href,asset,alt,note=items[kind]
 benefits='<ul class="collective-benefits"><li>Aanvragen uit de buurt samen</li><li>Efficiënter plannen, mogelijk offertevoordeel</li><li>Eigen advies. Jij beslist.</li></ul>' if kind in ('warmtepomp','thuisbatterij') else ''
 return '<aside class="proposition proposition-'+kind+'" aria-label="Advertentie PITO '+kind+'"><div class="proposition-copy"><small class="promotion-disclosure">Advertentie</small><p class="proposition-label">'+label+'</p><h2>'+title+'</h2><p>'+body+'</p>'+benefits+'</div><a class="proposition-image" href="'+href+'" tabindex="-1" aria-hidden="true"><img src="/preview-assets/'+asset+'" alt="'+alt+'" loading="lazy"></a><div class="proposition-action"><a href="'+href+'">'+cta+' <span aria-hidden="true">›</span></a><p>'+note+'</p></div></aside>'

def wings():
 def slot(markup,name):return markup.replace('<aside ', '<aside data-ad-slot="'+name+'" ',1)
 return '<div class="campaign-wings segmented-wings" aria-label="Promotieblokken"><div class="campaign-column column-left">'+slot(video_display('oppas',True),'left-top')+slot(video_display('kat',True),'left-middle')+slot(proposition('stichtingen'),'left-bottom')+'</div><div class="campaign-column column-right">'+slot(proposition('warmtepomp'),'right-top')+slot(proposition('thuisbatterij'),'right-middle')+slot(proposition('bedrijven'),'right-bottom')+'</div></div>'


def article_app_banner():
 return '<aside class="article-app-banner" aria-label="Download de PITO app"><img src="/news-static/campaign/pito-wink-cutout-v1.png" alt="" loading="lazy"><div><strong>Open PITO. Ontdek je buurt.</strong><p>Activiteiten, ontmoetingen en nieuws dichtbij.</p>'+store_links()+'</div></aside>'


def download_closing():
 return '<aside class="download-closing" aria-label="Download PITO app"><div class="download-closing-copy"><span class="download-eyebrow">DOWNLOAD PITO APP</span><h2>Blijf op de hoogte<br>van jouw buurt.</h2><p>Ontdek wat er speelt in jouw gemeente.<br>Nieuws, activiteiten en mensen dichtbij.</p>'+store_links()+'<small>Gratis voor iPhone en Android</small></div><div class="download-closing-art"><img src="/news-static/campaign/pito-wink-cutout-v1.png" alt="PITO, jouw buurtvogel" loading="lazy"></div></aside>'


def community_display():
 return '<aside class="community-display" aria-label="PITO voor stichtingen"><div><span class="download-eyebrow">PITO VOOR STICHTINGEN</span><h2>Meer mensen.<br>Meer samen.</h2><p>Zet jouw activiteiten op de kaart en bereik mensen uit de buurt.</p><a href="https://pito.app/?page=account-stichting">Doe gratis mee <span aria-hidden="true">→</span></a></div><img src="/preview-assets/f0110d8291b315cb7f0f.webp" alt="Buurtbewoners ontmoeten elkaar tijdens een PITO-event" loading="lazy"></aside>'
