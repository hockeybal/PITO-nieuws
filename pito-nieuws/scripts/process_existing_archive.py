"""Consolidate every saved source offline, without date windows or publication.

Original evidence, editorial decisions and CMS data are never modified. Missing
evidence remains explicit. Source texts and own articles stay in separate tables.
"""
import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
from html import escape
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from newsroom_worker import extract_article
import publication

INBOXES = ('municipal-archive-inbox', 'regional-archive-inbox', 'inbox',
           'sports-inbox', 'vru-inbox', 'cms-source-inbox')


def read(path, default):
    return json.loads(path.read_text()) if path.is_file() else default


def canonical(value):
    if not isinstance(value, str):
        raise ValueError('Bronadres ontbreekt')
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Ongeldig openbaar bronadres')
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), p.query, ''))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def strings(value):
    return [value] if isinstance(value, str) else [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def process(root, output, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    data = root/'data'
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    registry = read(data/'newsroom/source-registry.json', read(data/'sources.json', []))
    sources = {s['id']: s for s in registry}
    municipalities = {m['slug']: m['name'] for m in read(data/'municipalities.json', [])}
    records, articles, rejected, inputs = {}, {}, [], {}
    raw_recovered = 0

    def record(url):
        key = canonical(url)
        return records.setdefault(key, dict(sourceUrl=key, sourceTitle='', sourceIds=[],
            municipalityCandidates=[], origins=[], dateObservations=[],
            evidenceFiles=[], issues=[], linkedArticles=[], previousDecisions=[],
            body='', bodyUsable=False, bodyEvidence=None, bodyRank=-1))

    def ingest(row, origin):
        try:
            r = record(row.get('sourceUrl'))
        except ValueError as error:
            rejected.append(dict(origin=origin, sourceUrl=row.get('sourceUrl'), reason=str(error)))
            return None
        r['origins'].append(origin)
        title = row.get('pageTitle') or row.get('sourceTitle') or row.get('title')
        if title:
            r['sourceTitle'] = title
        for key in ('sourceId', 'sourceIds'):
            r['sourceIds'].extend(strings(row.get(key)))
        for key in ('municipality', 'municipalities', 'municipalityCandidates',
                    'sourceMunicipality', 'sourceMunicipalities', 'coverageCandidates'):
            r['municipalityCandidates'].extend(x for x in strings(row.get(key)) if x in municipalities)
        date = row.get('sourceTimestamp') or row.get('sourcePublishedAt') or row.get('publishedAt')
        if date:
            r['dateObservations'].append(dict(value=date, evidence=row.get('dateEvidence', 'metadata'), origin=origin))
        if row.get('evidenceFile'):
            path = (root/row['evidenceFile']).resolve()
            # Treat filenames from imported records as data, never as unrestricted reads.
            available = path.is_relative_to(root.resolve()) and path.is_file()
            r['evidenceFiles'].append(dict(path=row['evidenceFile'], available=available))
        return r

    def body(r, doc, origin, rank, usable=True):
        text = doc.get('body', '')
        if not isinstance(text, str) or not text.strip():
            return
        if doc.get('sha256') and publication.body_digest(text) != doc['sha256']:
            r['issues'].append('body_digest_mismatch:'+origin)
            return
        if rank > r['bodyRank']:
            r.update(body=text, bodyUsable=usable, bodyEvidence=origin,
                     bodyRank=rank, sourceTitle=doc.get('title') or r['sourceTitle'])
            if doc.get('publishedAt'):
                r['selectedDate'] = doc['publishedAt']
                r['selectedDateEvidence'] = doc.get('dateEvidence', 'metadata')

    for name in INBOXES+('source-documents',):
        path = data/(name+'.json')
        rows = read(path, [])
        inputs[name] = len(rows)
        for row in rows:
            r = ingest(row, name)
            if r is None:
                continue
            paragraphs = [p.strip() for p in row.get('sourceParagraphs', []) if isinstance(p, str) and p.strip()]
            if paragraphs:
                text = '\n\n'.join(dict.fromkeys(paragraphs))
                usable = row.get('readStatus') == 'read' and len(text) >= 180
                body(r, dict(body=text, title=row.get('pageTitle'), publishedAt=row.get('sourcePublishedAt'),
                             dateEvidence=row.get('dateEvidence', 'metadata')), name, 20 if usable else 5, usable)
                if row.get('readStatus'):
                    r['originalReadStatus'] = row['readStatus']

    for url, decision in read(data/'source-decisions.json', {}).items():
        r = ingest(dict(decision, sourceUrl=url), 'source-decisions')
        if r is not None:
            r['previousDecisions'].append(decision)

    saved_documents = sorted((data/'newsroom/documents').glob('*.json'))
    inputs['saved-worker-documents'] = len(saved_documents)
    for path in saved_documents:
        doc = read(path, {})
        r = ingest(doc, 'saved-worker-document')
        if r is not None:
            body(r, doc, 'saved-worker-document', 40)
            r['collectedAt'] = doc.get('checkedAt')

    archive_path = data/'newsroom/source-archive.sqlite3'
    if archive_path.is_file():
        con = sqlite3.connect(archive_path.resolve().as_uri()+'?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        try:
            con.execute('BEGIN')
            queue = {row['url']: dict(row) for row in con.execute('SELECT * FROM queue')}
            inputs['firecrawlQueue'] = len(queue)
            for row in queue.values():
                metadata = json.loads(row['metadata'])
                r = ingest(dict(metadata, sourceUrl=row['url']), 'firecrawl-queue')
                if r is not None:
                    r['crawlStatus'] = row['status']
                    if row['error']:
                        r['crawlReason'] = row['error']
            for row in con.execute('SELECT source_key,url FROM source_links'):
                record(row['url'])['sourceIds'].append(row['source_key'])
            for row in con.execute('SELECT d.url,d.revision,r.document,r.collected_at FROM documents d JOIN revisions r ON r.revision=d.revision'):
                doc = json.loads(row['document'])
                r = ingest(dict(doc, sourceUrl=row['url']), 'versioned-source-archive')
                if r is not None:
                    body(r, doc, 'versioned-source-archive', 40)
                    r.update(archiveRevision=row['revision'], collectedAt=row['collected_at'])
            tables = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for row in con.execute('SELECT * FROM raw_pages') if 'raw_pages' in tables else []:
                r = record(row['url'])
                raw = bytes(row['html'])
                if hashlib.sha256(raw).hexdigest() != row['sha256']:
                    r['issues'].append('raw_digest_mismatch')
                    continue
                r['rawHtmlAvailable'] = True
                if r['bodyRank'] >= 40:
                    continue
                try:
                    doc = extract_article(raw, json.loads(queue[row['url']]['metadata']), now)
                except (ValueError, TypeError, KeyError) as error:
                    r['extractionIssue'] = str(error)
                    continue
                body(r, doc, 'saved-html-reparsed', 35)
                r['collectedAt'] = row['collected_at']
                raw_recovered += 1
        finally:
            con.close()

    article_inputs = [('local-preview', read(data/'articles.json', []))]
    article_inputs.extend((str(path.relative_to(root)), read(path, {}).get('articles', []))
                          for path in sorted((data/'newsroom').glob('*/strapi-preview.json')))
    for origin, rows in article_inputs:
        inputs[origin] = len(rows)
        for a in rows:
            if not a.get('slug'):
                continue
            identity = digest(a['slug']+'\n'+str(a.get('body', '')))
            own = articles.setdefault(identity, dict(id=identity, origins=[], article=a))
            own['origins'].append(origin)
            urls = [a.get('sourceUrl')]+[s.get('url') for s in a.get('additionalSources', []) if isinstance(s, dict)]
            for url in filter(None, urls):
                r = ingest(dict(sourceUrl=url), 'own-article-reference')
                if r is not None:
                    r['linkedArticles'].append(dict(id=identity, slug=a['slug'], title=a.get('title', ''),
                        savedStatus=a.get('reviewStatus', 'unknown'), origin=origin))

    hosts = defaultdict(set)
    for key, s in sources.items():
        for host in s.get('articleHosts', []) or [urlsplit(s.get('url', '')).hostname]:
            if host:
                hosts[host.lower()].add(key)
    same_body = {}
    for url, r in sorted(records.items()):
        r.pop('bodyRank')
        for key in ('sourceIds', 'municipalityCandidates', 'origins', 'issues'):
            r[key] = sorted(set(r[key]))
        r['registryHostCandidates'] = sorted(hosts.get(urlsplit(url).hostname, set()))
        r['linkedArticles'] = list({a['id']: a for a in r['linkedArticles']}.values())
        r['evidenceFiles'] = list({x['path']: x for x in r['evidenceFiles']}.values())
        r['dateObservations'] = list({json.dumps(x, sort_keys=True): x for x in r['dateObservations']}.values())
        day = r.pop('selectedDate', None)
        evidence = r.pop('selectedDateEvidence', None)
        dates = []
        for observation in r['dateObservations']:
            try:
                parsed = publication._date(observation['value'])
                if parsed > now+dt.timedelta(minutes=5):
                    r['issues'].append('future_publication_date')
                else:
                    dates.append(observation)
            except (ValueError, TypeError):
                r['issues'].append('invalid_publication_date')
        if not day and dates:
            preferred = next((x for x in dates if x['evidence'] == 'source_page'), dates[0])
            day, evidence = preferred['value'], preferred['evidence']
        r['sourcePublishedAt'], r['dateEvidence'] = day, evidence
        if len({x['value'][:10] for x in dates}) > 1:
            r['issues'].append('conflicting_date_observations')
        if r['body']:
            r['bodySha256'] = digest(r['body'])
            if r['bodyUsable']:
                previous = same_body.setdefault(r['bodySha256'], url)
                if previous != url:
                    r['sameBodyAs'] = previous
            if r['bodyEvidence'] == 'source-documents' and not any(x['available'] for x in r['evidenceFiles']):
                r['issues'].append('original_html_missing')
        decision_statuses = {d.get('status') for d in r['previousDecisions']}
        title = r['sourceTitle'].strip().lower()
        is_index = title in ('home', 'nieuws', 'nieuwsoverzicht', 'nieuws | gemeente bunschoten') and urlsplit(url).path.rstrip('/') in ('', '/nieuws', '/nieuwsoverzicht')
        if r['linkedArticles']:
            status = 'existing_own_article'
        elif decision_statuses & {'excluded', 'not_article', 'needs_fact_check'}:
            status = next(s for s in ('needs_fact_check', 'not_article', 'excluded') if s in decision_statuses)
        elif is_index or r.get('crawlStatus') == 'index':
            status = 'not_article'
        elif not r['bodyUsable']:
            status = 'source_text_missing'
        elif not day or any(x in r['issues'] for x in ('invalid_publication_date', 'future_publication_date', 'conflicting_date_observations')):
            status = 'date_review'
        elif r.get('sameBodyAs'):
            status = 'duplicate_body_review'
        else:
            status = 'available_source_text'
        r.update(processingStatus=status, publicationAllowed=False, humanVerified=False)

    rows = sorted(records.values(), key=lambda r: (r['sourcePublishedAt'] or '', r['sourceUrl']), reverse=True)
    # Structured events have individual upstream identities. In particular, all
    # NDW events share a feed URL: deduplicating those by URL would lose records.
    signals = {}
    signal_types = {'koop-inbox': 'official_notice_requires_primary_document',
                    'council-inbox': 'meeting_is_not_a_decision',
                    'ndw-inbox': 'historical_traffic_snapshot'}
    for name, kind in signal_types.items():
        items = read(data/(name+'.json'), [])
        inputs[name] = len(items)
        for item in items:
            try:
                url = canonical(item.get('sourceUrl'))
            except ValueError as error:
                rejected.append(dict(origin=name, sourceUrl=item.get('sourceUrl'), reason=str(error)))
                continue
            identity = name+':'+str(item.get('upstreamId') or item.get('entityId') or item.get('id') or digest(json.dumps(item, sort_keys=True)))
            # Keep changed payloads as separate historical versions as well.
            key = digest(identity+'\n'+json.dumps(item, sort_keys=True))
            signals[key] = dict(id=key, upstreamIdentity=identity, kind=kind, sourceUrl=url,
                title=item.get('sourceTitle') or item.get('recordType') or identity,
                sourceRecordUrl=url if url in records else None,
                primaryTextAvailable=records.get(url, {}).get('bodyUsable', False),
                original=item, publicationAllowed=False, humanVerified=False)
    counts = dict(Counter(r['processingStatus'] for r in rows))
    source_counts = []
    for key, s in sorted(sources.items()):
        related = [r for r in rows if key in r['sourceIds']]
        source_counts.append(dict(sourceKey=key, name=s.get('name', key), url=s.get('url'),
            linkedUrls=len(related), usableTexts=sum(r['bodyUsable'] for r in related),
            counts=dict(Counter(r['processingStatus'] for r in related))))
    valid_days = sorted(r['sourcePublishedAt'][:10] for r in rows if r['sourcePublishedAt'])
    report = dict(processedAt=now.isoformat(), scope='Volledig bestaand lokaal bronarchief; geen periodefilter',
        inputs=inputs, registeredSources=len(sources), uniqueSourceUrls=len(rows), recordsProcessed=len(rows),
        documentsWithText=sum(bool(r['body']) for r in rows), usableSourceTexts=sum(r['bodyUsable'] for r in rows),
        recoveredFromSavedHtml=raw_recovered, ownArticleVersions=len(articles), counts=counts,
        sourceDateRange=[valid_days[0], valid_days[-1]] if valid_days else [],
        recordsWithMissingOriginalHtml=sum('original_html_missing' in r['issues'] for r in rows),
        recordsWithDateConflicts=sum('conflicting_date_observations' in r['issues'] for r in rows),
        existingArticleReferencesWithoutSourceText=sum(r['processingStatus'] == 'existing_own_article' and not r['bodyUsable'] for r in rows),
        structuredSignalRecords=len(signals), structuredSignalCounts=dict(Counter(s['kind'] for s in signals.values())),
        rejectedRecords=rejected, allSavedInputsProcessed=True, publicationReady=False,
        firecrawlRequests=0, writerRequests=0, cmsWrites=0, published=0)
    write_json(output/'processing-report.json', report)
    write_json(output/'source-coverage.json', source_counts)
    write_json(output/'records.json', rows)
    write_json(output/'own-articles.json', list(articles.values()))
    write_json(output/'signal-records.json', list(signals.values()))
    # This queue carries actual saved texts and provenance, without granting approval.
    write_json(output/'writing-queue.json', [r for r in rows if r['processingStatus'] in
               ('available_source_text', 'date_review', 'duplicate_body_review', 'needs_fact_check')])
    write_json(output/'recovery-queue.json', [r for r in rows if not r['bodyUsable'] and
               r['processingStatus'] not in ('excluded', 'not_article')])
    temporary = output/'archive.tmp'
    if temporary.exists():
        temporary.unlink()
    db = sqlite3.connect(temporary)
    with db:
        db.execute('CREATE TABLE sources(url TEXT PRIMARY KEY,title TEXT,published_at TEXT,status TEXT,body TEXT,metadata TEXT)')
        db.execute('CREATE TABLE own_articles(id TEXT PRIMARY KEY,slug TEXT,body TEXT,metadata TEXT)')
        db.execute('CREATE TABLE signals(id TEXT PRIMARY KEY,upstream_identity TEXT,kind TEXT,source_url TEXT,metadata TEXT)')
        db.executemany('INSERT INTO sources VALUES(?,?,?,?,?,?)', ((r['sourceUrl'], r['sourceTitle'], r['sourcePublishedAt'],
            r['processingStatus'], r['body'], json.dumps({k:v for k,v in r.items() if k != 'body'}, ensure_ascii=False)) for r in rows))
        db.executemany('INSERT INTO own_articles VALUES(?,?,?,?)', ((a['id'], a['article']['slug'], a['article'].get('body', ''), json.dumps(a, ensure_ascii=False)) for a in articles.values()))
        db.executemany('INSERT INTO signals VALUES(?,?,?,?,?)', ((s['id'], s['upstreamIdentity'], s['kind'], s['sourceUrl'], json.dumps(s, ensure_ascii=False)) for s in signals.values()))
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    db.close()
    if integrity != 'ok':
        raise ValueError('Samengevoegd archief doorstaat integriteitscontrole niet')
    temporary.chmod(0o600)
    temporary.replace(output/'archive.sqlite3')
    render(output, report, rows, articles)
    render_signals(output, signals)
    return report


LABELS = {'existing_own_article': 'Eigen artikel aanwezig', 'available_source_text': 'Brontekst beschikbaar',
          'source_text_missing': 'Brontekst ontbreekt of onvolledig', 'date_review': 'Datum controleren',
          'duplicate_body_review': 'Identieke tekst controleren', 'not_article': 'Geen artikel',
          'excluded': 'Eerder uitgesloten', 'needs_fact_check': 'Inhoudelijke controle nodig'}


def render(output, report, rows, articles):
    e = lambda v: escape(str(v or ''), quote=True)
    parts = ['''<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PITO volledig bronarchief</title><style>body{font:16px/1.55 system-ui;color:#20352c;background:#f4f5ef;margin:0}main{max-width:1120px;margin:auto;padding:32px 20px}h1{line-height:1.1;font-size:42px}.tools{display:flex;gap:16px;flex-wrap:wrap;position:sticky;top:0;background:#f4f5ef;padding:16px 0}input,select{padding:12px;font:inherit;max-width:100%;border:1px solid #9aa99b;border-radius:6px}input{flex:1}article{background:white;border:1px solid #d8e1d6;border-radius:8px;padding:20px;margin:16px 0}h2{font-size:21px}small{color:#506154}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}summary{cursor:pointer;font-weight:600;margin:12px 0}a{color:#165a38}[hidden]{display:none!important}</style><main><h1>Volledig bestaand bronarchief</h1>''']
    parts.append('<p>'+e(report['uniqueSourceUrls'])+' unieke bronadressen · '+e(report['usableSourceTexts'])+' bruikbare opgeslagen teksten · '+e(report['registeredSources'])+' geregistreerde bronnen.</p><p>Alle opgeslagen periodes zijn meegenomen. Bestaande eigen teksten en controlebesluiten zijn behouden. Beschikbare brontekst is geen redactionele goedkeuring. Dit lokale overzicht haalt niets op en publiceert niets.</p>')
    if report['structuredSignalRecords']:
        parts.append('<p><a href="signalenbibliotheek.html">Bekijk ook '+e(report['structuredSignalRecords'])+' bekendmakingen, raadsvergaderingen en verkeerssignalen</a>.</p>')
    parts.append('<div class="tools"><input id="q" type="search" aria-label="Zoeken" placeholder="Zoek titel, gemeente, bron of tekst"><select id="status" aria-label="Verwerkingsstatus"><option value="">Alle statussen</option>')
    for key, count in sorted(report['counts'].items()):
        parts.append('<option value="'+e(key)+'">'+e(LABELS[key])+' ('+str(count)+')</option>')
    parts.append('</select></div><p id="count" aria-live="polite"></p>')
    for r in rows:
        parts.append('<article data-status="'+e(r['processingStatus'])+'"><small>'+e(LABELS[r['processingStatus']])+' · '+e(r['sourcePublishedAt'] or 'Datum onbekend')+' · '+e(', '.join(r['municipalityCandidates']))+'</small><h2>'+e(r['sourceTitle'] or r['sourceUrl'])+'</h2><a href="'+e(r['sourceUrl'])+'" target="_blank" rel="noopener noreferrer">Originele bron</a>')
        if r['body']:
            parts.append('<details><summary>Opgeslagen brontekst'+(' (onvolledig)' if not r['bodyUsable'] else '')+'</summary><pre>'+e(r['body'])+'</pre></details>')
        for a in r['linkedArticles']:
            own = articles[a['id']]['article']
            parts.append('<details><summary>Eigen tekst: '+e(a['title'])+'</summary><p>'+e(own.get('summary'))+'</p><pre>'+e(own.get('body'))+'</pre><small>Opgeslagen status: '+e(a['savedStatus'])+'. Historische lokale kopie; actuele CMS-status niet gecontroleerd.</small></details>')
        if r['previousDecisions'] or r['issues'] or r.get('extractionIssue') or r.get('crawlReason'):
            details = dict(previousDecisions=r['previousDecisions'], issues=r['issues'], extractionIssue=r.get('extractionIssue'), crawlReason=r.get('crawlReason'))
            parts.append('<details><summary>Bewijs en controlepunten</summary><pre>'+e(json.dumps(details, ensure_ascii=False, indent=2))+'</pre></details>')
        parts.append('</article>')
    parts.append('''</main><script>const rows=[...document.querySelectorAll('article')],q=document.querySelector('#q'),s=document.querySelector('#status');function filter(){let n=0;const v=q.value.toLocaleLowerCase('nl');for(const r of rows){r.hidden=!(r.textContent.toLocaleLowerCase('nl').includes(v)&&(!s.value||r.dataset.status===s.value));if(!r.hidden)n++}document.querySelector('#count').textContent=n+' bronadressen zichtbaar'}let timer;q.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(filter,160)});s.addEventListener('change',filter);filter();</script></html>''')
    path = output/'bronnenbibliotheek.html'
    path.write_text(''.join(parts))
    path.chmod(0o600)


def render_signals(output, signals):
    labels = {'official_notice_requires_primary_document': 'Bekendmaking: primair document controleren',
              'meeting_is_not_a_decision': 'Raadsvergadering: geen vastgesteld besluit',
              'historical_traffic_snapshot': 'Verkeer: historische momentopname'}
    e = lambda v: escape(str(v or ''), quote=True)
    parts = ['<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width"><title>PITO opgeslagen signalen</title><style>body{font:16px/1.55 system-ui;max-width:1100px;margin:32px auto;padding:20px;color:#20352c}input,select{font:inherit;padding:12px;margin:10px 0}article{border-bottom:1px solid #ddd;padding:18px 0}h2{font-size:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#506154}</style><h1>Opgeslagen bekendmakingen en signalen</h1><p><a href="bronnenbibliotheek.html">Terug naar bronteksten</a></p><p>Historische inname, geen bevestigde actuele verkeersmelding of redactionele goedkeuring. Een aanvraag is geen verleende vergunning; een vergadering is geen raadsbesluit.</p><input id="q" type="search" placeholder="Zoek adres, gemeente of onderwerp" aria-label="Zoeken"><select id="kind" aria-label="Soort signaal"><option value="">Alle soorten</option>']
    for kind, label in labels.items():
        parts.append('<option value="'+e(kind)+'">'+e(label)+'</option>')
    parts.append('</select><p id="count" aria-live="polite"></p>')
    for s in signals.values():
        parts.append('<article data-kind="'+e(s['kind'])+'"><small>'+e(labels[s['kind']])+'</small><h2>'+e(s['title'])+'</h2><a href="'+e(s['sourceUrl'])+'" target="_blank" rel="noopener noreferrer">Oorspronkelijke bron</a><details><summary>Opgeslagen gegevens en controlepunten</summary><pre>'+e(json.dumps(s['original'], ensure_ascii=False, indent=2))+'</pre></details></article>')
    parts.append('''<script>const rows=[...document.querySelectorAll('article')],q=document.querySelector('#q'),k=document.querySelector('#kind');function filter(){const v=q.value.toLocaleLowerCase('nl');let n=0;for(const r of rows){r.hidden=!(r.textContent.toLocaleLowerCase('nl').includes(v)&&(!k.value||r.dataset.kind===k.value));if(!r.hidden)n++}document.querySelector('#count').textContent=n+' signalen zichtbaar'}let timer;q.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(filter,180)});k.addEventListener('change',filter);filter();</script></html>''')
    path = output/'signalenbibliotheek.html'
    path.write_text(''.join(parts))
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(process(args.root.resolve(), args.output.resolve()), ensure_ascii=False))


if __name__ == '__main__':
    main()
