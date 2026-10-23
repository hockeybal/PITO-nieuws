"""Loopback-only website against the isolated Strapi E2E session; no live writes.

python3 scripts/start_strapi_test.py /private/tmp/<cms-test>/session.json
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit
from wsgiref.simple_server import make_server


def _allow_local_cms_images(application, origin):
    """Test-process CSP exception for the already validated loopback CMS."""
    def local_application(environ, start_response):
        def local_response(status, headers, exc_info=None):
            local_headers = []
            for name, value in headers:
                if name.lower() == 'content-security-policy':
                    directives = value.split(';')
                    for index, directive in enumerate(directives):
                        parts = directive.split()
                        if parts and parts[0] == 'img-src' and origin not in parts:
                            directives[index] = directive+' '+origin
                    value = ';'.join(directives)
                local_headers.append((name, value))
            if exc_info is not None:
                return start_response(status, local_headers, exc_info)
            return start_response(status, local_headers)
        return application(environ, local_response)
    return local_application


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('--port', type=int, choices=(4202, 4212), default=4212)
    args = parser.parse_args(argv)
    session = json.loads(args.session.read_text())
    url = session['url'].rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Alleen een afzonderlijke lokale Strapi-testsessie is toegestaan')
    runtime = Path(tempfile.mkdtemp(prefix='pito-news-strapi-runtime-'))
    # All values are scoped to this child process. Existing services are untouched.
    os.environ.update(PITO_STANDALONE='1', PITO_SITE_MODE='production', PITO_LOCAL_TEST='1',
        PITO_LOCAL_TEST_PORT=str(args.port), PITO_PUBLIC_URL='https://pitonieuws.nl', PITO_STRAPI_URL=url,
        PITO_NEWS_READ_TOKEN=session['readToken'], PITO_APP_CONTENT_URL=url+'/api/pito-app-content/snapshot',
        PITO_APP_CONTENT_TOKEN=session['appContentToken'], PITO_WEATHER_CACHE=str(runtime/'weather.json'))
    for key in ('PITO_EDITION_DATE', 'PITO_PUBLIC_PREVIEW', 'PITO_NEWS_DRAFT_TOKEN', 'PITO_WRITER_API_KEY', 'OPENAI_API_KEY', 'PITO_WRITER_MODEL'):
        os.environ.pop(key, None)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import weather
    weather.CACHE = runtime/'weather.json'
    weather.get = lambda: {'status': 'unavailable', 'station': 'De Bilt', 'source': 'KNMI'}
    import production_app
    application = _allow_local_cms_images(production_app.create_app(), parsed.scheme+'://'+parsed.netloc)
    print('Lokale Strapi-website: http://127.0.0.1:'+str(args.port)+'/nieuws/utrecht', flush=True)
    print('Eigen runtime: '+str(runtime)+'; geen productiegegevens aangepast.', flush=True)
    with make_server('127.0.0.1', args.port, application) as server:
        server.serve_forever()


if __name__ == '__main__': main()
