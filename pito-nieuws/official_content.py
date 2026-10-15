"""Read the publication itself, never the surrounding website or inferred legal terms."""
import json, re, time
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request, urlopen
ROOT = Path(__file__).parent / 'data' / 'official-content'
class PublicationParser(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True); self.depth=0; self.blocks=[]; self.parts=[]; self.tag=None
 def flush(self):
  text=re.sub(r'\s+', ' ', ''.join(self.parts)).strip()
  if text:self.blocks.append({'kind':'heading' if self.tag in ('h1','h2','h3','h4') or (text.endswith(':') and len(text)<100) else 'paragraph','text':text})
  self.parts=[];self.tag=None
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag=='div':
   if self.depth:self.depth+=1
   elif 'officiele-publicatie' in attrs.get('class','').split():self.depth=1
  if not self.depth:return
  if tag in ('p','h1','h2','h3','h4','li','tr'):self.flush();self.tag=tag
  if tag in ('br','td','th'):self.parts.append(' ')
 def handle_endtag(self,tag):
  if not self.depth:return
  if tag in ('p','h1','h2','h3','h4','li','tr'):self.flush()
  if tag=='div':
   self.depth-=1
   if not self.depth:self.flush()
 def handle_data(self,text):
  if self.depth:self.parts.append(text)
def parse(html):
 p=PublicationParser();p.feed(html)
 if len(p.blocks)<2:raise ValueError('No substantive official publication found')
 return p.blocks
def cache_path(r):
 key=r.get('upstreamId','')
 if not re.fullmatch(r'[a-z]+-\d{4}-\d+',key):raise ValueError('Invalid official identifier')
 return ROOT/(key+'.json')
def read(r,fetch=False):
 try:
  file=cache_path(r)
  if file.exists():return json.loads(file.read_text())
  if not fetch:return None
  url='https://zoek.officielebekendmakingen.nl/'+r['upstreamId']+'.html'
  if url!=r['sourceUrl']:return None
  with urlopen(Request(url,headers={'User-Agent':'PITO-Nieuws/1.0'}),timeout=8) as response:
   if response.geturl()!=url:raise ValueError('Unexpected redirect')
   raw=response.read(3000001)
   if len(raw)>3000000:raise ValueError('Publication too large')
  return save(r,raw.decode('utf-8'))
 except (OSError,ValueError):return None
def save(r,html):
 data={'sourceUrl':r['sourceUrl'],'retrievedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'blocks':parse(html)}
 ROOT.mkdir(parents=True,exist_ok=True);file=cache_path(r);tmp=file.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(file)
 return data
def fields(data):
 blocks=data['blocks'];return {b['text'].rstrip(':').casefold():blocks[i+1]['text'] for i,b in enumerate(blocks[:-1]) if b['kind']=='heading' and blocks[i+1]['kind']=='paragraph'}
def presentation(r,data):
 f=fields(data);description=f.get('omschrijving van het verzoek');decision=decision_status(data);location=f.get('locatie',r['authority'])
 title=r['sourceTitle'];intro=''
 if description:
  subject=re.sub(r'^het nieuwbouwen van\s+', 'Nieuwbouw ', description, flags=re.I)
  subject=subject[0].upper()+subject[1:]
  title=subject+' — '+location
  if decision.lower()=='verleend':
   intro='De vergunning voor '+description.removeprefix('het ')+ ' aan '+location+' is verleend.'
  else:
   intro=subject+'. Locatie: '+location+'.'
   if decision:intro+=' Besluit: '+decision.lower()+'.'
 return title,intro,decision.lower()

def decision_status(data):
 # Only an explicit decision field or affirmative wording near the start.
 value=fields(data).get('genomen besluit op het verzoek','').strip().lower()
 if value in ('verleend','geweigerd','ingetrokken','vergunningvrij'):return value
 found=set()
 for b in data['blocks'][:10]:
  text=b['text'].casefold()
  if re.search(r'bezwaar|beroep|rechtsmiddel|voorlopige voorziening',text):break
  if re.search(r'\b(?:geweigerde omgevingsvergunning|vergunning[^.]{0,100}(?:is|wordt) geweigerd|besloten[^.]{0,100}te weigeren)',text):found.add('geweigerd')
  elif re.search(r'\b(?:verleende omgevingsvergunning|vergunning[^.]{0,100}(?:is|heeft|hebben) verleend|besloten[^.]{0,160}te verlenen)',text):found.add('verleend')
  elif re.search(r'\bingekomen aanvraag\b',text):found.add('aanvraag')
 return next(iter(found)) if len(found)==1 else ''
