"""Readable, paginated source queues for the local editorial team."""
import math
from urllib.parse import urlencode
import news,editorial,coverage
KINDS={'websites':('Lokale nieuwswebsites','regional-archive-inbox'),'gemeenten':('Gemeentelijke archieven','municipal-archive-inbox'),'feeds':('Nieuwsfeeds','inbox'),'raad':('Raadsvergaderingen','council-inbox'),'bekendmakingen':('Bekendmakingen','koop-inbox'),'verkeer':('Verkeerssignalen','ndw-inbox'),'incidenten':('VRU-incidenten','vru-inbox')}
def page(kind='feeds',m='',q='',page=1):
 kind=kind if kind in KINDS else 'feeds';label,file=KINDS[kind];rows=coverage.optional(file,[])
 rows=[r for r in rows if (not m or r.get('municipality')==m or r.get('sourceMunicipality')==m or m in r.get('municipalities',[]) or m in r.get('sourceMunicipalities',[]) or m in r.get('municipalityCandidates',[])) and (not q or q.casefold() in str(r).casefold())]
 datekey={'websites':'sourcePublishedAt','gemeenten':'sourcePublishedAt','feeds':'sourcePublishedAt','raad':'meetingAt','bekendmakingen':'sourcePublishedAt','verkeer':'startsAt','incidenten':'incidentAt'}[kind]
 rows.sort(key=lambda r:r.get(datekey) or '',reverse=True);total=len(rows);pages=max(1,math.ceil(total/30));page=max(1,min(pages,page));visible=rows[(page-1)*30:page*30]
 names={x['slug']:x['name'] for x in news.read('municipalities')}
 tabs='<nav class="signal-tabs">'+''.join('<a '+('aria-current="page" ' if k==kind else '')+'href="/nieuws/redactie/signalen?type='+k+'">'+v[0]+'</a>' for k,v in KINDS.items())+'</nav>'
 options='<option value="">Alle gemeenten</option>'+''.join('<option value="'+k+'" '+('selected' if k==m else '')+'>'+news.e(v)+'</option>' for k,v in names.items())
 form='<form class="signal-search" action="/nieuws/redactie/signalen"><input type="hidden" name="type" value="'+kind+'"><label>Gemeente<select name="gemeente">'+options+'</select></label><label>Zoek een onderwerp<input name="q" value="'+news.e(q)+'" placeholder="Bijvoorbeeld begroting of woningbouw"></label><button>Toon signalen</button></form>'
 prepared={a['sourceUrl']:a for a in news.articles()}
 cards=[]
 for row in visible:
  title=row.get('sourceTitle') or row.get('recordType') or 'Signaal';city=names.get(row.get('municipality') or row.get('sourceMunicipality'),'Geografie controleren')
  dt=row.get(datekey,'') or 'Datum controleren';date_label='Incidentdatum' if kind=='incidenten' else 'Vergaderdatum' if kind=='raad' else 'Start geldigheidsperiode' if kind=='verkeer' else 'Brondatum'
  article=prepared.get(row['sourceUrl']); status='ARTIKEL VOORBEREID' if article else 'CONTROLE NODIG'
  article_link='<p><a href="'+news.url(article)+'">Bekijk het eigen PITO-artikel</a></p>' if article else ''
  cards.append('<article class="signal-card"><p class="eyebrow">'+news.e(city)+' · '+status+'</p><h2>'+news.e(title)+'</h2><p class="byline">'+date_label+': '+news.e(dt)+'</p><p>'+news.e(row.get('note','Controleer primaire bron, plaats, datum en relevantie.'))+'</p><a href="'+news.e(row['sourceUrl'])+'" target="_blank" rel="noopener">Open de bron</a>'+('<a href="'+news.e(row['officialCouncilUrl'])+'">Officiële gemeenteraad</a>' if row.get('officialCouncilUrl') else '')+article_link+'</article>')
 links='<nav class="archive-pages" aria-label="Signaalpagina">'+''.join('<a '+('aria-current="page" ' if n==page else '')+'href="/nieuws/redactie/signalen?'+urlencode({'type':kind,'gemeente':m,'q':q,'pagina':n})+'">'+str(n)+'</a>' for n in sorted({1,pages,*range(max(1,page-2),min(pages,page+2)+1)}))+'</nav>'
 body=editorial.breadcrumb([('PITO','/'),('Redactie','/nieuws/redactie'),('Signalen','/nieuws/redactie/signalen')])+'<section class="section"><p class="eyebrow">VAN BRON NAAR VERHAAL</p><h1>De redactie-inbox.</h1><p class="standfirst">Onderzoek wat inwoners raakt. Deze signalen zijn nog geen nieuwsartikelen.</p>'+tabs+form+'<p>'+str(total)+' signalen in deze selectie · pagina '+str(page)+' van '+str(pages)+'</p><div class="notice">Dit zijn opgehaalde momentopnamen. Controleer de actuele primaire bron. Het gemeentefilter omvat ook het brongebied; de plaats van ieder bericht moet nog worden vastgesteld. Een lege selectie bewijst niet dat er geen ontwikkelingen zijn. Raadsdata zijn vergaderdata; verkeerskandidaten zijn nog niet aan gemeenten toegewezen.</div><div class="signal-grid">'+(''.join(cards) or '<p>Geen signalen in deze selectie. Controleer brondekking of kies een andere gemeente.</p>')+'</div>'+links+'<p><a href="/nieuws/redactie/aanvoer">Bronnen en automatische inname</a> · <a href="/nieuws/redactie/overzicht">Bekijk de brondekking</a> · <a href="/nieuws/redactie">Naar artikelcontrole</a></p></section>'
 return news.layout('Redactie-inbox · '+label,body,'/nieuws/redactie/signalen')
