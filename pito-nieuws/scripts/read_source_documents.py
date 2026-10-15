"""Fetch private primary-source evidence. No text is published by this collector."""
import concurrent.futures,datetime,json,re,hashlib,time,argparse
from pathlib import Path
from municipal_archive_intake import fetch,date,ROOT
END=datetime.date.today().isoformat();START=(datetime.date.today()-datetime.timedelta(days=92)).isoformat()
def one(row):
 out=dict(row)
 try:
  soup,file=fetch(row['sourceUrl'])
  out['evidenceFile']=file;out['checkedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  h=soup.find('h1');meta_title=soup.find('meta',property='og:title');out['pageTitle']=(meta_title.get('content','') if meta_title else '') or (h.get_text(' ',strip=True) if h else '') or row.get('sourceTitle','')
  meta=soup.find('meta',property='article:published_time') or soup.find('meta',attrs={'name':'dcterms.date'})
  d=date(meta.get('content','')) if meta else None
  if not d:
   for script in soup.select('script[type="application/ld+json"]'):
    m=re.search(r'"datePublished"\s*:\s*"([^\"]+)"',script.get_text())
    if m:d=date(m[1]);break
  preferred_main=soup.select_one('[role="main"]') if 'www.derondevenen.nl/' in row['sourceUrl'] else None
  main=preferred_main or soup.select_one('.elementor-widget-theme-post-content, .entry-content, [itemprop="articleBody"], .article-body') or soup.find('article') or soup.find('main') or soup.find(id='content') or soup
  if not d:
   tm=soup.select_one('.published time, time[datetime], .date time')
   if tm:d=date(tm.get('datetime','') or tm.get_text(' ',strip=True))
  if not d:
   stamp=soup.select_one('.publication-date, .date-display-single, .news-date, .date.published')
   if stamp:d=date(stamp.get_text(' ',strip=True))
  if not d and 'www.hemurenge.nl/' in row['sourceUrl']:
   stamp=soup.select_one('.post-meta')
   if stamp:d=date(stamp.get_text(' ',strip=True))
  if not d:
   selector='.news-single-date' if 'www.leusden.nl/' in row['sourceUrl'] else '.elementor-post-info__item--type-custom' if 'www.omroepzout.nl/' in row['sourceUrl'] else None
   for stamp in soup.select(selector) if selector else []:
    d=date(stamp.get_text(' ',strip=True))
    if d:break
  if d:out['sourcePublishedAt']=d;out['dateEvidence']='source_page'
  for tag in main.select('nav,footer,header,script,style,form,aside,.breadcrumb,.breadcrumbs'):tag.decompose()
  rtv=soup.select('.api-text .text') if 'rtvutrecht.nl/' in row['sourceUrl'] else []
  paragraphs=[p.get_text(' ',strip=True) for p in rtv] if rtv else [p.get_text(' ',strip=True) for p in main.find_all('p')]
  # SRC uses a div with line breaks, not paragraph elements. Keep related-news lists out.
  if re.match(r'https://(?:www\.)?src\.fm/regionieuws/\d+/',row['sourceUrl']):
   content=soup.select_one('.three_quarter > .pushtop5.push20')
   stamp=soup.select_one('.three_quarter > .date-content')
   if content:
    paragraphs=[content.get_text(' ',strip=True)]
    if stamp:
     found=date(stamp.get_text(' ',strip=True))
     if found:out['sourcePublishedAt']=found;out['dateEvidence']='source_page'
  out['sourceParagraphs']=list(dict.fromkeys(p for p in paragraphs if len(p)>60))[:80]
  out['extractionVersion']='article-body-v2'
  out['readStatus']='read' if out['pageTitle'] and sum(map(len,out['sourceParagraphs']))>=180 else 'no_article_body'
  out['humanVerified']=False
  out['withinWindow']=bool(out.get('sourcePublishedAt') and START<=out['sourcePublishedAt']<=END)
 except Exception as e:out['readStatus']='error';out['error']=str(e)[:200]
 return out
def main():
 global START,END
 ap=argparse.ArgumentParser();ap.add_argument('--start',default=START);ap.add_argument('--end',default=END);ap.add_argument('--limit',type=int,default=100);ap.add_argument('--source');ap.add_argument('--retry',action='store_true');a=ap.parse_args()
 START=a.start;END=a.end
 if datetime.date.fromisoformat(START)>datetime.date.fromisoformat(END) or a.limit<1:ap.error('Ongeldige periode of limiet')
 target=ROOT/'data/source-documents.json'
 existing={r['sourceUrl']:r for r in json.loads(target.read_text())} if target.exists() else {}
 records={}
 for name in ['municipal-archive-inbox','inbox','regional-archive-inbox','sports-inbox']:
  path=ROOT/'data'/(name+'.json')
  if not path.exists():continue
  for row in json.loads(path.read_text()):
   if a.source and a.source not in row.get('sourceUrl',''):continue
   if row.get('sourcePublishedAt') and not START<=row['sourcePublishedAt'][:10]<=END:continue
   if not row.get('sourceUrl','').startswith('https://'):continue
   previous=existing.get(row['sourceUrl'],{})
   if previous.get('extractionVersion')=='article-body-v2' and not a.retry and (previous.get('readStatus')=='read' or previous.get('checkedAt','')[:10]==datetime.date.today().isoformat()):continue
   old=records.setdefault(row['sourceUrl'],dict(row))
   if not old.get('sourcePublishedAt') and row.get('sourcePublishedAt'):old['sourcePublishedAt']=row['sourcePublishedAt'];old['dateEvidence']='feed_timestamp'
   if not old.get('municipality') and row.get('sourceMunicipality'):old['municipality']=row['sourceMunicipality']
 # Round-robin by host prevents a large blocked publisher starving other sources.
 from urllib.parse import urlsplit
 groups={}
 for row in sorted(records.values(),key=lambda r:r.get('sourcePublishedAt') or '',reverse=True):groups.setdefault(urlsplit(row['sourceUrl']).netloc,[]).append(row)
 selected=[]
 while groups and len(selected)<a.limit:
  for host in list(groups):
   if len(selected)>=a.limit:break
   selected.append(groups[host].pop(0))
   if not groups[host]:del groups[host]
 statuses={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for row in pool.map(one,selected):
   existing[row['sourceUrl']]=row;statuses[row['readStatus']]=statuses.get(row['readStatus'],0)+1
 tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(list(existing.values()),ensure_ascii=False,indent=2));tmp.replace(target)
 report={'runAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'window':[START,END],'selected':len(selected),'remainingCandidates':max(0,len(records)-len(selected)),'statuses':statuses,'autoPublish':False}
 (ROOT/'data/source-read-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
