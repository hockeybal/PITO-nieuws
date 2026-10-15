"""Read-through adapter for PITO's shared app content; never creates a second agenda."""
import datetime,json,os,time,urllib.request
import seo
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).parent
CACHE={'at':0,'items':[],'status':'not_configured'}
def normalize(payload,asof):
 data=payload.get('data',payload);result=[];seen=set()
 if not isinstance(data,dict):raise ValueError('Expected shared PITO content object')
 for a in data.get('activities',[]):
  # Deliberately require the shared contract's publication flags. No fallback publication.
  if a.get('status')!='published' or a.get('show_on_web') is not True:continue
  aid=str(a.get('id',''));title=a.get('title');m=a.get('municipality','').lower().replace(' ','-');link=a.get('url','')
  u=urlsplit(link)
  if m not in {x['slug'] for x in json.loads((ROOT/'data/municipalities.json').read_text())}:continue
  if not aid or not title or u.scheme!='https' or not u.hostname or u.username or u.password:continue
  for o in a.get('occurrences',[]):
   day=o.get('date','')
   try:datetime.date.fromisoformat(day)
   except ValueError:continue
   key=(aid,day,o.get('times_text',''))
   if day<asof or key in seen:continue
   seen.add(key)
   images=[]
   for image in a.get('web_images',[])[:6]:
    iu=urlsplit(str(image.get('url','')))
    if image.get('web_usage_approved') is True and iu.scheme=='https' and iu.hostname and not iu.username and not iu.password and image.get('credit'):
     images.append({'url':image['url'],'alt':str(image.get('alt','')),'credit':str(image['credit'])})
   result.append({'images':images,'category':a.get('category',''),'timesText':o.get('times_text',''),'agendaHighlight':a.get('agendaHighlight',True),'id':aid,'kind':'activity','title':title,'municipality':m,'date':day,'occurrenceId':str(o.get('id') or ''),'occurrenceKey':str(o.get('id') or o.get('times_text','')),'startDate':o.get('startDate'),'endDate':o.get('endDate'),'locationName':a.get('locationName'),'address':a.get('address'),'organizer':a.get('organizer'),'priceText':a.get('priceText'),'cancelled':o.get('cancelled',False),'label':day+' · '+o.get('times_text',''),'summary':a.get('description',''),'sourceName':'PITO-app','url':link})
 return sorted(result,key=lambda a:a['date'])
def get():
 endpoint=os.environ.get('PITO_APP_CONTENT_URL','')
 if not endpoint:return local_preview(), 'local_preview'
 if time.time()-CACHE['at']<60:return CACHE['items'],CACHE['status']
 try:
  u=urlsplit(endpoint)
  if u.scheme!='https' and not (u.scheme=='http' and u.hostname in ['localhost','127.0.0.1']):raise ValueError('HTTPS required')
  headers={'Accept':'application/json'};token=os.environ.get('PITO_APP_CONTENT_TOKEN','')
  if token:headers['Authorization']='Bearer '+token
  req=urllib.request.Request(endpoint,headers=headers)
  with urllib.request.urlopen(req,timeout=5) as r:
   raw=r.read(2_000_001)
  if len(raw)>2_000_000:raise ValueError('Response too large')
  data=json.loads(raw);items=normalize(data,'1900-01-01') # Retain past detail pages; views filter current dates.
  CACHE.update(at=time.time(),items=items,status='connected')
 except Exception:CACHE.update(at=time.time(),items=[],status='unavailable')
 return CACHE['items'],CACHE['status']

def local_preview():
 """Existing user-owned import, clearly labelled as a snapshot rather than live data."""
 path=ROOT/'data/app-local-preview.json'
 if not path.exists():return []
 rows=[]
 for a in json.loads(path.read_text())['activities']:
  for o in a['occurrences']:
   rows.append(dict(a,kind='activity',date=o['date'],label=o.get('times_text') or 'Tijden bij de organisator',timesText=o.get('times_text',''),summary=a['description'],occurrenceKey=o.get('times_text','')))
 return rows
