"""De Bilt observations from KNMI's public table; server-side, ten-minute cache."""
import datetime as dt,json,re,threading,time
from html import escape,unescape
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
URL='https://www.knmi.nl/nederland-nu/weer/waarnemingen/'
CACHE=Path(__file__).parent/'data/weather-de-bilt.json'
TZ=ZoneInfo('Europe/Amsterdam');LOCK=threading.Lock();last_attempt=0
MONTHS='januari februari maart april mei juni juli augustus september oktober november december'.split()
def text(s):return ' '.join(unescape(re.sub('<[^>]+>',' ',s)).split())
def parse(html):
 stamp=re.search(r'Waarnemingen\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})\s+(\d\d):(\d\d)\s+uur',text(html))
 if not stamp:raise ValueError('Geen KNMI-meettijd')
 d,month,y,h,m=stamp.groups();measured=dt.datetime(int(y),MONTHS.index(month)+1,int(d),int(h),int(m),tzinfo=TZ)
 headers=None
 for table in re.findall(r'<table\b.*?</table>',html,re.S):
  heads=[text(x) for x in re.findall(r'<th\b[^>]*>(.*?)</th>',table,re.S)]
  if not heads or not heads[0].startswith('Station'):continue
  tempindex=next((i for i,x in enumerate(heads) if x.startswith('Temp') and 'C' in x),None)
  if tempindex is None:continue
  for row in re.findall(r'<tr\b.*?</tr>',table,re.S):
   cells=[text(x) for x in re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S)]
   if cells and cells[0]=='De Bilt':
    value=float(cells[tempindex].replace(',','.'))
    if not -50<=value<=60:raise ValueError('Onwaarschijnlijke temperatuur')
    return {'station':'De Bilt','temperature':value,'condition':cells[1], 'measuredAt':measured.isoformat(),'source':'KNMI','sourceUrl':URL,'fetchedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
 raise ValueError('De Bilt ontbreekt')
def refresh():
 global last_attempt
 if not LOCK.acquire(False):return
 try:
  if time.monotonic()-last_attempt<600:return
  last_attempt=time.monotonic()
  with urlopen(Request(URL,headers={'User-Agent':'PITO Nieuws weather/1.0 (De Bilt observation; 10-minute cache)'}),timeout=12) as r:
   raw=r.read(2000000).decode('utf-8')
  data=parse(raw);age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(data['measuredAt'])).total_seconds()
  if age < -300 or age>7200:raise ValueError('Bronmeting niet actueel')
  tmp=CACHE.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(CACHE)
 except Exception as exc:
  # Keep last verified observation; presentation independently limits its age.
  print('KNMI weer verversen mislukt:',type(exc).__name__,flush=True)
 finally:LOCK.release()
def get(refresh_allowed=True,now=None):
 if refresh_allowed and time.monotonic()-last_attempt>=600:threading.Thread(target=refresh,daemon=True).start()
 try:
  data=json.loads(CACHE.read_text());stamp=dt.datetime.fromisoformat(data['measuredAt']);age=((now or dt.datetime.now(dt.timezone.utc))-stamp).total_seconds()
  if age < -300 or age>7200:return {'status':'unavailable','station':'De Bilt','source':'KNMI'}
  return dict(data,status='fresh' if age<=1800 else 'stale')
 except (OSError,ValueError,KeyError,TypeError):return {'status':'unavailable','station':'De Bilt','source':'KNMI'}
def header():
 d=get();available=d['status']!='unavailable'
 value=(f"{d['temperature']:.1f}".replace('.',',')+'°C') if available else 'Weer'
 stamp=dt.datetime.fromisoformat(d['measuredAt']).astimezone(TZ).strftime('%H:%M') if available else ''
 title=('De Bilt · bron: KNMI · gemeten '+stamp+(' · vertraagde meting' if d['status']=='stale' else '')) if available else 'De Bilt · KNMI-meting tijdelijk niet beschikbaar'
 return '<a class="masthead-weather" href="/nieuws/weer" title="'+escape(title)+'" aria-label="'+escape(value+' · '+title)+'"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4a3 3 0 0 1 6 0v10a5 5 0 1 1-6 0Z"/><path d="M12 6v11"/><circle cx="12" cy="18" r="1"/></svg><span data-weather-temperature>'+value+'<small>De Bilt'+(' · vertraagd' if d['status']=='stale' else '')+'</small></span></a>'
def page():
 import news
 d=get();available=d['status']!='unavailable'
 content='<h1>Het weer in De Bilt</h1><p>De Bilt is het vaste meetpunt voor alle PITO Nieuws-edities.</p>'
 if available:
  stamp=dt.datetime.fromisoformat(d['measuredAt']).astimezone(TZ)
  content+='<p class="weather-temperature">'+str(d['temperature']).replace('.',',')+' °C</p><p>'+escape(d['condition'])+'</p><p>Gemeten op '+stamp.strftime('%d-%m-%Y om %H:%M')+' uur (Nederlandse tijd).</p>'
  if d['status']=='stale':content+='<p>De meting is vertraagd. Dit is de laatst beschikbare waarde.</p>'
 else:content+='<p>De actuele meting is tijdelijk niet beschikbaar. Bekijk het weer rechtstreeks bij het KNMI.</p>'
 content+='<p>Bron: <a href="'+URL+'">KNMI-waarnemingen</a>. Gemeten temperatuur, geen weersverwachting. Het weer kan elders in de provincie afwijken.</p><p>We controleren elke tien minuten op nieuwe gegevens. Na twee uur zonder recente meting tonen we geen temperatuur meer.</p><p><a href="https://www.knmi.nl/nederland-nu/weer/waarschuwingen/utrecht">Waarschuwingen voor Utrecht</a></p><p>Het KNMI is niet betrokken bij deze weergave en onderschrijft de strekking daarvan niet noodzakelijkerwijs. <a href="https://www.knmi.nl/copyright">Hergebruik KNMI-gegevens</a>.</p>'
 return news.layout('Weer in De Bilt','<article class="news-legal">'+content+'</article>','/nieuws/weer')
