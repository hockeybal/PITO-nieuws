"""Bounded Firecrawl v2 reader. No background crawls or implicit paid retries."""
import http.client
import ipaddress
import json
import os
import socket
import ssl
from urllib.parse import urlsplit, urldefrag

from scripts.source_security import safe_external_url

MAX_RESPONSE = 4_000_000


class FirecrawlError(ValueError):
    pass


def public_url(url):
    """Check targets before handing them to an external browser service."""
    if not safe_external_url(url):
        raise FirecrawlError('Firecrawl vereist een publieke HTTPS-bronlink')
    host = urlsplit(url).hostname
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError()
    except (OSError, ValueError):
        raise FirecrawlError('Bronadres is niet publiek of niet bereikbaar via DNS') from None
    return url


def request_json(token, payload):
    connection = http.client.HTTPSConnection('api.firecrawl.dev', timeout=35, context=ssl.create_default_context())
    try:
        connection.request('POST', '/v2/scrape', json.dumps(payload).encode(), {
            'Authorization': 'Bearer '+token, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            raise FirecrawlError('Firecrawl-verzoek niet voltooid (HTTP '+str(response.status)+')')
        if response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise FirecrawlError('Firecrawl gaf geen JSON terug')
        raw = response.read(MAX_RESPONSE+1)
        if len(raw) > MAX_RESPONSE:
            raise FirecrawlError('Firecrawl-antwoord overschrijdt de leeslimiet')
        return json.loads(raw)
    except FirecrawlError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        # Provider bodies and exception messages may contain credentials.
        raise FirecrawlError('Firecrawl-verbinding mislukt of antwoord ongeldig') from None
    finally:
        connection.close()


class FirecrawlClient:
    def __init__(self, token, max_requests=10, transport=None, validate_url=None):
        if not isinstance(token, str) or not 1 <= len(token) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise FirecrawlError('FIRECRAWL_API_KEY ontbreekt of is ongeldig')
        if type(max_requests) is not int or not 1 <= max_requests <= 50:
            raise FirecrawlError('Firecrawl-limiet moet tussen 1 en 50 liggen')
        self.token, self.max_requests = token, max_requests
        self.transport = transport or request_json
        self.validate_url = validate_url or public_url
        self.requests = 0
        self._cache = {}

    @classmethod
    def from_environment(cls, environment=None):
        env = os.environ if environment is None else environment
        if env.get('PITO_FIRECRAWL_ENABLED') == '0':
            raise FirecrawlError('Firecrawl is op verzoek uitgeschakeld; geen nieuwe betaalde verzoeken toegestaan')
        try:
            limit = int(env.get('PITO_FIRECRAWL_MAX_REQUESTS', '10'))
        except (ValueError, TypeError):
            raise FirecrawlError('Firecrawl-limiet is ongeldig') from None
        return cls(env.get('FIRECRAWL_API_KEY', ''), max_requests=limit)

    def _scrape(self, url, format):
        key = (url, format)
        if key in self._cache:
            return self._cache[key]
        self.validate_url(url)
        if self.requests >= self.max_requests:
            raise FirecrawlError('Firecrawl-verzoeklimiet voor deze uitvoering bereikt')
        self.requests += 1
        try:
            result = self.transport(self.token, {
                'url': url, 'formats': ['rawHtml', 'links'] if format == 'page' else [format], 'onlyMainContent': False,
                'timeout': 25000, 'maxAge': 0, 'storeInCache': False,
                'skipTlsVerification': False, 'parsers': [],
            })
        except FirecrawlError:
            raise
        except Exception:
            raise FirecrawlError('Firecrawl-verzoek onderbroken') from None
        if not isinstance(result, dict) or result.get('success') is not True or not isinstance(result.get('data'), dict):
            raise FirecrawlError('Firecrawl bevestigde geen geslaagde bronlezing')
        data = result['data']
        metadata = data.get('metadata')
        if not isinstance(metadata, dict) or type(metadata.get('statusCode')) is not int or metadata['statusCode'] != 200 or metadata.get('error'):
            raise FirecrawlError('Firecrawl-bronpagina niet succesvol opgehaald')
        # Do not attach evidence from a login page or an unexpected redirect.
        if metadata.get('sourceURL') != url:
            raise FirecrawlError('Firecrawl bevestigde de aangevraagde bronlink niet')
        if metadata.get('url') and urldefrag(metadata['url'])[0] != urldefrag(url)[0]:
            raise FirecrawlError('Firecrawl-bronpagina is omgeleid; controleer de bronlink')
        if format == 'page':
            raw, links = data.get('rawHtml'), data.get('links')
            if not isinstance(raw, str) or not raw or len(raw.encode()) > 2_000_000 or '\x00' in raw:
                raise FirecrawlError('Firecrawl gaf geen bruikbaar volledig HTML-document')
            if not isinstance(links, list) or len(links) > 10000 or any(not isinstance(v, str) for v in links):
                raise FirecrawlError('Firecrawl gaf geen bruikbare bronlinks')
            value = {'rawHtml': raw.encode(), 'links': links}
            self._cache[(url, 'rawHtml')] = value['rawHtml']
            self._cache[(url, 'links')] = links
        else:
            value = data.get(format)
        if format == 'rawHtml':
            if not isinstance(value, str) or not value or len(value.encode()) > 2_000_000 or '\x00' in value:
                raise FirecrawlError('Firecrawl gaf geen bruikbaar volledig HTML-document')
            value = value.encode()
        elif format != 'page':
            if not isinstance(value, list) or len(value) > 10000 or any(not isinstance(v, str) for v in value):
                raise FirecrawlError('Firecrawl gaf geen bruikbare bronlinks')
        self._cache[key] = value
        return value

    def article_html(self, url):
        return self._scrape(url, 'rawHtml')

    def links(self, url):
        return self._scrape(url, 'links')

    def page(self, url):
        return self._scrape(url, 'page')
