"""Read-only WSGI application for the public site, behind an HTTPS proxy.

Run with Python 3.10+ and Gunicorn, never with the preview HTTP server::

    PITO_SITE_MODE=production PITO_STANDALONE=1 \
    PITO_PUBLIC_URL=https://pitonieuws.nl \
    gunicorn --bind 127.0.0.1:4201 'production_app:create_app()'

The established GET renderers are shared with the local preview. This entry
point owns the HTTP boundary: no editor, submission API, audit files, preview
HTML or arbitrary filesystem paths are exposed. Static files stream in bounded
chunks; video seeking does not load a whole film into a worker's memory.
"""
from dataclasses import dataclass
from email.utils import formatdate, parsedate_to_datetime
from http import HTTPStatus
import logging
import mimetypes
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, unquote, urlsplit


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
PORTABLE = ROOT / 'portable-assets'
LOGGER = logging.getLogger('pito.web')
CHUNK_SIZE = 65536
PUBLIC_EXTENSIONS = frozenset({
    '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.avif',
    '.ico', '.mp4', '.woff', '.woff2', '.ttf', '.otf',
})
PRIVATE_ROUTES = (
    '/nieuws/redactie', '/nieuws/onderzoek', '/nieuws/beeldbibliotheek',
    '/nieuws/seo-controle', '/nieuws/bronberichten', '/nieuws/aanvoerstatus',
)
SECURITY_HEADERS = (
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('Referrer-Policy', 'strict-origin-when-cross-origin'),
    ('Permissions-Policy', 'camera=(), microphone=(), geolocation=(self)'),
    ('Cross-Origin-Resource-Policy', 'same-origin'),
    ('Strict-Transport-Security', 'max-age=15552000'),
    ('Content-Security-Policy', "default-src 'self'; script-src 'self'; "
     "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
     "font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; "
     "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"),
)


@dataclass
class Response:
    status: int
    headers: list
    body: object


def text_response(text, status=200, content_type='text/plain; charset=utf-8', headers=()):
    body = text.encode('utf-8') if isinstance(text, str) else bytes(text)
    return Response(status, [('Content-Type', content_type),
                             ('Content-Length', str(len(body))),
                             ('Cache-Control', 'no-cache')] + list(headers), [body])


def _normalized_target(environ):
    """Decode exactly once, accounting for already-decoded WSGI PATH_INFO."""
    raw = environ.get('RAW_URI') or environ.get('REQUEST_URI')
    query = environ.get('QUERY_STRING', '')
    if raw:
        raw_path, _, _raw_query = raw.partition('?')
        if (re.search(r'%(?![0-9a-fA-F]{2})', raw_path)
                or re.search(r'%(?:2f|5c)', raw_path, re.I)):
            raise ValueError('Invalid encoded path')
        path = unquote(raw_path, encoding='utf-8', errors='strict')
    else:
        # PEP 3333 has already percent-decoded PATH_INFO. Do not decode again.
        path = environ.get('PATH_INFO', '/')
    if len(path) > 4096 or len(query) > 4096:
        raise ValueError('Request target too long')
    if (not path.startswith('/') or path.startswith('//') or '//' in path
            or any(ord(c) < 32 or ord(c) == 127 for c in path + query)
            or any(c in path for c in ('\\', '%', '#', '?'))):
        raise ValueError('Invalid path')
    if any(part.startswith('.') for part in path.split('/') if part):
        raise ValueError('Hidden or relative path')
    return path.rstrip('/') or '/', query


def _private(path):
    if any(path == prefix or path.startswith(prefix + '/') for prefix in PRIVATE_ROUTES):
        return True
    if (path == '/api' or path.startswith('/api/')) and path != '/api/weather':
        return True
    return False


def _date_matches(value, modified):
    try:
        stamp = parsedate_to_datetime(value)
        return stamp.tzinfo is not None and stamp.timestamp() >= int(modified)
    except (ValueError, TypeError, OverflowError):
        return False


def _range(value, size):
    if len(value) > 128:
        raise ValueError('Invalid range')
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
    if not match or not any(match.groups()) or size == 0:
        raise ValueError('Invalid range')
    first, last = match.groups()
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:
        suffix = int(last)
        if suffix == 0:
            raise ValueError('Empty range')
        start, end = max(0, size - suffix), size - 1
    if start > end or start >= size:
        raise ValueError('Unsatisfiable range')
    return start, end


class FileChunks:
    """WSGI iterable that closes immediately when a client aborts its stream."""
    def __init__(self, stream, remaining):
        self.stream = stream
        self.remaining = remaining

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining <= 0:
            self.close()
            raise StopIteration
        chunk = self.stream.read(min(CHUNK_SIZE, self.remaining))
        if not chunk:
            self.close()
            raise StopIteration
        self.remaining -= len(chunk)
        return chunk

    def close(self):
        self.stream.close()


def static_response(base, relative, environ):
    base = Path(base).resolve()
    target = (base / relative).resolve()
    if (base not in target.parents or not target.is_file()
            or any(part.startswith('.') for part in Path(relative).parts)
            or any(part in ('source-audit', 'local-audit') for part in Path(relative).parts)
            or (target.suffix.lower() not in PUBLIC_EXTENSIONS
                and not (base == STATIC.resolve() and relative == 'utrecht-boundaries.json'))):
        return text_response('Niet gevonden', 404)
    stream = target.open('rb')
    try:
        stat = os.fstat(stream.fileno())
        size = stat.st_size
        etag = '"{:x}-{:x}"'.format(stat.st_mtime_ns, size)
        headers = [('Content-Type', mimetypes.guess_type(str(target))[0] or 'application/octet-stream'),
                   ('Cache-Control', 'public, max-age=' + ('3600' if target.suffix in ('.css', '.js') else '86400')),
                   ('ETag', etag), ('Last-Modified', formatdate(stat.st_mtime, usegmt=True)),
                   ('Accept-Ranges', 'bytes')]
        none_match = environ.get('HTTP_IF_NONE_MATCH')
        matches = none_match and any(v.strip().removeprefix('W/') in (etag, '*')
                                     for v in none_match.split(','))
        if matches or (not none_match and _date_matches(environ.get('HTTP_IF_MODIFIED_SINCE'), stat.st_mtime)):
            stream.close()
            return Response(304, headers, [])
        start, end, status = 0, size - 1, 200
        requested = environ.get('HTTP_RANGE')
        if_range = environ.get('HTTP_IF_RANGE')
        if requested and (not if_range or if_range == etag or _date_matches(if_range, stat.st_mtime)):
            try:
                start, end = _range(requested, size)
            except ValueError:
                stream.close()
                return text_response('Ongeldig bereik', 416,
                                     headers=[('Content-Range', f'bytes */{size}'), ('Accept-Ranges', 'bytes')])
            status = 206
            headers.append(('Content-Range', f'bytes {start}-{end}/{size}'))
        length = max(0, end - start + 1)
        headers.append(('Content-Length', str(length)))
        if environ.get('REQUEST_METHOD') == 'HEAD':
            stream.close()
            return Response(status, headers, [])
        stream.seek(start)
        # Native file_wrapper can use sendfile for complete assets. Partial
        # responses need a bounded iterator so they cannot spill beyond Range.
        wrapper = environ.get('wsgi.file_wrapper')
        body = wrapper(stream, CHUNK_SIZE) if wrapper and status == 200 else FileChunks(stream, length)
        return Response(status, headers, body)
    except BaseException:
        stream.close()
        raise


def _static_target(path):
    if path.startswith('/news-static/'):
        return STATIC, path[len('/news-static/'):]
    if path == '/style.css':
        return PORTABLE, 'style.css'
    if path.startswith(('/build/', '/media/', '/preview-assets/')):
        return PORTABLE, path.lstrip('/')
    return None


def _renderer_type():
    import server
    import portable_handler
    if portable_handler.Handler not in server.Handler.__mro__:
        raise RuntimeError('Start de productieapp in een apart proces met PITO_STANDALONE=1.')

    class Renderer(server.Handler):
        # No BaseHTTPRequestHandler constructor, socket, rfile or writable API.
        def __init__(self, path, environ):
            self.path = path
            self.headers = {key[5:].replace('_', '-').title(): value
                            for key, value in environ.items() if key.startswith('HTTP_')}
            self.response = None

        def allowed(self):
            return True  # Host was already checked at the WSGI boundary.

        def send(self, data, typ='text/html; charset=utf-8', status=200):
            self.response = text_response(data, status, typ)
            return self.response

        def redirect(self, target, status=302):
            self.response = text_response('', status, headers=[('Location', target)])
            return self.response

        def file(self, basepath, relative):
            # All public asset paths are handled before entering the renderer.
            return self.send('Niet gevonden', status=404)

    return Renderer


def create_app():
    """Gunicorn application factory; fail closed before accepting requests."""
    if sys.version_info < (3, 10):
        raise RuntimeError('De productieapp vereist Python 3.10 of nieuwer.')
    if os.environ.get('PITO_SITE_MODE') != 'production':
        raise RuntimeError('PITO_SITE_MODE=production is verplicht voor de publieke WSGI-app.')
    origin = os.environ.get('PITO_PUBLIC_URL', '').rstrip('/')
    public = urlsplit(origin)
    if (public.scheme != 'https' or public.netloc not in ('pitonieuws.nl', 'www.pitonieuws.nl')
            or public.path or public.query or public.fragment):
        raise RuntimeError('PITO_PUBLIC_URL moet https://pitonieuws.nl of https://www.pitonieuws.nl zijn.')
    if os.environ.get('PITO_STANDALONE') != '1':
        raise RuntimeError('PITO_STANDALONE=1 is verplicht voor de zelfstandige productieapp.')
    if os.environ.get('PITO_EDITION_DATE'):
        raise RuntimeError('PITO_EDITION_DATE is alleen voor tests en lokale preview; verwijder dit uit productie.')
    local_test = os.environ.get('PITO_LOCAL_TEST') == '1'
    local_port = os.environ.get('PITO_LOCAL_TEST_PORT', '4201')
    if local_test and local_port not in ('4201', '4202', '4212'):
        raise RuntimeError('Lokale testpoort moet 4201, 4202 of 4212 zijn.')
    renderer = _renderer_type()
    weather_cache = os.environ.get('PITO_WEATHER_CACHE')
    if weather_cache:
        import weather
        weather.CACHE = Path(weather_cache)

    def application(environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        local_request = (local_test and environ.get('REMOTE_ADDR') in ('127.0.0.1', '::1')
                         and environ.get('HTTP_HOST', '').lower() in
                         tuple(host+':'+local_port for host in ('127.0.0.1', 'localhost', '[::1]')))
        try:
            # Modules consult the process environment for publication policy.
            # An accidental runtime change must never turn this into a preview.
            if (os.environ.get('PITO_SITE_MODE') != 'production'
                    or os.environ.get('PITO_PUBLIC_URL', '').rstrip('/') != origin
                    or os.environ.get('PITO_EDITION_DATE')):
                response = text_response('Website tijdelijk niet beschikbaar', 503)
            elif not local_request and environ.get('HTTP_HOST', '').lower() not in (public.netloc, public.netloc + ':443'):
                response = text_response('Ongeldige host', 421)
            elif method not in ('GET', 'HEAD'):
                response = text_response('Deze actie is niet beschikbaar', 405, headers=[('Allow', 'GET, HEAD')])
            else:
                try:
                    path, query = _normalized_target(environ)
                except (ValueError, UnicodeError):
                    response = text_response('Ongeldige URL', 400)
                else:
                    secure = local_request or environ.get('wsgi.url_scheme') == 'https'
                    if environ.get('REMOTE_ADDR') in ('127.0.0.1', '::1'):
                        secure = secure or environ.get('HTTP_X_FORWARDED_PROTO') == 'https'
                    if _private(path):
                        response = text_response('Niet gevonden', 404)
                    elif not secure:
                        from urllib.parse import quote
                        target = origin + quote(path, safe='/') + ('?' + query if query else '')
                        response = text_response('', 308, headers=[('Location', target)])
                    elif _static_target(path):
                        response = static_response(*_static_target(path), environ)
                    else:
                        page = renderer(path + ('?' + query if query else ''), environ)
                        page.do_GET()
                        response = page.response or text_response('Niet gevonden', 404)
                    if any(parse_qs(query).get(k) for k in ('q', 'categorie', 'status', 'onderwerp')):
                        response.headers.append(('X-Robots-Tag', 'noindex, follow'))
        except Exception:
            LOGGER.exception('PITO public request failed')
            response = text_response('Website tijdelijk niet beschikbaar', 500)
        headers = response.headers + list(SECURITY_HEADERS)
        if local_request:
            headers = [(name, value) for name, value in headers if name != 'X-Robots-Tag']
            headers.append(('X-Robots-Tag', 'noindex, nofollow'))
        start_response(f'{response.status} {HTTPStatus(response.status).phrase}', headers)
        if method == 'HEAD':
            if hasattr(response.body, 'close'):
                response.body.close()
            return []
        return response.body

    return application
