"""Fetch configured RSS/Atom headlines; article bodies are never published."""

import argparse
import concurrent.futures
import datetime
import email.utils
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if __package__:
    from .source_security import fetch_public_https, parse_xml, safe_external_url
else:
    from source_security import fetch_public_https, parse_xml, safe_external_url


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKERS = 6
MAX_WORKERS = 12


def canonical(url):
    if not safe_external_url(url):
        raise ValueError('Alleen publieke HTTPS-bronlinks')
    parsed = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query)
             if not key.lower().startswith('utm_')]
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path,
                       urlencode(query), ''))


def parse_feed(raw, source, start, end, stats=None):
    root = parse_xml(raw, 2_000_000)
    # RSS 1.0 uses namespaced items under rdf:RDF; Atom uses feed/entry.
    root_name = root.tag.split('}')[-1]
    if root_name not in ('rss', 'RDF', 'feed'):
        raise ValueError('Bronantwoord is geen RSS- of Atom-feed')
    items = [item for item in root.iter()
             if item.tag.split('}')[-1] in ('item', 'entry')]
    result = []
    skipped = 0
    counts = {'feedEntries': len(items), 'skippedMissingDate': 0, 'skippedInvalidDate': 0,
              'skippedOutsideWindow': 0, 'skippedInvalidItem': 0}
    coverage = sorted(set(source.get('coverageCandidates', [])
                          + ([source['municipality']] if source.get('municipality') else [])))
    for item in items:
        def text(name):
            for child in item:
                if child.tag.split('}')[-1] == name:
                    return child.text or ''
            return ''

        title = re.sub('<[^>]*>', '', text('title')).strip()[:350]
        link = text('link').strip()
        if not link:
            link = next((child.attrib.get('href', '') for child in item
                         if child.tag.split('}')[-1] == 'link'
                         and child.attrib.get('rel', 'alternate') == 'alternate'), '')
        rawdate = text('pubDate') or text('published') or text('updated') or text('date')
        if not rawdate.strip():
            skipped += 1
            counts['skippedMissingDate'] += 1
            continue
        try:
            try:
                timestamp = email.utils.parsedate_to_datetime(rawdate)
            except (ValueError, TypeError):
                timestamp = datetime.datetime.fromisoformat(rawdate.replace('Z', '+00:00'))
            # Keep the source's stated date/offset; never invent a timezone.
            day = timestamp.date().isoformat()
        except (ValueError, TypeError, IndexError, OverflowError):
            skipped += 1
            counts['skippedInvalidDate'] += 1
            continue
        if not start <= day <= end:
            skipped += 1
            counts['skippedOutsideWindow'] += 1
            continue
        try:
            link = canonical(link)
            allowed = source.get('articleHosts', [])
            if allowed and urlsplit(link).hostname not in allowed:
                raise ValueError('Linkhost buiten broncontract')
            if not title:
                raise ValueError('Bronbericht heeft geen kop')
        except (ValueError, TypeError, IndexError, OverflowError):
            skipped += 1
            counts['skippedInvalidItem'] += 1
            continue
        images = []
        for child in item.iter():
            tag = child.tag.split('}')[-1]
            if tag not in ('content', 'thumbnail', 'enclosure'):
                continue
            candidate = child.attrib.get('url', '')
            if candidate.startswith('https://') and (
                tag == 'thumbnail' or child.attrib.get('medium') == 'image'
                or child.attrib.get('type', '').startswith('image/')
                or re.search(r'\.(jpg|jpeg|png|webp)(?:\?|$)', candidate, re.I)
            ):
                images.append({'url': candidate, 'sourcePage': link,
                               'rightsStatus': 'unknown', 'publicationAllowed': False})
        result.append({
            'imageCandidates': images[:4], 'municipalityCandidates': coverage,
            'id': hashlib.sha256(link.encode()).hexdigest()[:20],
            'sourceTitle': title, 'sourceUrl': link, 'sourcePublishedAt': day,
            'sourceId': source['id'], 'status': 'needs_review', 'municipalities': [],
            'sourceMunicipality': source.get('municipality', ''),
            'sourceTimestamp': (rawdate.strip() if re.fullmatch(r'\d{4}-\d{2}-\d{2}', rawdate.strip())
                                else timestamp.isoformat()),
            'sourceTimezoneKnown': timestamp.utcoffset() is not None,
            'fingerprint': hashlib.sha256((title + '|' + rawdate).encode()).hexdigest()[:20],
            'note': 'Geografie en primaire feiten nog door redactie controleren.',
        })
    if stats is not None:
        stats.update(counts)
    return result, skipped


def merge_signal(known, inbox, item, run_at):
    old = known.get(item['sourceUrl'])
    if old is None:
        item['sourceIds'] = [item['sourceId']]
        item['sourceMunicipalities'] = ([item['sourceMunicipality']]
                                        if item.get('sourceMunicipality') else [])
        item['firstSeenAt'] = run_at
        item['lastSeenAt'] = run_at
        inbox.append(item)
        known[item['sourceUrl']] = item
        return 1
    old['sourceIds'] = sorted(set(old.get('sourceIds', [old['sourceId']]) + [item['sourceId']]))
    old['sourceMunicipalities'] = sorted(set(
        old.get('sourceMunicipalities', ([old['sourceMunicipality']]
                                       if old.get('sourceMunicipality') else []))
        + ([item['sourceMunicipality']] if item.get('sourceMunicipality') else [])))
    old['lastSeenAt'] = run_at
    old['imageCandidates'] = item.get('imageCandidates', [])
    old['municipalityCandidates'] = sorted(set(old.get('municipalityCandidates', [])
                                               + item.get('municipalityCandidates', [])))
    if 'sourceTimezoneKnown' in item:
        old['sourceTimezoneKnown'] = item['sourceTimezoneKnown']
    if old.get('fingerprint') != item['fingerprint']:
        if old.get('fingerprint'):
            old.setdefault('revisions', []).append({key: old.get(key) for key in
                                                  ('sourceTitle', 'sourcePublishedAt',
                                                   'sourceTimestamp', 'fingerprint')})
        old.update({key: item[key] for key in ('sourceTitle', 'sourcePublishedAt',
                                             'sourceTimestamp', 'fingerprint')})
        old['sourceChangedAt'] = run_at
        old['status'] = 'needs_review'
    return 0


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _feed_host(source):
    try:
        return urlsplit(source['feed']).hostname or ''
    except (ValueError, TypeError):
        return ''


def _fetch_source(source, start, end, host_limits):
    """Workers only fetch and parse. The caller alone merges and writes."""
    started = time.monotonic()
    report = {
        'source': source['id'], 'name': source.get('name', source['id']),
        'url': source['feed'], 'kind': source.get('kind', ''),
        'municipality': source.get('municipality', ''),
        'coverageCandidates': source.get('coverageCandidates', []),
        'startedAt': _now(),
    }
    items = []
    try:
        canonical(source['feed'])
        with host_limits[_feed_host(source)]:
            raw = fetch_public_https(source['feed'], max_bytes=2_000_000, timeout=25,
                                     user_agent='PITO-feed-intake/1.0')
        stats = {}
        items, skipped = parse_feed(raw, source, start, end, stats=stats)
        report.update(stats)
        report.update(status='ok', receivedInWindow=len(items), skipped=skipped,
                      added=0, oldestReceived=min((row['sourcePublishedAt'] for row in items), default=None),
                      newestReceived=max((row['sourcePublishedAt'] for row in items), default=None),
                      fullArchive=False, lastSuccessAt=_now())
        if items:
            report['freshnessStatus'] = 'recent'
        elif not stats['feedEntries']:
            report.update(freshnessStatus='empty', warning='Feed bereikbaar maar leeg.')
        elif stats['skippedMissingDate'] + stats['skippedInvalidDate'] == stats['feedEntries']:
            report.update(freshnessStatus='undated', warning='Geen bruikbare publicatiedatums; berichten worden niet getoond.')
        elif stats['skippedOutsideWindow']:
            report.update(freshnessStatus='outside_window', warning='Geen bruikbare berichten binnen de ophaalperiode.')
        else:
            report.update(freshnessStatus='unusable', warning='Feed bereikbaar maar bevat geen bruikbare berichten.')
    except Exception as error:
        detail = (error.stderr.decode(errors='replace') if isinstance(error, subprocess.CalledProcessError)
                  and isinstance(error.stderr, bytes) else str(error))
        report.update(status='error', error=detail[:300], added=0)
    report['finishedAt'] = _now()
    report['durationSeconds'] = round(time.monotonic() - started, 3)
    return report, items


def _atomic_json(path, value):
    """Replace one complete JSON snapshot; interruption leaves the old file readable."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), (path.stat().st_mode & 0o777) if path.exists() else 0o644)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(start, end, workers=DEFAULT_WORKERS):
    datetime.date.fromisoformat(start)
    datetime.date.fromisoformat(end)
    if start > end:
        raise ValueError('Begin ligt na einde')
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f'Aantal gelijktijdige bronnen moet tussen 1 en {MAX_WORKERS} liggen')
    sources = [source for source in json.loads((ROOT / 'data/sources.json').read_text()) if source.get('feed')]
    path = ROOT / 'data/inbox.json'
    inbox = json.loads(path.read_text()) if path.exists() else []
    known = {row['sourceUrl']: row for row in inbox}
    report_path = ROOT / 'data/intake-report.json'
    previous = {}
    if report_path.exists():
        try:
            previous = {row['source']: row for row in json.loads(report_path.read_text()).get('sources', [])}
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
    started = time.monotonic()
    report = {'runAt': _now(), 'window': [start, end], 'sources': [], 'added': 0,
              'configured': len(sources), 'workers': workers, 'autoPublish': False}
    host_limits = {_feed_host(source): threading.BoundedSemaphore(2) for source in sources}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        # map retains configuration order regardless of response order. This also
        # makes duplicate ownership and revision history deterministic.
        for source_report, items in executor.map(
            lambda source: _fetch_source(source, start, end, host_limits), sources
        ):
            for item in items:
                source_report['added'] += merge_signal(known, inbox, item, report['runAt'])
            if source_report['status'] != 'ok':
                earlier = previous.get(source_report['source'], {})
                source_report['lastSuccessAt'] = earlier.get('lastSuccessAt') or (
                    earlier.get('finishedAt', earlier.get('runAt')) if earlier.get('status') == 'ok' else None)
            report['added'] += source_report['added']
            report['sources'].append(source_report)
    report['succeeded'] = sum(row['status'] == 'ok' for row in report['sources'])
    report['failed'] = len(sources) - report['succeeded']
    report['finishedAt'] = _now()
    report['durationSeconds'] = round(time.monotonic() - started, 3)
    _atomic_json(path, inbox)
    _atomic_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start')
    parser.add_argument('--end', default=datetime.date.today().isoformat())
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()
    try:
        end = datetime.date.fromisoformat(args.end)
        start = args.start or (end - datetime.timedelta(days=14)).isoformat()
        report = run(start, args.end, args.workers)
        return 1 if report['configured'] and not report['succeeded'] else 0
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    sys.exit(main())
