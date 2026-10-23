"""Editorial overview; archives retain their independent paginated routes."""
import news, media_library, promotions, seo, facts, homepage_agenda, preferred_source

TOPICS=[('Bestuur','Politiek & bestuur','politiek'),('Veiligheid','Veiligheid','veiligheid'),('Wonen','Wonen & bouwen','wonen'),('Verkeer','Verkeer & OV','verkeer'),('Samenleving','Algemeen','buurt'),('Sport','Amateursport','sport')]
TIPS=[
 ('kennismaken-met-je-buren','Nieuw in de straat? Zo leer je je buren kennen','Een kleine kennismaking maakt de buurt vertrouwder.', ['Begin klein. Stel jezelf voor als je iemand op straat tegenkomt. Je hoeft niet meteen een hele buurtborrel te organiseren.','Nodig een paar buren uit voor koffie of een wandeling. Geef een concrete dag en tijd aan en maak duidelijk dat aansluiten vrijblijvend is.','Vraag welke activiteiten er al zijn. Een buurtmoestuin, een sportclub of een gezamenlijke opruimactie is een ontspannen manier om mensen te ontmoeten.','Maak afspraken voordat je iemand aan een buurtgroep toevoegt. Vraag toestemming en deel geen adressen of telefoonnummers van anderen.']),
 ('samen-iets-organiseren','Een buurtactiviteit organiseren: begin met deze vier stappen','Van een wandeling tot samen de straat opruimen.', ['Kies één eenvoudig idee en vraag een paar buren of zij mee willen doen. Een klein begin is makkelijker te organiseren en later uit te breiden.','Spreek een plek, tijd en taakverdeling af. Houd rekening met toegankelijkheid en met mensen die niet in een buurtapp zitten.','Controleer bij je gemeente welke regels voor de gekozen plek en activiteit gelden. Voor een evenement of het gebruik van de openbare ruimte kunnen voorwaarden gelden.','Vertel duidelijk wat deelnemers kunnen verwachten en of er kosten zijn. Deel na afloop alleen foto’s van deelnemers die dat goed vinden.']),
 ('lenen-in-de-buurt','Een ladder of boormachine lenen? Maak het makkelijk voor elkaar','Duidelijke afspraken houden lenen prettig.', ['Vraag eerst rond voordat je iets koopt dat je maar één keer nodig hebt. Noem wat je nodig hebt en voor hoe lang.','Spreek af wanneer je het voorwerp terugbrengt en bekijk samen de staat ervan. Vraag hoe je het veilig gebruikt.','Geef het schoon en compleet terug. Is er iets misgegaan? Vertel het meteen en bespreek samen een oplossing.','Help ook eens op een andere manier terug: een boodschap meenemen of planten water geven kan net zo welkom zijn.'])]

TIP_IMAGES=['utrecht-buurtstraat-2024','utrecht-park-2024','gereedschap-2024']
def tip_visual(index):
 media=news.read('images').get(TIP_IMAGES[index])
 if not media_library.eligible(media):return ''
 return '<figure class="tip-photo"><img src="/news-static/images/'+news.e(media['file'])+'" alt="'+news.e(media['alt'])+'" loading="lazy"><figcaption>Foto ter illustratie · <a href="'+news.e(media['sourceUrl'])+'">'+news.e(media['author'])+'</a> · <a href="'+news.e(media['licenseUrl'])+'">'+news.e(media['license'])+'</a> · uitsnede</figcaption></figure>'
def tips_block():
 cards=''.join('<article>'+tip_visual(i)+'<h3><a href="/nieuws/tips/'+slug+'">'+news.e(title)+'</a></h3><span class="tip-category">Samen in de buurt</span></article>' for i,(slug,title,_,__) in enumerate(TIPS))
 return '<section class="pito-tips" aria-labelledby="pito-tips-title"><header class="desk-heading"><h2 id="pito-tips-title">Tips van PITO</h2><span>Dichtbij begint met elkaar</span></header><div class="tips-row">'+cards+'</div></section>'

def tip_page(slug):
 tip=next((x for x in TIPS if x[0]==slug),None)
 if not tip:return None
 _,title,intro,paragraphs=tip
 body='<nav class="article-context"><a href="'+news.BASE+'">Nieuws uit Utrecht</a><a href="'+news.BASE+'#pito-tips-title">Tips van PITO</a></nav><article class="article-wrap"><p class="eyebrow">TIPS VAN PITO · SAMEN IN DE BUURT</p><h1>'+news.e(title)+'</h1><p class="standfirst">'+news.e(intro)+'</p>'+tip_visual(TIPS.index(tip))+'<div class="article-body">'+''.join('<p>'+news.e(p)+'</p>' for p in paragraphs)+'</div></article>'+promotions.ad('wide','collectieven')
 return news.layout(title,body,'/nieuws/tips/'+slug,intro)

def overview(allitems,m,controls):
 path=news.BASE+('/'+m if m else '')
 source_library=news.read('images')
 opening=(news.ranking.province_frontpage(allitems) if not m else allitems)[:4]
 used={a['slug'] for a in opening};sections=[]
 for category,label,key in TOPICS:
  group=sorted([a for a in allitems if a['category']==category and a['slug'] not in used],key=lambda a:news.article_date(a),reverse=True)[:9]
  # Keep a recent, genuinely relevant photograph as the section's visual anchor.
  photo=next((a for a in group[:5] if media_library.candidates(a,source_library)),None)
  if photo:group.remove(photo);group.insert(0,photo)
  used.update(a['slug'] for a in group)
  if group:sections.append((category,label,key,group))
 fact=facts.pick(m);library={k:v for k,v in source_library.items() if not v['file'].startswith('tip-') and k not in TIP_IMAGES}
 fact_media=library.get(fact.get('imageKey')) if fact else None
 if fact_media:library={k:v for k,v in library.items() if media_library.identity(v)!=media_library.identity(fact_media)}
 # Headline-only links must not consume photographs needed by visible cards.
 visual=opening+[a for _,_,_,g in sections for a in g[:5]]
 assigned={a['slug']:a for a in media_library.assign(visual,library)}
 selected=[assigned.get(a['slug'],dict(a,_displayImageKey='')) for a in opening+[a for _,_,_,g in sections for a in g]]
 opening=selected[:len(opening)];offset=len(opening)
 latest=sorted(allitems,key=news.ranking.chronology_key,reverse=True)[:4]
 timeline=''.join('<li><time>'+news.date(news.article_date(a))+'</time><a href="'+news.url(a)+'">'+news.e(a['title'])+'</a></li>' for a in latest)
 body='<div class="frontpage editorial-overview">'

 if opening:
  body+='<div class="news-opening"><div class="news-lead">'+news.card(opening[0],True)+'</div><aside class="news-latest"><h2>Net binnen</h2><ol class="timeline">'+timeline+'</ol><a class="text-link" href="'+path+'?periode=archive&sortering=latest">Meer nieuws ›</a></aside><div class="news-secondary">'+''.join(news.card(a) for a in opening[1:])+'</div></div>'

 else:body+='<p>Er zijn nog geen gecontroleerde berichten voor deze selectie.</p>'
 body+=homepage_agenda.block(m)
 for index,(category,label,key,group) in enumerate(sections):
  group=selected[offset:offset+len(group)];offset+=len(group)
  body+=topic_section(group,m,category,label,key,index)
  if category=='Sport':
   import club_directory
   body+=club_directory.block(m)
  if index==1:body+='<div class=home-app-break>'+promotions.ad('compact','app')+'</div>'
 import environment_notices
 body+=environment_notices.block(m)

 body+=tips_block()
 body+=facts.block(m) if fact else ''

 body+=__import__('useful_addresses').block(m)
 body+='<nav class="desk-bottom" aria-label="Verder ontdekken"><a href="'+path+'?periode=archive&sortering=latest">Alle nieuwsberichten ›</a><a href="'+seo.agenda_path(m)+'">Bekijk de lokale agenda ›</a></nav></div>'
 return media_library.deduplicate_images(body,source_library),selected


def topic_section(group,m,category,label,key,index=0,show_heading=True):
 names={x['slug']:x['name'] for x in news.read('municipalities')}
 def item(a,featured=False):
  card=news.card(a,featured)
  place=' · '.join(names.get(x,x) for x in a.get('municipalities',[])[:2]) or 'Provincie Utrecht'
  return card.replace('<div class="story-copy">','<div class="story-copy"><span class="story-location">'+news.e(place)+'</span>')
 feature=item(group[0],True)
 side=''.join(item(a) for a in group[1:5])
 more=''.join('<li><a href="'+news.url(a)+'">'+news.e(a['title'])+'</a><span>'+news.e(names.get((a.get('municipalities') or [''])[0],''))+'</span></li>' for a in group[5:])
 return '<section class="topic-desk" data-tone="'+'paper'+'" data-category="'+category+'" id="rubriek-'+key+'">'+('<header class="desk-heading"><h2>'+label+'</h2><a href="'+seo.topic_path(m,category)+'">Alles over '+label.lower()+' ›</a></header>' if show_heading else '')+'<div class="topic-composition"><div class="topic-feature">'+feature+'</div><div class="topic-briefs">'+side+'</div></div>'+('<ul class="topic-more">'+more+'</ul>' if more else '')+'</section>'
