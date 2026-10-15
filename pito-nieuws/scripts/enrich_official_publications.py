"""Warm the official publication cache; detail pages also fetch uncached publications."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import environment_notices as notices, official_content
from concurrent.futures import ThreadPoolExecutor
rows=notices.records()
if '--all' not in sys.argv:
 selected=[];counts={}
 for r in rows:
  m=r['municipality']
  if counts.get(m,0)<2:selected.append(r);counts[m]=counts.get(m,0)+1
 rows=selected
with ThreadPoolExecutor(max_workers=4) as pool:
 results=list(pool.map(lambda r:bool(official_content.read(r,fetch=True)),rows))
print({'requested':len(rows),'available':sum(results),'unavailable':len(rows)-sum(results)})
