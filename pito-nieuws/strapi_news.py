"""One authenticated, atomic Strapi snapshot for every public news renderer.

The custom v1 endpoint is intentionally NOT a paginated collection endpoint.
A response is activated only after its entire manifest, articles and redirects
validate. No disk/SQLite fallback exists. Each process reconciles on demand at
most every 45 seconds, including when no webhook has arrived. HTTP has an eight
second timeout, so normal publish/unpublish visibility is below 60 seconds.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, replace
import datetime as dt
from functools import wraps
from ranking import local_date
import json
import os
import re
import threading
import time
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

TTL_SECONDS = 45
MAX_STALE_SECONDS = 300
RETRY_SECONDS = 5
MAX_RESPONSE = 12_000_000
MUNICIPALITIES = frozenset('amersfoort baarn bunnik bunschoten de-bilt de-ronde-venen eemnes houten ijsselstein leusden lopik montfoort nieuwegein oudewater renswoude rhenen soest stichtse-vecht utrecht utrechtse-heuvelrug veenendaal vijfheerenlanden wijk-bij-duurstede woerden woudenberg zeist'.split())
CATEGORIES = frozenset(('Bestuur', 'Veiligheid', 'Verkeer', 'Wonen', 'Samenleving', 'Sport'))
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
IDENTITY = re.compile(r'[A-Za-z0-9_-]{1,180}\Z')


class StrapiNewsError(ValueError):
    """Fixed operational errors only: do not reflect server bodies or tokens."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StrapiNewsError('CMS-redirect geweigerd')


def _configuration(environment, token_name):
    base = environment.get('PITO_STRAPI_URL', '').rstrip('/')
    token = environment.get(token_name, '')
    if not base or not token:
        raise StrapiNewsError('CMS-verbinding niet ingesteld')
    parsed = urlsplit(base)
    local = environment.get('PITO_LOCAL_TEST') == '1' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if (parsed.scheme != 'https' and not (local and parsed.scheme == 'http')
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise StrapiNewsError('CMS vereist een geldige HTTPS-basis-URL')
    if not isinstance(token, str) or not 1 <= len(token) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise StrapiNewsError('CMS-token ongeldig')
    return base, token


def request_json(base, path, token, method='GET', body=None):
    """Fixed endpoint, no proxies/redirects; a draft timeout is retried by key."""
    raw = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    headers = {'Authorization': 'Bearer '+token, 'Accept': 'application/json', 'Cache-Control': 'no-cache'}
    if raw is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(base+path, data=raw, headers=headers, method=method)
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(req, timeout=8) as response:
            if response.status != 200 and not (method == 'POST' and response.status == 201):
                raise StrapiNewsError('CMS-verzoek niet voltooid')
            if response.headers.get_content_type() != 'application/json':
                raise StrapiNewsError('CMS-antwoord is geen JSON')
            result = response.read(MAX_RESPONSE+1)
            if len(result) > MAX_RESPONSE:
                raise StrapiNewsError('CMS-antwoord te groot')
            return json.loads(result)
    except (OSError, ValueError) as error:
        # Deliberately replace all HTTP response bodies, URLs and header values.
        raise StrapiNewsError('CMS-verbinding mislukt of antwoord ongeldig') from None


def _text(value, field, maximum=20000, required=False):
    if not isinstance(value, str) or len(value) > maximum or '\x00' in value or (required and not value.strip()):
        raise StrapiNewsError('CMS-artikel heeft ongeldig veld '+field)
    return value


def _timestamp(value, field):
    _text(value, field, 80, True)
    try:
        date = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError()
        return date.astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        raise StrapiNewsError('CMS-datum ongeldig: '+field) from None


def _https(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) <= 32 for c in value):
        return False
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password


def _article(row, wall_time, base_url=None):
    if not isinstance(row, dict):
        raise StrapiNewsError('CMS-artikel ontbreekt')
    identity = _text(row.get('documentId'), 'documentId', 180, True)
    slug = _text(row.get('slug'), 'slug', 240, True)
    if not IDENTITY.fullmatch(identity) or not SLUG.fullmatch(slug):
        raise StrapiNewsError('CMS-identiteit of slug ongeldig')
    if row.get('reviewStatus') != 'approved' or not row.get('publishedAt'):
        raise StrapiNewsError('CMS-snapshot bevat ongepubliceerde inhoud')
    first = _timestamp(row.get('firstPublishedAt'), 'firstPublishedAt')
    last = _timestamp(row.get('lastPublishedAt'), 'lastPublishedAt')
    published = _timestamp(row.get('publishedAt'), 'publishedAt')
    if first > last or max(first, last, published) > wall_time+dt.timedelta(seconds=30):
        raise StrapiNewsError('CMS-publicatiedatums niet consistent')
    municipalities = row.get('municipalities')
    province_wide = row.get('provinceWide', False)
    if (not isinstance(municipalities, list) or any(not isinstance(m, str) or m not in MUNICIPALITIES for m in municipalities)
            or len(municipalities) != len(set(municipalities)) or type(province_wide) is not bool
            or not municipalities and not province_wide):
        raise StrapiNewsError('CMS-gemeenteselectie ongeldig')
    source_based = row.get('sourceBased', True)
    source_url = row.get('sourceUrl') or ''
    if type(source_based) is not bool or row.get('category') not in CATEGORIES or (source_based and not _https(source_url)) or (source_url and not _https(source_url)):
        raise StrapiNewsError('CMS-rubriek of bron ongeldig')
    source_date = _text(row.get('sourcePublishedAt') or '', 'sourcePublishedAt', 80)
    if source_date:
        try:
            local_date(source_date)
        except ValueError:
            raise StrapiNewsError('CMS-bronpublicatiedatum ongeldig') from None
    elif source_based and (not isinstance(row.get('dateNote'), str) or not row['dateNote'].strip()):
        raise StrapiNewsError('Ontbrekende brondatum vereist een concrete toelichting')
    # Explicit public allowlist. Never expose full evidence, internal review
    # notes, rights dossiers, external keys or accidental new CMS fields.
    article = {'id': identity, 'documentId': identity, 'slug': slug,
               'title': _text(row.get('title'), 'title', 400, True),
               'summary': _text(row.get('summary'), 'summary', 4000, True),
               'body': _text(row.get('body'), 'body', 200000, True),
               'category': row['category'], 'municipalities': municipalities,
               'provinceWide': province_wide, 'sourceUrl': source_url, 'sourceBased': source_based,
               'sourceName': _text(row.get('sourceName'), 'sourceName', 300, True),
               'sourcePublishedAt': local_date(source_date), 'sourcePublishedAtExact': source_date,
               'firstPublishedAt': row['firstPublishedAt'], 'lastPublishedAt': row['lastPublishedAt'],
               'webPublishedAt': row['firstPublishedAt'], 'publishedAt': row['publishedAt'],
               'webModifiedAt': row['lastPublishedAt'], 'updatedAt': row.get('updatedAt') or row['lastPublishedAt'],
               'publicationStatus': 'published', 'reviewStatus': 'approved'}
    for name in ('eventDate', 'dateNote', 'impact', 'imageKey'):
        article[name] = _text(row.get(name) or '', name, 20000)
    topics = row.get('imageTopics') or []
    if not isinstance(topics, list) or any(not isinstance(v, str) for v in topics):
        raise StrapiNewsError('CMS-beeldonderwerpen ongeldig')
    article['imageTopics'] = topics
    ranking = row.get('ranking') or {}
    if not isinstance(ranking, dict):
        raise StrapiNewsError('CMS-rangschikking ongeldig')
    # Keep the established ranker and audience selection, with typed values.
    public_ranking = {}
    for key in ('impact', 'reach', 'urgency', 'duration', 'actionability'):
        value = ranking.get(key, 0)
        if type(value) is not int or not 0 <= value <= 5:
            raise StrapiNewsError('CMS-impactbeoordeling ongeldig')
        public_ranking[key] = value
    for key in ('cluster', 'activeUntil', 'audienceNeed', 'audienceReason', 'actionFrom', 'actionUntil', 'alertCheckedOn'):
        if ranking.get(key) is not None:
            public_ranking[key] = _text(ranking[key], 'ranking.'+key, 1500)
    if 'alertConfirmed' in ranking:
        if type(ranking['alertConfirmed']) is not bool:
            raise StrapiNewsError('CMS-waarschuwing ongeldig')
        public_ranking['alertConfirmed'] = ranking['alertConfirmed']
    article['ranking'] = public_ranking
    author = row.get('author') or 'PITO Nieuws'
    article['authorName'] = _text(author, 'author', 300)
    article['author'] = author
    author_type = row.get('authorType') or ('automatic' if 'automatisch' in author.lower() else 'human')
    if author_type not in ('human', 'automatic') or row.get('humanReviewed', True) is not True:
        raise StrapiNewsError('CMS-auteurschap of beoordelingsbewijs ongeldig')
    article['authorType'] = author_type
    # Authorship and human review are independent. A machine-written draft
    # can be published only after the CMS gate records real editorial review.
    article['humanReviewed'] = True
    article['authorship'] = {'kind': 'automated' if author_type == 'automatic' else 'editorial'}
    additional = row.get('additionalSources') or []
    if not isinstance(additional, list) or any(not isinstance(s, dict) or not _https(s.get('url')) or not isinstance(s.get('name'), str) for s in additional):
        raise StrapiNewsError('CMS-extra bronnen ongeldig')
    article['additionalSources'] = [{'name': s['name'], 'url': s['url']} for s in additional]
    image = row.get('image')
    if image is not None:
        if not isinstance(image, dict):
            raise StrapiNewsError('CMS-beeld ongeldig')
        image_url = image.get('url')
        if base_url and isinstance(image_url, str) and image_url.startswith('/uploads/') and '\\' not in image_url:
            image_url = urljoin(base_url, image_url)
        local_image = base_url and urlsplit(base_url).scheme == 'http' and urlsplit(base_url).hostname in ('127.0.0.1', 'localhost', '::1') and isinstance(image_url, str) and image_url.startswith(base_url+'/uploads/')
        if image.get('web_usage_approved') is True and (_https(image_url) or local_image) and image.get('credit'):
            article['image'] = {'url': image_url, 'alt': _text(image.get('alt') or '', 'image.alt', 1000),
                                'credit': _text(image['credit'], 'image.credit', 1000, True), 'web_usage_approved': True}
    return article


@dataclass(frozen=True)
class Snapshot:
    articles: tuple = ()
    redirects: tuple = ()
    revision: str = ''
    status: str = 'unavailable'


def validate_snapshot(payload, wall_time=None, base_url=None):
    wall_time = wall_time or dt.datetime.now(dt.timezone.utc)
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), dict) or not isinstance(payload.get('meta'), dict):
        raise StrapiNewsError('CMS-snapshot ontbreekt')
    data, meta = payload['data'], payload['meta']
    if meta.get('schemaVersion') != 1 or meta.get('complete') is not True or 'pagination' in meta:
        raise StrapiNewsError('CMS-snapshot is onvolledig of gepagineerd')
    if not isinstance(data.get('articles'), list) or not isinstance(data.get('redirects'), list):
        raise StrapiNewsError('CMS-snapshotlijsten ontbreken')
    for field, expected in (('total', len(data['articles'])), ('articleCount', len(data['articles'])), ('redirectCount', len(data['redirects']))):
        if type(meta.get(field)) is not int or meta[field] != expected:
            raise StrapiNewsError('CMS-manifest klopt niet')
    generated = _timestamp(meta.get('generatedAt'), 'generatedAt')
    if generated < wall_time-dt.timedelta(seconds=MAX_STALE_SECONDS) or generated > wall_time+dt.timedelta(seconds=30):
        raise StrapiNewsError('CMS-snapshot is verouderd')
    revision = _text(meta.get('revision'), 'revision', 64, True)
    if not re.fullmatch(r'[0-9a-f]{64}', revision):
        raise StrapiNewsError('CMS-revisie ongeldig')
    articles = tuple(_article(a, wall_time, base_url) for a in data['articles'])
    by_slug = {a['slug']: a['documentId'] for a in articles}
    if len(by_slug) != len(articles) or len({a['documentId'] for a in articles}) != len(articles):
        raise StrapiNewsError('CMS-snapshot bevat dubbele identiteit')
    redirects = []
    for r in data['redirects']:
        if (not isinstance(r, dict) or not isinstance(r.get('from'), str) or not SLUG.fullmatch(r['from'])
                or not isinstance(r.get('to'), str) or not SLUG.fullmatch(r['to'])
                or r['from'] in by_slug or r['to'] not in by_slug or by_slug[r['to']] != r.get('documentId')):
            raise StrapiNewsError('CMS-redirect ongeldig')
        redirects.append((r['from'], r['to']))
    if len(dict(redirects)) != len(redirects):
        raise StrapiNewsError('CMS-redirectconflict')
    return Snapshot(articles, tuple(redirects), revision, 'connected')


class SnapshotReader:
    def __init__(self, fetch, clock=None, wall_clock=None, base_url=None):
        self.fetch = fetch
        self.base_url = base_url
        self.clock = clock or time.monotonic
        self.wall_clock = wall_clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self._snapshot = None
        self._success = None
        self._attempt = None
        self._lock = threading.RLock()

    def read(self, force=False):
        with self._lock:
            now = self.clock()
            fresh = self._success is not None and now-self._success < TTL_SECONDS
            retry = self._attempt is None or now-self._attempt >= RETRY_SECONDS
            if force or not fresh and retry:
                self._attempt = now
                try:
                    payload = self.fetch()
                    snapshot = validate_snapshot(payload, self.wall_clock(), self.base_url)
                    generated = _timestamp(payload['meta']['generatedAt'], 'generatedAt')
                    server_age = max(0, (self.wall_clock()-generated).total_seconds())
                except Exception:
                    # Never activate a partial snapshot or expose credentialed
                    # endpoint details in logs, HTML or a public error response.
                    pass
                else:
                    self._snapshot, self._success = snapshot, self.clock()-server_age
            age = self.clock()-self._success if self._success is not None else None
            if self._snapshot is None or age is None or age >= MAX_STALE_SECONDS:
                return Snapshot(status='unavailable')
            status = 'connected' if age < TTL_SECONDS else 'stale'
            return deepcopy(replace(self._snapshot, status=status))


_reader = None
_reader_key = None
_reader_lock = threading.Lock()
_scope = ContextVar('pito_news_request_snapshot', default=None)


def configured():
    return bool(os.environ.get('PITO_STRAPI_URL') or os.environ.get('PITO_NEWS_READ_TOKEN'))


def enabled():
    import search_visibility
    return configured() or search_visibility.public_facing()


def snapshot(force=False):
    global _reader, _reader_key
    scope = _scope.get()
    if not force and scope is not None and 'snapshot' in scope:
        return deepcopy(scope['snapshot'])
    try:
        base, token = _configuration(os.environ, 'PITO_NEWS_READ_TOKEN')
    except StrapiNewsError:
        current = Snapshot(status='not_configured')
    else:
        key = (base, token, os.environ.get('PITO_LOCAL_TEST'))
        with _reader_lock:
            if key != _reader_key:
                _reader = SnapshotReader(lambda: request_json(base, '/api/pito-news/snapshot', token), base_url=base)
                _reader_key = key
            reader = _reader
        current = reader.read(force)
    if not force and scope is not None:
        scope['snapshot'] = current
    return deepcopy(current)


def get():
    result = snapshot()
    return list(result.articles), result.status


def redirect(slug):
    return dict(snapshot().redirects).get(slug)


@contextmanager
def request_scope():
    token = _scope.set({})
    try:
        yield
    finally:
        _scope.reset(token)


def coherent_request(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        with request_scope():
            return method(*args, **kwargs)
    return wrapped


class DraftClient:
    """Draft-only ingress. The server enforces review and publish boundaries."""
    def __init__(self, base, token, transport=None):
        self.base, self.token = base, token
        self.transport = transport or request_json

    @classmethod
    def from_environment(cls, environment=None):
        environment = os.environ if environment is None else environment
        if not environment.get('PITO_STRAPI_URL') or not environment.get('PITO_NEWS_DRAFT_TOKEN'):
            return None
        return cls(*_configuration(environment, 'PITO_NEWS_DRAFT_TOKEN'))

    def submit(self, record):
        bundle = record['bundle']
        source = bundle['sources'][0]
        identity = str(record['id'])
        # An immutable local evidence revision is linked to a stable CMS draft.
        # Full source bodies and quotes remain in the private local store.
        import hashlib
        digest = hashlib.sha256(json.dumps(bundle, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        payload = {'externalKey': 'newsroom:'+identity, 'eventKey': bundle['event']['key'],
                   'title': bundle['title'], 'slug': record['slug'], 'summary': bundle['summary'],
                   'body': '\n\n'.join(p['text'] for p in bundle['paragraphs']),
                   'category': bundle['category'], 'municipalities': bundle['municipalities'],
                   'provinceWide': False, 'sourceUrl': source['url'], 'sourceName': source['name'],
                   'sourcePublishedAt': source['publishedAt'], 'eventDate': bundle['event']['date'],
                   'origin': 'writer',
                   'rights': 'Eigen feitelijke tekst; geen bronbeeld overgenomen; bronverwijzing vastgelegd.',
                   'sensitive': bool(bundle.get('sensitive')),
                   'additionalSources': [{'url': s['url'], 'name': s['name']} for s in bundle['sources'][1:]],
                   'evidenceReference': 'newsroom:'+identity+':'+digest,
                   'privateEvidence': {'localArticleId': identity, 'bundleSha256': digest,
                                       'sourceDigests': [s['sha256'] for s in bundle['sources']],
                                       'sourceCheckedAt': source['checkedAt'],
                                       'note': 'Automatisch schrijfconcept; menselijke beoordeling vereist'}}
        return self.submit_data(payload)

    def submit_data(self, payload):
        result = self.transport(self.base, '/api/pito-news/drafts', self.token, 'POST', {'data': payload})
        data = result.get('data') if isinstance(result, dict) else None
        if (not isinstance(data, dict) or not isinstance(data.get('documentId'), str)
                or not IDENTITY.fullmatch(data['documentId']) or data.get('status') != 'draft'
                or type(data.get('created')) is not bool):
            raise StrapiNewsError('CMS-concept niet bevestigd; dezelfde invoersleutel opnieuw proberen')
        return data
