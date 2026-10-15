"""Official club marks, kept separate from licensed editorial photographs."""
import json
from pathlib import Path
from media_library import club_mentions, article_topics
ROOT=Path(__file__).parent

def for_article(article, photo=None):
 if article.get('category')!='Sport':return None
 # Preserve a real photograph of the named club or an explicitly selected image.
 if photo and (photo.get('clubNames') or photo.get('articleSlugs') or photo.get('usageMode')=='editorial-choice'):return None
 try:clubs=json.loads((ROOT/'data/club-logos.json').read_text())
 except (OSError,ValueError):return None
 for text in (article.get('title',''),):
  matches=[c for c in clubs if c.get('enabled') and c.get('sport') in article_topics(article) and c['municipality'] in article.get('municipalities',[]) and club_mentions(text,c) and (ROOT/'static/images'/c['file']).is_file()]
  if len(matches)==1:return matches[0]
  if len(matches)>1:return None # A derby must not arbitrarily inherit one team's badge.
 return None
