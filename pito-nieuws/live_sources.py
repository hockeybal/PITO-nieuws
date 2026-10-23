"""Fresh, attributed RSS headline links; never turns signals into PITO articles.

Files are read for each request so an atomic intake update is visible without a
web-service restart. Missing or malformed data produces an honest empty state.
"""
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
import ipaddress
import json
import re

from scripts.source_security import safe_external_url

DATA = Path(__file__).parent / 'data'
AMSTERDAM = ZoneInfo('Europe/Amsterdam')
PAGE_PATH = '/nieuws/bronberichten'
STATUS_PATH = '/nieuws/aanvoerstatus'
PAGE_SIZE = 30
STALE_AFTER = timedelta(hours=2)
PROVINCIAL_SOURCE_IDS = frozenset(('politie', 'provincie-live', 'rtv-utrecht'))


def _read(name, default):
    try:
        value = json.loads((DATA / (name + '.json')).read_text())
        return value if isinstance(value, type(default)) else default
    except (OSError, ValueError, UnicodeError):
        return default


def _rows(value):
    return value if isinstance(value, list) else []


def _e(value):
    return escape(str(value or ''), quote=True)


def _now(now=None):
    value = now or datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _timestamp(value):
    """Accept an actual zoned instant, without inventing a feed timezone."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def _source_date(item):
    raw = item.get('sourceTimestamp')
    if raw:
        instant = _timestamp(raw)
        if instant is not None:
            return instant, True
        # Date-only feeds are allowed; malformed/naive timestamps are not
        # silently replaced with ingestion time or a conflicting publication day.
        if not isinstance(raw, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            return None, False
    else:
        raw = item.get('sourcePublishedAt')
    try:
        day = date.fromisoformat(raw)
        return datetime.combine(day, time.min, tzinfo=AMSTERDAM), False
    except (TypeError, ValueError):
        return None, False


def _canonical_url(raw):
    if not safe_external_url(raw):
        return ''
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        if '.' not in host or host.endswith(('.localhost', '.local', '.internal')):
            return ''
        try:
            if not ipaddress.ip_address(host).is_global:
                return ''
        except ValueError:
            pass
        port = parsed.port
        netloc = ('[' + host + ']' if ':' in host else host) + (':' + str(port) if port and port != 443 else '')
        query = urlencode([(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                           if not key.casefold().startswith('utm_') and key.casefold() not in ('fbclid', 'gclid')])
        return urlunsplit(('https', netloc, parsed.path or '/', query, ''))
    except (ValueError, UnicodeError):
        return ''


def _names():
    return {row['slug']: row['name'] for row in _read('municipalities', [])
            if isinstance(row, dict) and isinstance(row.get('slug'), str) and isinstance(row.get('name'), str)}


def _geography(item, sources, names):
    """Single-municipality source contracts and explicit article place markers.

    A coverage candidate is not a confirmed municipality. In particular the
    province-wide RTV/Politie Utrecht feeds do not mean Utrecht city.
    """
    places = set()
    for source in sources:
        municipality = source.get('municipality')
        if isinstance(municipality, str) and municipality in names:
            places.add(municipality)
    if item.get('geographyConfirmed') is True or item.get('geographyStatus') == 'confirmed':
        places.update(m for m in _rows(item.get('municipalities')) if isinstance(m, str) and m in names)
    title = item.get('sourceTitle', '')
    for slug, name in names.items():
        if slug == 'utrecht':
            if re.search(r'(?i)(?:^\s*utrecht\s*[-:–—]|\b(?:gemeente|stad)\s+utrecht\b|\butrecht-stad\b|\bin\s+utrecht\b(?!\s*(?:[-–—]\s*)?(?:provincie|regio|se\s+heuvelrug)))', title):
                places.add(slug)
        elif re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', title, flags=re.I):
            places.add(slug)
    return sorted(places)


def _province_relevant(item, sources, places, names):
    if places:
        return True
    for source in sources:
        if source.get('provinceWide') is True or source.get('geographicScope') == 'province' or source.get('id') in PROVINCIAL_SOURCE_IDS:
            return True
        # Regional catchments establish relevance to the province, while the
        # individual municipalities still require a local contract/place marker.
        if any(isinstance(value, str) and value in names for value in _rows(source.get('coverageCandidates'))):
            return True
    title = item.get('sourceTitle', '')
    # Utrecht without city context can establish provincial relevance without
    # being used to assign a headline to the city of Utrecht.
    return bool(re.search(r'(?i)\butrecht\b', title))


def items(m='', q='', now=None):
    """Return safe deduplicated headlines from the rolling fourteen-day window."""
    current = _now(now)
    cutoff = current - timedelta(days=14)
    names = _names()
    if m and m not in names:
        return []
    source_map = {row['id']: row for row in _read('sources', [])
                  if isinstance(row, dict) and isinstance(row.get('id'), str) and safe_external_url(row.get('feed'))}
    result = {}
    for item in _read('inbox', []):
        if not isinstance(item, dict):
            continue
        title = item.get('sourceTitle')
        if not isinstance(title, str) or not title.strip():
            continue
        url = _canonical_url(item.get('sourceUrl'))
        if not url:
            continue
        identifiers = item.get('sourceIds', [])
        identifiers = identifiers if isinstance(identifiers, list) else []
        identifiers = list(dict.fromkeys([x for x in [item.get('sourceId')] + identifiers if isinstance(x, str)]))
        known = [source_map[ident] for ident in identifiers if ident in source_map]
        # Only RSS/Atom catalog sources participate, not unrelated inbox imports.
        if not known:
            continue
        host = urlsplit(url).hostname
        known = [source for source in known if not source.get('articleHosts') or
                 isinstance(source.get('articleHosts'), list) and host in source['articleHosts']]
        if not known:
            continue
        published, has_time = _source_date(item)
        if published is None or published > current or published < cutoff:
            continue
        places = _geography(item, known, names)
        if not _province_relevant(item, known, places, names):
            continue
        if m and m not in places:
            continue
        source = known[0]
        source_name = source.get('name') or host
        clean_title = re.sub(r'[\x00-\x1f\x7f]', '', title).strip()[:350]
        if not clean_title:
            continue
        if q and q.casefold() not in (clean_title + ' ' + str(source_name)).casefold():
            continue
        row = {'title': clean_title, 'url': url, 'sourceName': str(source_name),
               'sourceId': source['id'], 'published': published, 'hasTime': has_time,
               'municipalities': places}
        if url not in result or published > result[url]['published']:
            result[url] = row
    return sorted(result.values(), key=lambda row: (row['published'], row['title']), reverse=True)


def _freshness(check, current):
    try:
        newest = date.fromisoformat(check.get('newestReceived'))
        if (current.astimezone(AMSTERDAM) - timedelta(days=14)).date() <= newest <= current.astimezone(AMSTERDAM).date():
            return 'recent'
        return 'outside_window'
    except (TypeError, ValueError):
        value = check.get('freshnessStatus')
        return value if value in ('empty', 'undated', 'outside_window', 'unusable') else 'unknown'


def feed_status(now=None):
    current = _now(now)
    sources = [row for row in _read('sources', []) if isinstance(row, dict) and row.get('feed') and isinstance(row.get('id'), str)]
    report = _read('intake-report', {})
    pipeline = _read('pipeline-report', {})
    checks = {row.get('source'): row for row in _rows(report.get('sources'))
              if isinstance(row, dict) and isinstance(row.get('source'), str)}
    run_at = _timestamp(report.get('runAt'))
    if run_at and run_at > current:
        run_at = None
    rows = []
    for source in sources:
        check = checks.get(source['id'], {})
        state = check.get('status') if check.get('status') in ('ok', 'error') else 'unknown'
        checked_at = _timestamp(check.get('finishedAt') or check.get('checkedAt')) or run_at
        if checked_at and checked_at > current:
            checked_at = None
        last_success = _timestamp(check.get('lastSuccessAt') or check.get('lastSuccessfulAt'))
        if last_success and last_success > current:
            last_success = None
        if state == 'ok' and checked_at:
            last_success = checked_at
        rows.append({'id': source['id'], 'name': source.get('name') or source['id'],
                     'status': state, 'newestReceived': check.get('newestReceived'),
                     'freshnessStatus': _freshness(check, current),
                     'checkedAt': checked_at, 'lastSuccessAt': last_success,
                     'receivedInWindow': check.get('receivedInWindow'),
                     'error': str(check.get('error') or '')[:300],
                     'warning': str(check.get('warning') or '')[:300]})
    successful = [row['lastSuccessAt'] for row in rows if row['lastSuccessAt'] and row['lastSuccessAt'] <= current]
    for field in ('lastSuccessfulRunAt', 'lastSuccessAt', 'lastSuccessfulAt'):
        candidate = _timestamp(report.get(field))
        if candidate and candidate <= current:
            successful.append(candidate)
    # A pipeline start is not evidence of successful feed intake.
    last_success = max(successful, default=None)
    return {'configured': len(sources), 'ok': sum(row['status'] == 'ok' for row in rows),
            'errors': sum(row['status'] == 'error' for row in rows),
            'unknown': sum(row['status'] == 'unknown' for row in rows),
            'recent': sum(row['status'] == 'ok' and row['freshnessStatus'] == 'recent' for row in rows),
            'runAt': run_at, 'lastSuccessAt': last_success,
            'stale': run_at is None or current - run_at > STALE_AFTER,
            'degraded': run_at is None or current - run_at > STALE_AFTER or any(row['status'] != 'ok' for row in rows),
            'pipelineRunAt': _timestamp(pipeline.get('runAt')), 'sources': rows}


def _time_html(value, has_time=True):
    if value is None:
        return 'Nog niet beschikbaar'
    local = value.astimezone(AMSTERDAM)
    label = local.strftime('%d-%m-%Y %H:%M') + ' (Nederlandse tijd)' if has_time else local.strftime('%d-%m-%Y')
    iso = local.isoformat() if has_time else local.date().isoformat()
    return '<time datetime="' + _e(iso) + '">' + label + '</time>'


def _summary(status):
    if status['runAt'] is None:
        return 'Er is nog geen geldige ophaalronde geregistreerd.'
    text = str(status['ok']) + ' van ' + str(status['configured']) + ' feeds bereikbaar bij de laatste controle'
    if status['errors']:
        text += ' · ' + str(status['errors']) + ' met een fout'
    if status['unknown']:
        text += ' · ' + str(status['unknown']) + ' nog niet gecontroleerd'
    if status['errors'] or status['unknown']:
        text = 'Aanvoer gedeeltelijk beschikbaar: ' + text
    return text + ('. De laatste controle is meer dan twee uur geleden.' if status['stale'] else '.')


def _list(rows, heading='h3'):
    return '<ol class="live-sources-list">' + ''.join(
        '<li><' + heading + '><a href="' + _e(row['url']) + '" target="_blank" rel="noopener noreferrer external">' +
        _e(row['title']) + '<span class="live-source-arrow" aria-hidden="true"> ↗</span></a></' + heading + '>' +
        '<p class="live-source-meta">' + _e(row['sourceName']) + ' · ' + _time_html(row['published'], row['hasTime']) + '</p></li>'
        for row in rows) + '</ol>'


def block(m=''):
    rows = items(m)
    status = feed_status()
    link = PAGE_PATH + ('?' + urlencode({'gemeente': m}) if m else '')
    return ('<section class="live-sources" data-feed-state="' + ('degraded' if status['degraded'] else 'current') + '" aria-labelledby="live-sources-title">'
            '<header class="desk-heading"><h2 id="live-sources-title">Uit de bronnen</h2><a href="' + _e(link) + '">Alle bronberichten ›</a></header>'
            '<p class="live-sources-intro">Recente koppen uit RSS-feeds. Lees het volledige bericht bij de oorspronkelijke bron.</p>' +
            (_list(rows[:8]) if rows else '<p class="live-sources-empty">Nog geen bronberichten met een geldige publicatiedatum in de afgelopen veertien dagen voor deze selectie.</p>') +
            '<p class="live-sources-status">' + _e(_summary(status)) + ' <a href="' + STATUS_PATH + '">Bekijk de aanvoerstatus</a></p></section>')


def page(m='', q='', page='1'):
    import news
    names = _names()
    m = m if m in names else ''
    q = str(q or '')[:200]
    rows = items(m, q)
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    try:
        number = max(1, min(pages, int(page)))
    except (TypeError, ValueError):
        number = 1
    options = '<option value="">Hele provincie Utrecht</option>' + ''.join(
        '<option value="' + _e(slug) + '"' + (' selected' if slug == m else '') + '>' + _e(name) + '</option>'
        for slug, name in names.items())
    filters = ('<form class="live-sources-filters" action="' + PAGE_PATH + '"><label>Gemeente<select name="gemeente">' + options + '</select></label>'
               '<label>Zoek in bronkoppen<input type="search" name="q" value="' + _e(q) + '"></label><button>Toon berichten</button></form>')
    status = feed_status()
    selected = rows[(number - 1) * PAGE_SIZE:number * PAGE_SIZE]
    pagination = '<nav class="live-sources-pages" aria-label="Bronberichten pagina’s">' + ''.join(
        '<a href="' + PAGE_PATH + '?' + _e(urlencode({'gemeente': m, 'q': q, 'pagina': value})) + '"' +
        (' aria-current="page"' if value == number else '') + '>Pagina ' + str(value) + '</a>'
        for value in sorted(set([1, pages] + list(range(max(1, number - 2), min(pages, number + 2) + 1))))) + '</nav>' if pages > 1 else ''
    body = ('<section class="live-sources live-sources-page"><nav class="article-context"><a href="' + news.BASE + '">Nieuws uit Utrecht</a><a href="' + STATUS_PATH + '">Aanvoerstatus</a></nav>'
            '<p class="eyebrow">UIT DE BRONNEN</p><h1>Recente bronberichten' + (' · ' + _e(names[m]) if m else '') + '</h1>'
            '<p class="standfirst">Koppen en links uit de aangesloten RSS-feeds, met de naam en publicatiedatum van de bron. Je leest het volledige bericht op de website van die bron.</p>'
            '<p>Deze bronberichten worden automatisch opgehaald en zijn geen door PITO geschreven of gecontroleerde artikelen. Alleen berichten uit de afgelopen veertien dagen worden getoond.</p>' +
            filters + '<p class="live-sources-status">' + _e(_summary(status)) + '</p><p>' + str(len(rows)) + ' bronberichten in deze selectie.</p>' +
            (_list(selected, 'h2') if selected else '<p class="live-sources-empty">Geen recente bronberichten voor deze selectie.</p>') + pagination + '</section>')
    return news.layout('Recente bronberichten', body, PAGE_PATH,
                       'Recente koppen en bronlinks uit de aangesloten RSS-feeds voor de provincie Utrecht.')


def status_page():
    import news
    status = feed_status()
    labels = {'ok': 'Bereikbaar', 'error': 'Fout bij ophalen', 'unknown': 'Nog niet gecontroleerd'}
    freshness_labels = {'recent': 'Berichten uit de laatste 14 dagen', 'empty': 'Geen berichten in de feed',
                        'undated': 'Publicatiedatum ontbreekt', 'outside_window': 'Geen berichten uit de laatste 14 dagen',
                        'unusable': 'Geen bruikbare bronberichten', 'unknown': 'Niet vastgesteld'}
    rows = ''.join('<tr><th scope="row">' + _e(row['name']) + '</th><td>' + labels[row['status']] +
                   ('<small class="live-source-note">' + _e(row['error'] or row['warning']) + '</small>' if row['error'] or row['warning'] else '') + '</td><td>' +
                   _time_html(row['lastSuccessAt']) + '</td><td>' + _e(row['newestReceived'] or 'Geen datum ontvangen') + '</td><td>' +
                   _e(freshness_labels[row['freshnessStatus']]) + '</td></tr>'
                   for row in sorted(status['sources'], key=lambda row: (row['status'] != 'error', str(row['name']).casefold())))
    body = ('<section class="live-sources live-sources-page"><nav class="article-context"><a href="' + news.BASE + '">Nieuws uit Utrecht</a><a href="' + PAGE_PATH + '">Bronberichten</a></nav>'
            '<p class="eyebrow">RSS-AANVOER</p><h1>Aanvoerstatus</h1><p class="standfirst">' + _e(_summary(status)) + '</p>'
            '<dl class="live-sources-dates"><dt>Laatste ophaalronde</dt><dd>' + _time_html(status['runAt']) + '</dd>'
            '<dt>Laatste geslaagde broncontrole</dt><dd>' + _time_html(status['lastSuccessAt']) + '</dd></dl>'
            '<p>De RSS-feeds worden iedere vijftien minuten gecontroleerd. Een bereikbare feed kan geen recente berichten bevatten. Een ophaalfout blijft zichtbaar; eerder opgehaalde koppen blijven maximaal veertien dagen beschikbaar. Gemeenteselecties gebruiken de herkomst van een lokale bron of een expliciete plaatsaanduiding in de kop.</p>'
            '<div class="live-sources-table-wrap"><table class="live-sources-table"><caption>Status per aangesloten RSS-feed</caption><thead><tr><th>Bron</th><th>Laatste controle</th><th>Laatste geslaagde controle</th><th>Nieuwste ontvangen brondag</th><th>Recente berichten</th></tr></thead><tbody>' +
            rows + '</tbody></table></div></section>')
    return news.layout('Aanvoerstatus RSS-feeds', body, STATUS_PATH,
                       'De laatste ophaalronde, bereikbaarheid en fouten van de aangesloten RSS-feeds.')
