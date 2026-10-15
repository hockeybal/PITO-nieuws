"""Burgernet v1.1 alert status metadata only. No names, pictures or public alerts."""
import datetime,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
URL='https://services.burgernet.nl/landactiehost/api/v1/alerts'
def parse(raw):
 if len(raw)>2_000_000:raise ValueError('Te groot')
 items=json.loads(raw)
 if not isinstance(items,list):raise ValueError('Onbekende response')
 rows=[]
 for item in items:
  if not all(k in item for k in ('AlertId','MessageId','Type','State','AlertLevel')):raise ValueError('Alert onvolledig')
  rows.append({'id':str(item['AlertId']),'messageId':str(item['MessageId']),'sourceId':'burgernet-kindalerts','type':item['Type'],'state':item['State'],'level':str(item['AlertLevel']),'activeCandidate':item['Type'] in ('Alert','Update') and item['State']=='Actual','publicationAllowed':False,'regionalGeometryPending':str(item['AlertLevel'])=='5'})
 return rows

def run():
 report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceUrl':URL,'publicAlerts':0}
 try:
  raw=subprocess.run(['curl','--fail','--silent','--show-error','--max-time','25','--max-filesize','2000000','-H','Accept: application/json',URL],capture_output=True,check=True).stdout
  rows=parse(raw);report.update(status='ok',received=len(rows))
  (ROOT/'data/amber-status.json').write_text(json.dumps({'checkedAt':report['runAt'],'alerts':rows},ensure_ascii=False,indent=2))
 except Exception as error:
  # Failure is unknown, never an all-clear. Previously stored state is NOT refreshed.
  report.update(status='error',error=str(error)[:300])
 (ROOT/'data/amber-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report));return report
if __name__=='__main__':run()
