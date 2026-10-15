"""Bounded DATEX II v3 intake. Stores candidates; never creates public alerts."""
import re,argparse,datetime,gzip,hashlib,io,json,subprocess,xml.etree.ElementTree as ET
if __package__:
 from .source_security import parse_xml
else:
 from source_security import parse_xml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
URL='https://opendata.ndw.nu/actueel_beeld.xml.gz'
MAX_XML=25_000_000

def local(tag):return tag.rsplit('}',1)[-1]
def values(node,name):return [x.text.strip() for x in node.iter() if local(x.tag)==name and x.text and x.text.strip()]
def first(node,name):return next(iter(values(node,name)),'')
def instant(value):
 try:
  dt=datetime.datetime.fromisoformat(re.sub(r'(\.\d{6})\d+',r'\1',value).replace('Z','+00:00'))
  return dt if dt.tzinfo else None
 except (ValueError,AttributeError):return None

def decode(raw):
 if raw[:2]==b'\x1f\x8b':
  with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:raw=stream.read(MAX_XML+1)
 if len(raw)>MAX_XML or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Onveilige of te grote XML')
 return raw

def parse(raw,now=None):
 root=parse_xml(decode(raw),MAX_XML);now=now or datetime.datetime.now(datetime.timezone.utc)
 if 'datex2.eu/schema/3/' not in root.tag:raise ValueError('Alleen gecontroleerd DATEX II v3-schema')
 published=instant(first(root,'publicationTime'))
 if not published or published>now+datetime.timedelta(minutes=10) or now-published>datetime.timedelta(hours=2):raise ValueError('Snapshot ontbreekt, is verouderd of ligt in de toekomst')
 result={};stats={'situations':0,'outsideCandidateArea':0,'nonReal':0,'expired':0,'invalidTime':0}
 for situation in (x for x in root.iter() if local(x.tag)=='situation'):
  stats['situations']+=1
  if first(situation,'informationStatus')!='real':stats['nonReal']+=1;continue
  if first(situation,'confidentiality') not in ('noRestriction',''):continue
  for record in (x for x in situation if local(x.tag)=='situationRecord'):
   coords=[]
   for line in values(record,'posList'):
    try:
     numbers=[float(x) for x in line.split()]
     coords.extend(zip(numbers[::2],numbers[1::2]))
    except ValueError:continue
   # Broad shortlist only: includes adjacent areas. Editor must establish Utrecht impact.
   if not any(51.80<=lat<=52.30 and 4.78<=lon<=5.68 for lat,lon in coords):stats['outsideCandidateArea']+=1;continue
   start=instant(first(record,'overallStartTime'));end=instant(first(record,'overallEndTime'))
   if not start:stats['invalidTime']+=1;continue
   if end and end<now:stats['expired']+=1;continue
   if end and end<start:stats['invalidTime']+=1;continue
   rid=record.attrib.get('id','');version=first(record,'situationRecordVersionTime')
   if not rid:continue
   row={'id':hashlib.sha256(rid.encode()).hexdigest()[:20],'upstreamId':rid,'sourceId':'ndw-datex3','sourceUrl':URL,'sourceName':first(record,'sourceName') or 'NDW','recordType':record.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type','').split(':')[-1],'versionTime':version,'snapshotAt':published.isoformat(),'startsAt':start.isoformat(),'endsAt':end.isoformat() if end else None,'timing':'planned' if start>now else 'within_validity_window','severity':first(situation,'overallSeverity'),'status':'needs_review','municipalities':[],'geography':'bounding_box_candidate_not_confirmed','note':'Geen openbare waarschuwing. Controleer wegvak, richting, hinder, Utrechtse relevantie en actuele status bij de wegbeheerder.'}
   if rid not in result or version>result[rid]['versionTime']:result[rid]=row
 return list(result.values()),stats

def run(file=None):
 raw=Path(file).read_bytes() if file else subprocess.run(['curl','--fail','--silent','--show-error','--max-time','30','--max-filesize','8000000',URL],capture_output=True,check=True).stdout
 rows,stats=parse(raw);report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceUrl':URL,'status':'ok','candidates':len(rows),'statistics':stats,'publicAlerts':0}
 for name,data in [('ndw-inbox',rows),('ndw-report',report)]:
  p=ROOT/'data'/(name+'.json');p.with_suffix('.tmp').write_text(json.dumps(data,ensure_ascii=False,indent=2));p.with_suffix('.tmp').replace(p)
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--file');args=ap.parse_args();run(args.file)
