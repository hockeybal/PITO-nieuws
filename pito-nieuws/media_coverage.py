"""Read-only coverage audit shared by the editorial image bank and CLI."""
import collections
import media_library

def audit(articles,library=None):
 library=media_library.load() if library is None else library
 usable={k:v for k,v in library.items() if media_library.eligible(v)}
 missing=[];topics=collections.Counter()
 for a in articles:
  if not media_library.candidates(a,usable):
   labels=sorted(media_library.article_topics(a));topics.update(labels)
   missing.append({'slug':a['slug'],'title':a['title'],'municipalities':a.get('municipalities',[]),'topics':labels})
 return {'eligiblePhotos':len({media_library.identity(m) for m in usable.values()}),'articlesChecked':len(articles),'articlesWithCandidate':len(articles)-len(missing),'missing':missing,'missingTopics':dict(topics.most_common()),'note':'Een kandidaat is nog geen goedkeuring voor het specifieke bericht. Exacte bronfoto gaat voor onderwerpstock; opnamedatum vanaf 2022; geen AI-fallback.'}
