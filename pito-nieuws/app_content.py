"""Read-only adapter for the shared PITO agenda, never a second event store.

PITO_APP_CONTENT_URL points at the complete shared-contract snapshot (not a raw
Strapi collection). PITO_APP_CONTENT_TOKEN is sent server-side only. Production
never uses the local example snapshot and a failed refresh hides cached events.
"""
import datetime
import hashlib
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
MAX_RESPONSE_BYTES = 2_000_000
CACHE_SECONDS = 60
CACHE = {'at': 0, 'items': [], 'status': 'not_configured', 'config': '',
         'lastSuccessAt': None, 'error': None}
_LOCK = threading.Lock()


def _text(value, limit=500):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _web_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        return ''
    try:
        u = urlsplit(value)
        if u.scheme == 'https' and u.hostname and not (u.username or u.password):
            _ = u.port
            return value
    except ValueError:
        pass
    return ''


def _date_time(value, day):
    if not value:
        return None
    try:
        d = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is not None and d.date().isoformat() == day:
            return d.isoformat()
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def normalize(payload, asof, *, strict=False):
    """Validate a full shared snapshot; only explicit published web records pass.

    Live records require stable occurrence IDs. The legacy date/time identity is
    kept for existing callers importing older local fixtures. Cancellation stays
    in the record for a stable detail URL; public listing views exclude it.
    """
    if not isinstance(payload, dict):
        raise ValueError('Expected shared PITO content object')
    if type(payload.get('contractVersion', 1)) is not int or payload.get('contractVersion', 1) != 1:
        raise ValueError('Unsupported shared content contract')
    data = payload.get('data', payload)
    if not isinstance(data, dict) or not isinstance(data.get('activities'), list):
        raise ValueError('Expected activities list')
    metadata = payload.get('meta', {})
    pagination = metadata.get('pagination', {}) if isinstance(metadata, dict) else {}
    if payload.get('complete') is False or data.get('complete') is False or (isinstance(pagination, dict) and pagination.get('pageCount', 1) != 1):
        raise ValueError('Expected a complete shared snapshot')
    municipalities = {x['slug'] for x in json.loads((ROOT/'data/municipalities.json').read_text())}
    result = {}
    if len(data['activities']) > 10_000:
        raise ValueError('Too many activities')
    for a in data['activities']:
        if not isinstance(a, dict):
            continue
        if a.get('status') != 'published' or a.get('show_on_web') is not True:
            continue
        aid = _text(str(a.get('id') or ''), 200)
        title = _text(a.get('title'), 300)
        municipality = _text(a.get('municipality')).lower().replace(' ', '-')
        link = _web_url(a.get('url'))
        if not aid or not title or municipality not in municipalities or not link:
            continue
        occurrences = a.get('occurrences', [])
        if not isinstance(occurrences, list):
            continue
        images = []
        photos = a.get('web_images', [])
        for photo in photos[:6] if isinstance(photos, list) else []:
            if not isinstance(photo, dict):
                continue
            image_url = _web_url(photo.get('url'))
            credit = _text(photo.get('credit'))
            if photo.get('web_usage_approved') is True and image_url and credit:
                images.append({'url': image_url, 'alt': _text(photo.get('alt')), 'credit': credit})
        for o in occurrences[:1000]:
            if not isinstance(o, dict):
                continue
            day = o.get('date', '')
            try:
                parsed_day = datetime.date.fromisoformat(day)
            except (ValueError, TypeError):
                continue
            if parsed_day.isoformat() != day:
                continue
            oid = _text(str(o.get('id') or ''), 200)
            times = _text(o.get('times_text'))
            if day < asof or (strict and not oid):
                continue
            if not isinstance(o.get('cancelled', False), bool) or not isinstance(a.get('cancelled', False), bool):
                continue
            start = _date_time(o.get('startDate'), day)
            # An end on the following date is valid for an overnight event.
            end_day = str(o.get('endDate') or '')[:10]
            end = _date_time(o.get('endDate'), end_day)
            if strict and ((o.get('startDate') and not start) or (o.get('endDate') and not end)):
                continue
            if end and (not start or datetime.datetime.fromisoformat(end) < datetime.datetime.fromisoformat(start)):
                continue
            key = (aid, oid) if oid else (aid, day, times)
            if key in result and result[key]['cancelled'] and not (o.get('cancelled') or a.get('cancelled')):
                continue
            result[key] = {
                'images': images, 'category': _text(a.get('category')),
                'timesText': times, 'agendaHighlight': a.get('agendaHighlight') is True,
                'id': aid, 'kind': 'activity', 'title': title,
                'municipality': municipality, 'date': day,
                'occurrenceId': oid, 'occurrenceKey': oid or times,
                'startDate': start, 'endDate': end,
                'locationName': _text(a.get('locationName')), 'address': _text(a.get('address')),
                'organizer': _text(a.get('organizer')), 'priceText': _text(a.get('priceText')),
                'cancelled': o.get('cancelled', False) or a.get('cancelled', False),
                'label': day + (' · ' + times if times else ''),
                'summary': _text(a.get('description'), 12_000), 'sourceName': 'PITO-app', 'url': link,
            }
    return sorted(result.values(), key=lambda a: (a['date'], a.get('startDate') or '', a['id'], a['occurrenceId']))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # Configure the final endpoint explicitly so bearer tokens cannot leak.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Shared endpoint redirects are not allowed')


def _endpoint(endpoint, mode):
    if any(ord(c) < 33 for c in endpoint):
        raise ValueError('Invalid shared endpoint')
    u = urlsplit(endpoint)
    _ = u.port
    local = (mode != 'production' or os.environ.get('PITO_LOCAL_TEST') == '1') and u.hostname in ('localhost', '127.0.0.1', '::1')
    if not u.hostname or u.username or u.password or u.fragment or not (u.scheme == 'https' or (u.scheme == 'http' and local)):
        raise ValueError('HTTPS required for shared endpoint')


def get():
    endpoint = os.environ.get('PITO_APP_CONTENT_URL', '').strip()
    token = os.environ.get('PITO_APP_CONTENT_TOKEN', '')
    mode = os.environ.get('PITO_SITE_MODE', 'preview')
    public_preview = os.environ.get('PITO_PUBLIC_PREVIEW') == '1'
    # Hash credentials to isolate caches without retaining them in diagnostics.
    config = hashlib.sha256(json.dumps([endpoint, token, mode, public_preview]).encode()).hexdigest()
    with _LOCK:
        if not endpoint:
            CACHE.update(at=0, items=[], status='not_configured', config=config, lastSuccessAt=None, error=None)
            if mode != 'production' and not public_preview:
                CACHE.update(items=local_preview(), status='local_preview')
            return CACHE['items'], CACHE['status']
        if CACHE.get('config') == config and 0 <= time.time() - CACHE['at'] < CACHE_SECONDS:
            return CACHE['items'], CACHE['status']
        if CACHE.get('config') != config:
            CACHE.update(items=[], lastSuccessAt=None)
        try:
            _endpoint(endpoint, 'production' if public_preview else mode)
            if '\r' in token or '\n' in token:
                raise ValueError('Invalid shared token')
            headers = {'Accept': 'application/json', 'Accept-Encoding': 'identity'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            req = urllib.request.Request(endpoint, headers=headers)
            with urllib.request.build_opener(_NoRedirect()).open(req, timeout=5) as response:
                if response.status != 200:
                    raise ValueError('Unexpected shared endpoint response')
                content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                if content_type != 'application/json' and not content_type.endswith('+json'):
                    raise ValueError('Expected JSON response')
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError('Response too large')
            # Keep past details resolvable. Listing views select the current dates.
            items = normalize(json.loads(raw), '1900-01-01', strict=True)
            CACHE.update(at=time.time(), items=items, status='connected', config=config,
                         lastSuccessAt=datetime.datetime.now(datetime.timezone.utc).isoformat(), error=None)
        except Exception:
            # Never expose error text/secrets or stale withdrawn/cancelled events.
            CACHE.update(at=time.time(), items=[], status='unavailable', config=config, error='refresh_failed')
        return CACHE['items'], CACHE['status']


def diagnostics():
    """Safe operations summary: no endpoint, credentials, exception text or items."""
    return {'configured': bool(os.environ.get('PITO_APP_CONTENT_URL', '').strip()),
            'status': CACHE['status'], 'itemCount': len(CACHE['items']),
            'lastSuccessAt': CACHE.get('lastSuccessAt'), 'error': CACHE.get('error')}


def local_preview():
    """User-owned handoff snapshot; used only in the local preview environment."""
    if os.environ.get('PITO_SITE_MODE') == 'production' or os.environ.get('PITO_PUBLIC_PREVIEW') == '1':
        return []
    path = ROOT/'data/app-local-preview.json'
    if not path.exists():
        return []
    rows = []
    for a in json.loads(path.read_text())['activities']:
        for o in a['occurrences']:
            rows.append(dict(a, kind='activity', date=o['date'],
                             label=o.get('times_text') or 'Tijden bij de organisator',
                             timesText=o.get('times_text', ''), summary=a['description'],
                             occurrenceKey=o.get('times_text', '')))
    return rows
