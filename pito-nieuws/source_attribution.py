"""Public attribution is separate from the discovery/deduplication dossier."""
def public_sources(article):
    # Explicit selections are reviewed with the text; never truncate by count.
    candidates = article.get('publicSources')
    if candidates is None:
        candidates = [{'name': article['sourceName'], 'url': article['sourceUrl']}]
        candidates += [s for s in article.get('additionalSources', [])
                       if s.get('role') not in ('discovery', 'duplicate')]
    result, seen = [], set()
    for source in candidates:
        url = source.get('url', '')
        if url.startswith(('https://', 'http://')) and url not in seen:
            result.append(source)
            seen.add(url)
    return result
