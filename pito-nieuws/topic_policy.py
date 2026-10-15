"""Provisional topic suggestions for private source queues, not inferred facts or ranking."""
import json,re
from pathlib import Path
ROOT=Path(__file__).parent
def policy():return json.loads((ROOT/'data/editorial-category-policy.json').read_text())
def suggest(title):
 text=(title or '').casefold()
 return [{'id':row['id'],'label':row['label'],'matchedTerms':[term for term in row['keywords'] if re.search(r'\b'+re.escape(term),text)],'status':'needs_review'} for row in policy()['categories'] if any(re.search(r'\b'+re.escape(term),text) for term in row['keywords'])]
