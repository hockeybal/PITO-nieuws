"""Evidence-backed publication, independent of the legacy preview/CMS dataset.

The checks establish provenance, chronology and conservative publication gates.
They do not establish the semantic truth of arbitrary prose. Machine approval is
identified as such and is limited to explicitly configured primary-source hosts.
SQLite is authoritative; the JSON file is an atomic, rebuildable public export.
"""
import contextlib
import datetime as dt
import difflib
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
from urllib.parse import urlsplit, urlunsplit

UTC = dt.timezone.utc
POLICY_VERSION = 'evidence-publication-v1'
ROOT = Path(__file__).resolve().parent
REVIEW_CHECKS = ('facts', 'geography', 'dates', 'privacy', 'rights', 'wording')
STOPWORDS = set(('de het een en of te in op aan van voor door met om uit bij naar als is zijn wordt worden was waren heeft hebben had deze dit dat die er ook nog tot dan over onder tussen volgens meldt bekend maakte maakt kan kunnen zal zullen vanaf tijdens na per meer waar wie welke zich door hun ons onze bericht gemeente provincie nieuws bron informatie staat staan gaat gaan lokale aldus').split())
SENSITIVE = re.compile(r'\b(verdacht\w*|arrest\w*|aangehoud\w*|dodelijk\w*|overled\w*|zelfmoord\w*|su[iï]cid\w*|minderjarig\w*|kindermisbruik\w*|verkracht\w*|seksueel\w*|patient\w*|patiënt\w*|medisch\w*|slachtoffer\w*|gewond\w*|brand\w*|politie\w*|fraud\w*|corrupt\w*|schuld\w*|vermist\w*|vluchteling\w*|asiel\w*|verkiezing\w*)\b', re.I)
PRIVATE = re.compile(r'\b[1-9][0-9]{3}\s?[A-Z]{2}\b|\b[0-9]{9}\b|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|(?:\+31|0031|06)[\s.-]*(?:[0-9][\s.-]*){8,}', re.I)
CATEGORIES = {'Bestuur', 'Veiligheid', 'Verkeer', 'Wonen', 'Samenleving', 'Sport'}


class PublicationError(ValueError):
    pass


class DuplicateEvent(PublicationError):
    def __init__(self, article_id):
        self.article_id = article_id
        super().__init__('Gebeurtenis bestaat al: ' + article_id + '; gebruik revise, geen tweede artikel')


def utcnow():
    return dt.datetime.now(UTC)


def stamp(value=None):
    return (value or utcnow()).astimezone(UTC).isoformat()


def _date(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Datum ontbreekt')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        if len(value) != 10:
            raise ValueError('Tijdzone ontbreekt')
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normal(text):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def _tokens(text):
    return [x for x in _normal(text).split() if x not in STOPWORDS and len(x) > 2]


def body_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical_url(url):
    u = urlsplit(str(url))
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise ValueError('Publieke HTTPS-bron verplicht')
    host = u.hostname.lower().rstrip('.')
    if host in ('localhost', 'localhost.localdomain') or host.endswith(('.local', '.internal')):
        raise ValueError('Geen publieke bron')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError('Geen publiek bronadres')
    except ValueError as error:
        if str(error) == 'Geen publiek bronadres':
            raise
    if u.port not in (None, 443):
        raise ValueError('Niet-standaard bronpoort')
    return urlunsplit(('https', host, u.path.rstrip('/') or '/', u.query, ''))


def _municipalities():
    return {m['slug']: m['name'] for m in json.loads((ROOT/'data/municipalities.json').read_text())}


def _span(support, sources, errors, label):
    if not isinstance(support, dict):
        errors.append(label + ': ongeldig bewijsfragment')
        return ''
    source_id = support.get('sourceId')
    source = sources.get(source_id) if isinstance(source_id, str) else None
    start, end, quote = support.get('start'), support.get('end'), support.get('quote')
    if not source or type(start) is not int or type(end) is not int or not isinstance(quote, str):
        errors.append(label + ': bron, exacte tekst en tekenposities verplicht')
        return ''
    body = source.get('body', '')
    if not isinstance(body, str):
        errors.append(label + ': geen uitgelezen brontekst')
        return ''
    if start < 0 or end > len(body) or end <= start or len(quote.strip()) < 12 or body[start:end] != quote:
        errors.append(label + ': bewijsfragment komt niet overeen met brontekst')
        return ''
    return quote


def _grounded(text, support_text, label, errors, strict=False):
    """A conservative lexical screen, explicitly not a semantic fact checker."""
    words = set(_tokens(text))
    supported = set(_tokens(support_text))
    if not words or len(words & supported) / len(words) < (.8 if strict else .45):
        errors.append(label + ': onvoldoende tekstuele aansluiting op gekoppelde feiten')
    for number in re.findall(r'\b\d+(?:[.,:/-]\d+)*\b', text):
        if number not in re.findall(r'\b\d+(?:[.,:/-]\d+)*\b', support_text):
            errors.append(label + ': niet onderbouwd getal ' + number)
    for word in set(re.findall(r'\b(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag|januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\b', text, re.I)):
        if not re.search(r'\b'+re.escape(word)+r'\b', support_text, re.I):
            errors.append(label + ': niet onderbouwde dag of maand ' + word)
    # A frequent harmful change in rewriting is dropping a qualification.
    for qualifier in ('niet', 'geen', 'mogelijk', 'vermoedelijk', 'voorstel', 'voorgenomen', 'concept'):
        if re.search(r'\b'+qualifier+r'\b', support_text, re.I) and not re.search(r'\b'+qualifier+r'\b', text, re.I):
            errors.append(label + ': bronvoorbehoud ontbreekt (' + qualifier + ')')
    if re.search(r'\b(besloten|vastgesteld|goedgekeurd|veroordeeld)\b', text, re.I) and not re.search(r'\b(besloten|vastgesteld|goedgekeurd|veroordeeld)\b', support_text, re.I):
        errors.append(label + ': niet onderbouwde besluit- of schuldstatus')


def _event_date_supported(value, snippets, sources):
    """Screen event metadata against actual quoted dates, not writer flags.

    Dutch day/month notices often omit the year; in that case only the dated
    source's publication year is accepted. Relative dates require human review.
    This establishes the date's presence, not its semantic association with an
    arbitrary event; the prose/fact links and editorial checks remain necessary.
    """
    try:
        event = _date(value).date()
    except (ValueError, TypeError):
        return False
    text = '\n'.join(snippets)
    if re.search(r'(?<!\d)'+re.escape(event.isoformat())+r'(?!\d)', text):
        return True
    if re.search(r'\b0?'+str(event.day)+r'[/.-]0?'+str(event.month)+r'[/.-]'+str(event.year)+r'\b', text):
        return True
    months = ('januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus', 'september', 'oktober', 'november', 'december')
    month = months[event.month-1]
    name = '(?:'+month+'|'+month[:3]+r'\.?)'
    pattern = r'\b0?'+str(event.day)+r'(?:\s*(?:t/m|tot en met|tot|[-–])\s*\d{1,2})?\s+'+name+r'(?:\s+(\d{4}))?\b'
    source_years = set()
    for source in sources.values():
        try:
            source_years.add(_date(source.get('publishedAt')).year)
        except (ValueError, TypeError):
            pass
    for match in re.finditer(pattern, text, re.I):
        if (match.group(1) and int(match.group(1)) == event.year) or (not match.group(1) and event.year in source_years):
            return True
    return False


def validate_bundle(bundle, now=None, automated=False, auto_publish_hosts=()):
    """Return machine-check results; never accept serialized approval flags.

    A bundle contains extracted source bodies+SHA256, dated sources, exact spans
    supporting facts and municipality, and references from every written unit.
    """
    current = now or utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    errors, warnings = [], []
    if not isinstance(bundle, dict):
        return {'ok': False, 'errors': ['Bewijsdossier moet een object zijn'], 'warnings': [], 'policyVersion': POLICY_VERSION}
    for key, limit in (('title', 240), ('summary', 1800)):
        if not isinstance(bundle.get(key), str) or not bundle[key].strip() or len(bundle[key]) > limit:
            errors.append(key + ': ontbreekt of is te lang')
    if not isinstance(bundle.get('category'), str) or bundle.get('category') not in CATEGORIES:
        errors.append('Onbekende nieuwsrubriek')
    known = _municipalities()
    munis = bundle.get('municipalities')
    if not isinstance(munis, list) or not munis or any(not isinstance(m, str) or m not in known for m in munis):
        errors.append('Expliciete, bekende gemeente verplicht')
        munis = []
    event = bundle.get('event', {})
    if not isinstance(event, dict) or not isinstance(event.get('key'), str) or not 8 <= len(event['key']) <= 240:
        errors.append('Stabiele gebeurtenissleutel ontbreekt')
        event = {}
    try:
        _date(event.get('date'))
    except (ValueError, TypeError):
        errors.append('Gebeurtenisdatum ontbreekt of is ongeldig')
    raw_sources = bundle.get('sources', [])
    if not isinstance(raw_sources, list):
        raw_sources = []
    if len(raw_sources) > 30:
        errors.append('Te veel bronnen in één dossier')
        raw_sources = raw_sources[:30]
    sources = {}
    for source in raw_sources:
        if not isinstance(source, dict) or not isinstance(source.get('id'), str) or not source.get('id'):
            errors.append('Bronidentiteit ontbreekt')
            continue
        sid = source['id']
        if sid in sources:
            errors.append('Dubbele bronidentiteit: ' + sid)
        sources[sid] = source
        try:
            canonical_url(source.get('url'))
        except (ValueError, TypeError):
            errors.append(sid + ': ongeldige publieke bronlink')
        if not source.get('name'):
            errors.append(sid + ': bronnaam ontbreekt')
        body = source.get('body')
        if not isinstance(body, str) or len(body.strip()) < 160 or len(body) > 2_000_000:
            errors.append(sid + ': volledige uitgelezen brontekst ontbreekt (kop/RSS alleen is onvoldoende)')
        elif source.get('sha256') != body_digest(body):
            errors.append(sid + ': documentvingerafdruk klopt niet')
        try:
            published, checked = _date(source.get('publishedAt')), _date(source.get('checkedAt'))
            if published > current + dt.timedelta(minutes=5) or checked > current + dt.timedelta(minutes=5):
                errors.append(sid + ': toekomstige bron- of controledatum')
            if checked < published - dt.timedelta(days=1):
                errors.append(sid + ': brontekst gecontroleerd vóór bronpublicatie')
            if automated and (current-checked > dt.timedelta(hours=24) or current-published > dt.timedelta(days=14)):
                errors.append(sid + ': automatische publicatie vereist recent opgehaalde, recente bron')
        except (ValueError, TypeError):
            errors.append(sid + ': bevestigde bronpublicatie- en controledatum verplicht')
        if automated:
            host = (urlsplit(str(source.get('url', ''))).hostname or '').lower()
            if host not in {h.lower() for h in auto_publish_hosts} or source.get('kind') != 'official':
                errors.append(sid + ': automatische publicatie alleen vanaf expliciet geconfigureerde primaire bron')
            if source.get('rightsBasis') != 'facts_only':
                errors.append(sid + ': feitelijk hergebruik moet expliciet zijn vastgelegd')
    if not sources:
        errors.append('Geen brondocumenten')
    raw_facts = bundle.get('facts', [])
    if not isinstance(raw_facts, list):
        raw_facts = []
    facts, claims = {}, {}
    for fact in raw_facts:
        if not isinstance(fact, dict) or not isinstance(fact.get('id'), str) or not fact.get('id'):
            errors.append('Feitidentiteit ontbreekt')
            continue
        fid = fact['id']
        if fid in facts:
            errors.append('Dubbele feitidentiteit: ' + fid)
        facts[fid] = fact
        source_ids = fact.get('sourceIds', [])
        if not isinstance(source_ids, list) or any(not isinstance(s, str) for s in source_ids):
            source_ids = []
        if not source_ids or any(s not in sources for s in source_ids):
            errors.append(fid + ': gekoppelde bron ontbreekt')
        supports = fact.get('supports', [])
        if not isinstance(supports, list) or not supports:
            errors.append(fid + ': exacte bronfragmenten ontbreken; verified:true is onvoldoende')
            supports = []
        snippets = [_span(s, sources, errors, fid) for s in supports]
        if {s.get('sourceId') for s in supports if isinstance(s, dict) and isinstance(s.get('sourceId'), str)} != set(source_ids):
            errors.append(fid + ': elke genoemde bron moet een bewijsfragment hebben')
        if not isinstance(fact.get('statement'), str) or not fact['statement'].strip():
            errors.append(fid + ': feitelijke formulering ontbreekt')
        elif snippets:
            _grounded(fact['statement'], ' '.join(snippets), fid, errors, strict=automated)
        claim = fact.get('claim')
        if isinstance(claim, dict) and all(claim.get(k) for k in ('subject', 'predicate', 'value')):
            key = (_normal(claim['subject']), _normal(claim['predicate']))
            value = _normal(claim['value'])
            if key in claims and claims[key] != value:
                errors.append(fid + ': tegenstrijdige waarden voor hetzelfde feit')
            claims[key] = value
    if not facts:
        errors.append('Geen onderbouwde feiten')
    if automated:
        snippets = [support.get('quote', '') for fact in facts.values()
                    for support in (fact.get('supports') if isinstance(fact.get('supports'), list) else [])
                    if isinstance(support, dict) and isinstance(support.get('quote'), str)]
        if not _event_date_supported(event.get('date'), snippets, sources):
            errors.append('Automatische publicatie geblokkeerd: gebeurtenisdatum niet herleidbaar tot gedateerde bronfragmenten')
    municipal_support = {}
    for support in bundle.get('municipalityEvidence', []) if isinstance(bundle.get('municipalityEvidence', []), list) else []:
        quote = _span(support, sources, errors, 'Gemeenteduiding')
        municipality = support.get('municipality') if isinstance(support, dict) else None
        if isinstance(municipality, str) and municipality in known and quote:
            # A configured alias is allowed only when it is an existing place in
            # the project's locality map, never an untrusted bundle assertion.
            names = [known[municipality]]
            places_path = ROOT/'data/localities.json'
            if places_path.exists():
                places = json.loads(places_path.read_text())
                if isinstance(places, list):
                    names += [p.get('name', '') for p in places if isinstance(p, dict) and p.get('municipality') == municipality]
            if not any(_normal(n) and _normal(n) in _normal(quote) for n in names):
                errors.append('Gemeenteduiding: plaatsnaam staat niet in bewijsfragment')
            else:
                municipal_support[municipality] = True
    for municipality in munis:
        if municipality not in municipal_support:
            errors.append(municipality + ': onderbouwde lokale plaatsbepaling ontbreekt')
    paragraphs = bundle.get('paragraphs', [])
    if not isinstance(paragraphs, list) or not paragraphs:
        errors.append('Eigen artikelalinea’s ontbreken')
        paragraphs = []
    units = [('Kop', bundle.get('title', ''), bundle.get('titleFactIds')), ('Intro', bundle.get('summary', ''), bundle.get('summaryFactIds'))]
    for number, paragraph in enumerate(paragraphs, 1):
        if not isinstance(paragraph, dict):
            errors.append('Ongeldige alinea')
            continue
        units.append(('Alinea ' + str(number), paragraph.get('text', ''), paragraph.get('factIds')))
    article_text = '\n\n'.join(text for _, text, _ in units if isinstance(text, str))
    for label, text, ids in units:
        if not isinstance(text, str) or not text.strip() or len(text) > 12000:
            errors.append(label + ': tekst ontbreekt of is te lang')
        elif not isinstance(ids, list) or not ids or any(not isinstance(fid, str) or fid not in facts for fid in ids):
            errors.append(label + ': verwijzingen naar onderbouwde feiten ontbreken')
        else:
            _grounded(text, ' '.join(str(facts[fid].get('statement', '')) for fid in ids), label, errors, strict=automated)
    if len(' '.join(p.get('text', '') for p in paragraphs if isinstance(p, dict) and isinstance(p.get('text'), str)).split()) < 25:
        errors.append('Artikel bevat te weinig eigen inhoud; geen koppen- of RSS-publicatie')
    if '<' in article_text or '>' in article_text:
        errors.append('Artikeltekst moet platte tekst zijn')
    # No long copied sentence/paragraph, even if a bundle says rights approved.
    body_words = _normal(' '.join(p.get('text', '') for p in paragraphs if isinstance(p, dict) and isinstance(p.get('text'), str))).split()
    for source in sources.values():
        source_words = _normal(source.get('body', '')).split()
        matching = difflib.SequenceMatcher(None, body_words, source_words, autojunk=False).get_matching_blocks()
        copied = sum(block.size for block in matching if block.size >= 5)
        if any(block.size >= 14 for block in matching) or (copied > 25 and copied > len(body_words)*.35):
            errors.append(source.get('id', '') + ': te veel letterlijk overgenomen brontekst')
    source_context = '\n'.join(s.get('body', '') for s in sources.values() if isinstance(s.get('body'), str))
    # A writer cannot make a risky incident eligible by omitting its sensitive
    # words, names or qualifications from the proposed article and selected quote.
    sensitive = bool(bundle.get('sensitive')) or bool(SENSITIVE.search(article_text+'\n'+source_context)) or bundle.get('category') == 'Veiligheid'
    private = bool(PRIVATE.search(article_text+'\n'+source_context))
    if sensitive or private:
        warnings.append('Gevoelig onderwerp/persoonsgegevens: menselijke inhoudscontrole vereist')
        if automated:
            errors.append('Automatische publicatie geblokkeerd voor gevoelige onderwerpen of persoonsgegevens')
    if automated:
        for qualifier in ('niet', 'geen', 'mogelijk', 'vermoedelijk', 'voorstel', 'voorgenomen', 'concept',
                          'afgelast', 'geannuleerd', 'ingetrokken', 'uitgesteld', 'vervallen', 'rectificatie'):
            if re.search(r'\b'+qualifier+r'\b', source_context, re.I) and not re.search(r'\b'+qualifier+r'\b', article_text, re.I):
                errors.append('Automatische publicatie geblokkeerd: voorbehoud uit volledige brontekst ontbreekt ('+qualifier+')')
    if bundle.get('images'):
        from rights_review import image_review
        images = bundle['images'] if isinstance(bundle['images'], list) else []
        if not isinstance(bundle['images'], list):
            errors.append('Ongeldige beeldlijst')
        for image in images:
            if not isinstance(image, dict) or not image_review(image)['readyForPublication']:
                errors.append('Beeld heeft geen complete rechten- en privacycontrole')
        if automated:
            errors.append('Beeld wordt niet automatisch juridisch vrijgegeven')
    if automated and (bundle.get('category') not in ('Verkeer', 'Samenleving', 'Sport') or bundle.get('publicationScope') != 'public_service'):
        errors.append('Automatische publicatie beperkt tot expliciete laag-risico publieksinformatie')
    return {'ok': not errors, 'errors': list(dict.fromkeys(errors)), 'warnings': warnings,
            'policyVersion': POLICY_VERSION, 'checkedAt': stamp(current),
            'semanticTruthCertified': False, 'humanReviewed': False}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _fingerprint(bundle):
    raw_facts = bundle.get('facts', [])
    raw_municipalities = bundle.get('municipalities', [])
    facts = set(' '.join(_tokens(str(f.get('statement', '')))) for f in raw_facts if isinstance(f, dict)) if isinstance(raw_facts, list) else set()
    event_date = str(bundle.get('event', {}).get('date', ''))[:10]
    return {'municipalities': sorted(m for m in raw_municipalities if isinstance(m, str)) if isinstance(raw_municipalities, list) else [],
            'date': event_date, 'tokens': sorted(set(_tokens(str(bundle.get('title', '')) + ' ' + ' '.join(facts))))}


def _source_urls(bundle):
    result = set()
    sources = bundle.get('sources', [])
    for source in sources if isinstance(sources, list) else []:
        if isinstance(source, dict):
            try:
                result.add(canonical_url(source.get('url')))
            except (ValueError, TypeError):
                pass
    return result


def _same_event(a, b):
    if not set(a['municipalities']) & set(b['municipalities']) or a['date'] != b['date']:
        return False
    left, right = set(a['tokens']), set(b['tokens'])
    return len(left & right) >= 5 and len(left & right) / max(1, len(left | right)) >= .65


def _article(row):
    b = json.loads(row['bundle'])
    primary = b['sources'][0]
    approved_kind = row['approval_kind']
    return {'id': row['id'], 'slug': row['slug'], 'title': b['title'], 'summary': b['summary'],
            'body': '\n\n'.join(p['text'] for p in b['paragraphs']), 'category': b['category'],
            'municipalities': b['municipalities'], 'sourceUrl': primary['url'], 'sourceName': primary['name'],
            'sourcePublishedAt': primary['publishedAt'][:10], 'sourcePublishedAtExact': primary['publishedAt'],
            'eventDate': b['event']['date'][:10],
            'additionalSources': [{'url': s['url'], 'name': s['name'], 'publishedAt': s['publishedAt']} for s in b['sources'][1:]],
            'verifiedAt': row['updated_at'][:10], 'evidenceCheckedAt': row['updated_at'],
            'webPublishedAt': row['published_at'], 'publishedAt': row['published_at'],
            'modifiedAt': row['updated_at'], 'updatedAt': row['updated_at'], 'reviewStatus': 'approved',
            'publicationStatus': 'published', 'approvalKind': approved_kind,
            'reviewer': row['approved_by'] if approved_kind == 'human' else '',
            'humanReviewed': approved_kind == 'human', 'automated': approved_kind == 'machine',
            'author': 'PITO Nieuws' if approved_kind == 'human' else 'PITO Nieuws · automatisch samengesteld',
            'authorship': b.get('authorship', {'kind': 'automated'}), 'reviewNote': row['note'],
            'rights': 'Eigen feitelijke samenvatting; bronverwijzingen vastgelegd; geen bronbeeld overgenomen.',
            'sensitive': bool(b.get('sensitive')),
            'revision': row['revision'], 'evidenceDigest': body_digest(row['bundle']),
            'publicationPolicy': POLICY_VERSION, 'eventKey': row['event_key'],
            'ranking': {'cluster': row['event_key']}, 'priority': 3}


def read_published(data_dir):
    """Read private legacy releases for audit/migration, never public web state.

    An absent store has no published articles. A damaged store raises so callers
    can fail closed and report it; legacy articles are never imported here.
    """
    db = Path(data_dir)/'publication.sqlite3'
    if not db.exists():
        return []
    connection = sqlite3.connect(db.resolve().as_uri()+'?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [_article(row) for row in connection.execute("SELECT * FROM articles WHERE status='published' ORDER BY published_at DESC,id")]
    finally:
        connection.close()


class PublicationStore:
    def __init__(self, data_dir, auto_publish_hosts=(), now=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir/'publication.sqlite3'
        self.auto_publish_hosts = tuple(auto_publish_hosts)
        self._clock = now or utcnow
        with self._locked() as con:
            con.executescript('''
              CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,slug TEXT NOT NULL UNIQUE,event_key TEXT NOT NULL UNIQUE,
                fingerprint TEXT NOT NULL,bundle TEXT NOT NULL,status TEXT NOT NULL,
                revision INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
                published_at TEXT,approved_by TEXT,approval_kind TEXT,approval_revision INTEGER,
                note TEXT NOT NULL DEFAULT '');
              CREATE TABLE IF NOT EXISTS audit (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,article_id TEXT NOT NULL,
                action TEXT NOT NULL,actor TEXT NOT NULL,at TEXT NOT NULL,revision INTEGER NOT NULL,
                note TEXT NOT NULL,snapshot TEXT NOT NULL);
            ''')

    @contextlib.contextmanager
    def _locked(self):
        lock_fd = os.open(str(self.data_dir/'publication.lock'), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, 'a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not self.path.exists():
                # This database contains private full source documents and
                # immutable review history, not just the public article pool.
                descriptor = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(descriptor)
            con = sqlite3.connect(self.path, timeout=30)
            con.row_factory = sqlite3.Row
            con.execute('PRAGMA foreign_keys=ON')
            con.execute('PRAGMA synchronous=FULL')
            try:
                yield con
            finally:
                con.close()

    def _check(self, bundle, automated=False):
        return validate_bundle(bundle, now=self._clock(), automated=automated, auto_publish_hosts=self.auto_publish_hosts)

    @staticmethod
    def _actor(actor):
        if not isinstance(actor, str) or not 2 <= len(actor.strip()) <= 160:
            raise PublicationError('Identificeer de handelende gebruiker of automatisering')
        return actor.strip()

    def _row(self, con, article_id):
        row = con.execute('SELECT * FROM articles WHERE id=? OR slug=?', (article_id, article_id)).fetchone()
        if not row:
            raise PublicationError('Artikel bestaat niet')
        return row

    def _audit(self, con, article_id, action, actor, note):
        row = self._row(con, article_id)
        con.execute('INSERT INTO audit(article_id,action,actor,at,revision,note,snapshot) VALUES(?,?,?,?,?,?,?)',
                    (row['id'], action, actor, stamp(self._clock()), row['revision'], note, _json(dict(row))))

    def _duplicate(self, con, bundle, exclude=None):
        key = _normal(bundle.get('event', {}).get('key', ''))
        fp = _fingerprint(bundle)
        urls = _source_urls(bundle)
        for row in con.execute('SELECT * FROM articles'):
            if row['id'] == exclude:
                continue
            old = json.loads(row['bundle'])
            old_urls = _source_urls(old)
            if row['event_key'] == key or urls & old_urls or _same_event(fp, json.loads(row['fingerprint'])):
                raise DuplicateEvent(row['id'])

    def submit(self, bundle, actor='pipeline'):
        actor = self._actor(actor)
        # JSON roundtrip removes caller references and rejects unserializable state.
        bundle = json.loads(_json(bundle))
        checks = self._check(bundle)
        if not isinstance(bundle, dict) or not isinstance(bundle.get('event'), dict) or not isinstance(bundle['event'].get('key'), str) or not _normal(bundle['event']['key']):
            raise PublicationError('Een stabiele gebeurtenissleutel is vereist, ook voor een geblokkeerd concept')
        event_key = _normal(bundle['event']['key'])
        article_id = 'pito-' + body_digest(event_key)[:20]
        slug = '-'.join(_normal(bundle.get('title', 'bericht')).split())[:100] + '-' + article_id[-8:]
        with self._locked() as con, con:
            con.execute('BEGIN IMMEDIATE')
            self._duplicate(con, bundle)
            now = stamp(self._clock())
            con.execute('INSERT INTO articles(id,slug,event_key,fingerprint,bundle,status,revision,created_at,updated_at,note) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (article_id, slug, event_key, _json(_fingerprint(bundle)), _json(bundle), 'draft', 1, now, now, 'Bewijscontrole: '+('; '.join(checks['errors']) or 'geslaagd; nog niet goedgekeurd')))
            self._audit(con, article_id, 'draft', actor, 'Concept opgeslagen; geen publicatie')
        result = self.get(article_id)
        result['checks'] = checks
        return result

    def get(self, article_id):
        with self._locked() as con:
            row = dict(self._row(con, article_id))
        row['bundle'] = json.loads(row['bundle'])
        row['fingerprint'] = json.loads(row['fingerprint'])
        return row

    def list(self, status=None):
        with self._locked() as con:
            rows = con.execute('SELECT * FROM articles'+(' WHERE status=?' if status else '')+' ORDER BY updated_at DESC', (status,) if status else ()).fetchall()
            result = [dict(row) for row in rows]
        for row in result:
            row['bundle'] = json.loads(row['bundle'])
            row['checks'] = self._check(row['bundle'])
        return result

    def review(self, article_id, actor, decision='approve', note='', automated=False, checks=None):
        actor = self._actor(actor)
        if decision not in ('approve', 'reject') or not isinstance(note, str) or not note.strip():
            raise PublicationError('Besluit en concrete controlenotitie vereist')
        if decision == 'approve' and not automated and (not isinstance(checks, dict) or any(checks.get(k) is not True for k in REVIEW_CHECKS)):
            raise PublicationError('Een menselijke redacteur moet feiten, plaats, datum, privacy, rechten en formulering bevestigen')
        with self._locked() as con, con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, article_id)
            if row['status'] not in ('draft', 'rejected'):
                raise PublicationError('Alleen ongepubliceerde concepten kunnen worden beoordeeld')
            if decision == 'approve':
                result = self._check(json.loads(row['bundle']), automated)
                if not result['ok']:
                    raise PublicationError('; '.join(result['errors']))
            con.execute('UPDATE articles SET status=?,approved_by=?,approval_kind=?,approval_revision=?,updated_at=?,note=? WHERE id=?',
                        ('approved' if decision == 'approve' else 'rejected', actor if decision == 'approve' else None,
                         ('machine' if automated else 'human') if decision == 'approve' else None,
                         row['revision'] if decision == 'approve' else None, stamp(self._clock()), note.strip(), row['id']))
            self._audit(con, row['id'], 'approve' if decision == 'approve' else 'reject', actor, note.strip())
        return self.get(article_id)

    def publish(self, article_id, actor, automated=False):
        actor = self._actor(actor)
        with self._locked() as con, con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, article_id)
            if row['status'] != 'approved' or row['approval_revision'] != row['revision']:
                raise PublicationError('Publicatie vereist goedkeuring van precies deze revisie')
            machine = row['approval_kind'] == 'machine'
            if machine and not automated:
                raise PublicationError('Machinegoedkeuring vereist een expliciete automatische publicatieopdracht')
            result = self._check(json.loads(row['bundle']), automated or machine)
            if not result['ok']:
                raise PublicationError('; '.join(result['errors']))
            now = stamp(self._clock())
            con.execute("UPDATE articles SET status='published',published_at=COALESCE(published_at,?),updated_at=? WHERE id=?", (now, now, row['id']))
            self._audit(con, row['id'], 'publish', actor, row['note'])
        return self._finish(article_id)

    def revise(self, article_id, bundle, actor, reason):
        actor = self._actor(actor)
        if not isinstance(reason, str) or not reason.strip():
            raise PublicationError('Een correctie- of wijzigingsreden is verplicht')
        bundle = json.loads(_json(bundle))
        result = self._check(bundle)
        if not result['ok']:
            raise PublicationError('; '.join(result['errors']))
        with self._locked() as con, con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, article_id)
            if _normal(bundle['event']['key']) != row['event_key']:
                raise PublicationError('Een revisie moet dezelfde gebeurtenissleutel behouden')
            self._duplicate(con, bundle, exclude=row['id'])
            con.execute("UPDATE articles SET bundle=?,fingerprint=?,status='draft',revision=revision+1,approved_by=NULL,approval_kind=NULL,approval_revision=NULL,updated_at=?,note=? WHERE id=?",
                        (_json(bundle), _json(_fingerprint(bundle)), stamp(self._clock()), reason.strip(), row['id']))
            self._audit(con, row['id'], 'revise', actor, reason.strip())
        # A revision is withheld until re-approved; old publication time remains.
        return self._finish(article_id)

    def retract(self, article_id, actor, reason):
        actor = self._actor(actor)
        if not isinstance(reason, str) or not reason.strip():
            raise PublicationError('Intrekkingsreden verplicht')
        with self._locked() as con, con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, article_id)
            if row['status'] == 'retracted':
                return dict(row)
            con.execute("UPDATE articles SET status='retracted',updated_at=?,note=? WHERE id=?", (stamp(self._clock()), reason.strip(), row['id']))
            self._audit(con, row['id'], 'retract', actor, reason.strip())
        return self._finish(article_id)

    def _finish(self, article_id):
        result = self.get(article_id)
        try:
            self.export_articles()
        except OSError as error:
            # State and audit are committed. Readers use SQLite so a failed JSON
            # export cannot keep a retracted story public or lose a correction.
            result['exportWarning'] = 'Database bijgewerkt; JSON-export opnieuw uitvoeren: ' + str(error)
        return result

    def export_articles(self):
        with self._locked() as con:
            rows = [_article(row) for row in con.execute("SELECT * FROM articles WHERE status='published' ORDER BY published_at DESC,id")]
            fd, name = tempfile.mkstemp(prefix='.published-', suffix='.json', dir=self.data_dir)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as out:
                    json.dump(rows, out, ensure_ascii=False, indent=2)
                    out.write('\n')
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(name, self.data_dir/'published-articles.json')
                directory = os.open(str(self.data_dir), os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        return rows

    def audit(self, article_id=None):
        with self._locked() as con:
            rows = con.execute('SELECT * FROM audit'+(' WHERE article_id=?' if article_id else '')+' ORDER BY sequence', (article_id,) if article_id else ()).fetchall()
            return [dict(row, snapshot=json.loads(row['snapshot'])) for row in rows]
