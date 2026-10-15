"""Private newsroom view of evidence and coverage, no raw source prose."""
import news,json
from collections import Counter
def page():
 path=news.ROOT/'data/municipal-source-inventory.json'
 cities=json.loads(path.read_text()); e=news.e;articles={a['slug']:a for a in news.articles()}
 intro='<section class="section"><p class="eyebrow">REDACTIE · BRONKAART</p><h1>26 gemeenten. Per bron inzicht.</h1><p class="standfirst">11 juli–11 oktober 2026</p><p>Dit overzicht toont gevonden bronroutes en werkelijk voorbereide artikelen. Een gevonden link is geen werkende feed. De bronkaart en het driemaandsarchief zijn nog niet volledig.</p><p><a href="/nieuws/redactie/bronnen">Bronnen en aansluitplan</a> · <a href="/nieuws/redactie/aanvoer">Aanvoer en koppelingen</a> · <a href="/nieuws/utrecht">Nieuwssite bekijken</a></p>'
 nav='<nav aria-label="Gemeenten in bronkaart" class="inventory-nav">'+''.join('<a href="#'+m['municipality']+'">'+e(m['name'])+'</a>' for m in cities)+'</nav>'
 blocks=[]
 for m in cities:
  links=''.join('<li><a href="'+news.url(articles[s])+'">'+e(articles[s]['title'])+'</a></li>' for s in m['articleSlugs'] if s in articles)
  grouped={}
  for s in m['sources']:grouped.setdefault(s['topic'],[]).append(s)
  sourcehtml=''.join('<h3>'+e(topic)+'</h3><ul>'+''.join('<li><a href="'+e(s['url'])+'" rel="noopener" target="_blank">'+e(s['name'])+'</a><small>'+e(s['state'])+' · '+e(s['workflow'])+'</small></li>' for s in ss)+'</ul>' for topic,ss in grouped.items())
  blocks.append('<section class="inventory-city" id="'+m['municipality']+'"><h2>'+e(m['name'])+'</h2><p>'+str(m['articles'])+' zichtbare lokale concepten · '+e(' · '.join(k+': '+str(v) for k,v in sorted(m['monthly'].items())))+'</p><p><a href="/nieuws/utrecht/'+m['municipality']+'?periode=archive&sortering=latest">Nieuwsarchief bekijken</a></p><details><summary>Bronnen en verwerkingsstatus ('+str(len(m['sources']))+')</summary>'+sourcehtml+'</details><details><summary>Voorbereide artikelen</summary><ul>'+links+'</ul></details><details><summary>Openstaande dekking</summary><ul>'+''.join('<li>'+e(g)+'</li>' for g in m['gaps'])+'</ul></details></section>')
 css='<style>.inventory-nav{display:flex;flex-wrap:wrap;gap:8px;margin:24px 0}.inventory-nav a{padding:7px 12px;background:#f3f5f8;border-radius:4px}.inventory-city{padding:24px 0;border-top:1px solid #ddd;scroll-margin-top:140px}.inventory-city summary{cursor:pointer;padding:12px 0;font-weight:700}.inventory-city li{margin:10px 0}.inventory-city small{display:block;color:#656565}.inventory-city ul{padding-left:20px}</style>'
 return news.layout('Bronkaart Utrecht',css+intro+nav+''.join(blocks)+'</section>','/nieuws/redactie/gemeenten')
