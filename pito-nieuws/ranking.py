"""Explainable local editorial ranking. Scores are judgments, never audience measurements."""
import datetime, os
from zoneinfo import ZoneInfo
WEIGHTS={'impact':7,'reach':4,'urgency':3,'duration':2,'actionability':1} # 85 + freshness 15
LABELS={'impact':'Ernst van de gevolgen','reach':'Bereik onder inwoners','urgency':'Urgentie','duration':'Duur van de gevolgen','actionability':'Handelingsperspectief'}
def today():
 from seo import today as local_today
 return local_today()
def local_date(value):
 if not value:return ''
 if len(value)==10:return datetime.date.fromisoformat(value).isoformat()
 stamp=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
 if stamp.tzinfo is not None:stamp=stamp.astimezone(ZoneInfo('Europe/Amsterdam'))
 return stamp.date().isoformat()
def article_date(a):
 # Missing source dates stay missing in source attribution. The real first
 # PITO publication can still place an own report in the public selection.
 return local_date(a.get('sourcePublishedAt') or a.get('webPublishedAt') or '')
def chronology_key(a):
 # Prefer a real source timestamp when available; date-only source records
 # remain in their original day and never inherit their test-import time.
 value=a.get('sourcePublishedAtExact') or a.get('sourcePublishedAt') or a.get('webPublishedAt') or ''
 try:
  stamp=datetime.datetime.fromisoformat(value.replace('Z','+00:00')) if 'T' in value else datetime.datetime.combine(datetime.date.fromisoformat(value),datetime.time())
  if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=ZoneInfo('Europe/Amsterdam'))
  return (stamp.astimezone(datetime.timezone.utc).isoformat(),a.get('slug',''))
 except (ValueError,TypeError):return ('',a.get('slug',''))
def age(a):
 try:return (today()-datetime.date.fromisoformat(article_date(a))).days
 except ValueError:return 99999
def is_recent(a):return 0<=age(a)<=14

def breakdown(a):
 r=a.get('ranking',{});result={}
 for k,w in WEIGHTS.items():
  try:v=max(0,min(5,int(r.get(k,0))))
  except (ValueError,TypeError):v=0
  if k=='urgency' and (not is_recent(a) or (r.get('activeUntil') and r['activeUntil']<today().isoformat())):v=0
  result[k]=v*w
 d=age(a);result['freshness']=15 if 0<=d<=1 else 12 if 0<=d<=3 else 9 if 0<=d<=7 else 5 if 0<=d<=14 else 0
 return result

def score(a):return sum(breakdown(a).values())
def importance(a):
 v=a.get('ranking',{}).get('impact',0)
 return 'Zeer grote gevolgen' if v>=5 else 'Grote gevolgen' if v>=4 else 'Merkbare gevolgen' if v>=3 else 'Beperkte gevolgen'

def order(items,mode='relevance',diversify=True):
 # Cluster is editorial; identical source URLs also collapse. Newest version wins.
 dedup={}
 for a in sorted(items,key=lambda a:(article_date(a),a['slug']),reverse=True):
  key=a.get('ranking',{}).get('cluster') or a.get('sourceUrl') or a.get('documentId') or a['slug']
  if key not in dedup:dedup[key]=a
 scores={id(a):score(a) for a in dedup.values()}
 pending=sorted(dedup.values(),key=lambda a:(scores[id(a)],article_date(a),a['slug']),reverse=True)
 if mode=='relevance':return relevant_order(pending,diversify)
 if mode=='latest':return sorted(pending,key=chronology_key,reverse=True)
 if not diversify:return pending
 chosen=[];cats={};places={}
 # Small documented diversity penalty only for first three positions. Never adds irrelevant news.
 while pending and len(chosen)<3:
  def adjusted(a):
   location=tuple(sorted(a.get('municipalities',[])))
   return scores[id(a)]-min(8,4*cats.get(a['category'],0))- (min(6,3*places.get(location,0)) if len(location)==1 else 0)
  pick=max(pending,key=lambda a:(adjusted(a),scores[id(a)],article_date(a),a['slug']))
  pending.remove(pick);chosen.append(pick);cats[pick['category']]=cats.get(pick['category'],0)+1
  loc=tuple(sorted(pick.get('municipalities',[])));places[loc]=places.get(loc,0)+1
 return chosen+pending

def validate(r):
 if not isinstance(r,dict):raise ValueError('Ongeldige impactbeoordeling')
 out={}
 for k in WEIGHTS:
  v=r.get(k)
  if isinstance(v,bool) or not str(v).isdigit() or not 0<=int(v)<=5:raise ValueError('Impactvelden moeten 0–5 zijn')
  out[k]=int(v)
 out['reason']=str(r.get('reason','')).strip()[:1500]
 if not out['reason']:raise ValueError('Motiveer de impactbeoordeling')
 out['cluster']=str(r.get('cluster','')).strip()[:160]
 until=str(r.get('activeUntil') or '')
 if until:datetime.date.fromisoformat(until)
 out['activeUntil']=until or None
 out.update(validate_audience(r))
 return out

# v2: research-informed editorial policy, not a measured preference prediction.
POLICY_VERSION='local-needs-2026-10-v1'
NEEDS={'service':'Praktisch voor je dag','explanation':'Begrijp wat er verandert','participation':'Denk of beslis mee','connection':'Ken je omgeving'}

def validate_audience(r):
 need=str(r.get('audienceNeed') or '')
 if need and need not in NEEDS:raise ValueError('Onbekende informatiebehoefte')
 reason=str(r.get('audienceReason') or '').strip()[:1500]
 if need and not reason:raise ValueError('Licht de informatiebehoefte toe')
 out={'audienceNeed':need,'audienceReason':reason}
 for key in ['actionFrom','actionUntil','alertCheckedOn']:
  value=str(r.get(key) or '')
  if value:datetime.date.fromisoformat(value)
  out[key]=value or None
 if out['actionFrom'] and out['actionUntil'] and out['actionFrom']>out['actionUntil']:raise ValueError('Einddatum moet na begindatum liggen')
 out['alertConfirmed']=r.get('alertConfirmed') in (True,'on')
 if out['alertConfirmed'] and not (need=='service' and out['alertCheckedOn'] and out['actionFrom'] and out['actionUntil']):raise ValueError('Een waarschuwing vereist service, controle- en geldigheidsdatums')
 return out

def audience(a):
 try:return validate_audience(a.get('ranking',{}))
 except (ValueError,TypeError):return {} # malformed imports never get priority

def relevance_tier(a):
 r=audience(a);start=r.get('actionFrom');end=r.get('actionUntil')
 window=bool(start and end and start<=today().isoformat()<=end)
 if (is_recent(a) and a.get('reviewStatus')=='approved' and (a.get('humanReviewed') or a.get('reviewer')) and
     r.get('alertConfirmed') and r.get('alertCheckedOn')==today().isoformat() and window):return 3
 if is_recent(a) and start and end and r.get('audienceNeed') in ('service','participation'):
  days=(datetime.date.fromisoformat(start)-today()).days
  if end>=today().isoformat() and (window or 0<=days<=7):return 2
 return 1 if r.get('audienceNeed') else 0

def explanation(a):
 r=audience(a);tier=relevance_tier(a)
 prefix='Vandaag gecontroleerde waarschuwing' if tier==3 else 'Binnenkort iets om rekening mee te houden' if tier==2 else NEEDS.get(r.get('audienceNeed'),'Nog geen informatiebehoefte beoordeeld')
 return prefix+(' · '+r['audienceReason'] if r.get('audienceReason') else '')

def relevant_order(items,diversify=True):
 pending=list(items);chosen=[];cats={}
 # These values are fixed during one sort. Only the category count changes
 # while selecting the first six stories; the remaining order is a stable sort.
 values={id(a):(relevance_tier(a),int(is_recent(a)),
                int(a.get('ranking',{}).get('impact',0)),
                article_date(a),a['slug']) for a in pending}
 while pending and diversify and len(chosen)<6:
  def key(a):
   # Tiers protect verified warnings and time-bounded practical information.
   # Within a tier retain the existing category spread, consequence and date.
   v=values[id(a)]
   return v[:3]+(-cats.get(a.get('category'),0),)+v[3:]
  pick=max(pending,key=key);pending.remove(pick);chosen.append(pick)
  cats[pick.get('category')]=cats.get(pick.get('category'),0)+1
 return chosen+sorted(pending,key=lambda a:values[id(a)],reverse=True)


def province_frontpage(items):
 """Local club reports stay in their municipal edition; wider consequences lead."""
 pool=[a for a in items if a.get('editorialScope')!='municipal']
 return sorted(pool,key=lambda a:(relevance_tier(a),int(is_recent(a)),int(a.get('ranking',{}).get('impact',0)),int(len(a.get('municipalities',[]))>1),score(a),article_date(a)),reverse=True)
