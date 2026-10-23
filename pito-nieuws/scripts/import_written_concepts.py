"""Import explicitly written concepts with immutable archived source evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from newsroom_worker import _atomic_json
from runtime_config import load_env_file
from source_archive import SourceArchive
from strapi_news import DraftClient, MUNICIPALITIES, CATEGORIES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder', type=Path, required=True)
    p.add_argument('--env-file', type=Path, required=True)
    args = p.parse_args(); load_env_file(args.env_file)
    queue = {r['n']:r for r in json.loads((args.folder/'authoring-queue.json').read_text())}
    decisions = json.loads((args.folder/'written-concepts.json').read_text())
    existing_path = args.folder/'written-concept-results.json'
    existing = json.loads(existing_path.read_text()) if existing_path.exists() else []
    done = {r['sourceUrl'] for r in existing}
    client = DraftClient.from_environment()
    for written in decisions:
        source = queue[written['n']]
        if source['url'] in done: continue
        assert written['category'] in CATEGORIES
        places = written.get('municipalities', [])
        assert set(places) <= MUNICIPALITIES
        assert places or (written.get('provinceWide') is True and written.get('provinceWideReason'))
        assert len(written['title']) <= 240 and len(written['summary']) >= 40 and len(written['body']) >= 180
        with SourceArchive(ROOT/'data') as archive:
            doc = archive.document(source['url'], source['revision'])
        assert doc and doc['sha256'] == source['sha256']
        identity = hashlib.sha256(source['url'].encode()).hexdigest()
        # URL identity is shared with the first manual Firecrawl concepts.
        payload = {'externalKey':'archive-editorial:'+identity, 'eventKey':'archive:'+identity,
            'title':written['title'], 'slug':written['slug'], 'summary':written['summary'],
            'body':written['body'], 'category':written['category'], 'municipalities':places,
            'provinceWide':bool(written.get('provinceWide')), 'sourceBased':True,
            'sourceUrl':source['url'], 'sourceName':source['sourceName'],
            'sourcePublishedAt':source['publishedAt'], 'dateNote':'Bronbericht van '+source['publishedAt'][:10]+'. Concept; nog niet menselijk beoordeeld.',
            'rights':'Eigen feitelijke samenvatting en parafrase; bronvermelding vastgelegd; geen bronbeeld overgenomen.',
            'sensitive':bool(written.get('sensitive')), 'origin':'writer', 'additionalSources':[],
            'imageTopics':written.get('imageTopics', []),
            'ranking':{'impact':2,'reach':2,'urgency':0,'duration':1,'actionability':1,
                'cluster':written['slug'],'audienceNeed':'explanation','audienceReason':'Nieuwe lokale broninformatie begrijpelijk samenvatten.'},
            'evidenceReference':'source-archive:'+source['revision'],
            'privateEvidence':{'archiveRevision':source['revision'],'sourceSha256':source['sha256'],
                'sourceCollectedAt':source['collectedAt'],'writer':'Codex, op expliciet verzoek; geen Grok-verzoek',
                'humanReviewed':False,'authoringQueueNumber':written['n']}}
        if written.get('eventDate'): payload['eventDate'] = written['eventDate']
        if written.get('provinceWideReason'): payload['provinceWideReason'] = written['provinceWideReason']
        result = client.submit_data(payload)
        existing.append(dict(result, slug=written['slug'], sourceUrl=source['url'], sourcePublishedAt=source['publishedAt']))
        _atomic_json(existing_path, existing); existing_path.chmod(0o600)
        file = args.folder/(written['slug']+'.txt')
        file.write_text(written['title']+'\n\n'+written['summary']+'\n\n'+written['body']
            +'\n\nBron: '+source['sourceName']+'\n'+source['url']+'\nBronpublicatie: '+source['publishedAt']+'\nStatus: concept.\n')
        file.chmod(0o600); done.add(source['url'])
    print(json.dumps({'writtenConceptsConfirmed':len(existing),'published':0,'writerApiRequests':0}))


if __name__ == '__main__': main()
