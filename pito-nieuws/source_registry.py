"""Private Strapi source registry; an unavailable registry never uses local defaults."""
import re
from urllib.parse import urlsplit

import strapi_news
from scripts.source_security import safe_external_url

SOURCE_FIELDS = ('sourceKey', 'name', 'url', 'feed', 'kind', 'articleHosts', 'municipality',
                 'coverageCandidates', 'active', 'reader', 'discovery', 'articlePathPrefix', 'maxLinks')
HOST = re.compile(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\Z')


def validate_source(row):
    if not isinstance(row, dict):
        raise ValueError('Ongeldige Strapi-bron')
    for key, maximum in (('sourceKey', 180), ('name', 240), ('kind', 120), ('url', 4096)):
        if not isinstance(row.get(key), str) or not row[key].strip() or len(row[key]) > maximum:
            raise ValueError('Strapi-bron heeft ongeldig veld '+key)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,180}', row['sourceKey']) or not safe_external_url(row['url']):
        raise ValueError('Strapi-bron heeft ongeldige identiteit of URL')
    if row.get('feed') and not safe_external_url(row['feed']):
        raise ValueError('Strapi-bron heeft ongeldige feed-URL')
    if type(row.get('active')) is not bool or row.get('reader') not in ('direct', 'firecrawl') or row.get('discovery') not in ('rss', 'page', 'manual'):
        raise ValueError('Strapi-bron heeft ongeldige verwerking')
    if row['discovery'] == 'rss' and not row.get('feed'):
        raise ValueError('Een RSS-bron vereist een feed-URL')
    hosts = row.get('articleHosts')
    if not isinstance(hosts, list) or not 1 <= len(hosts) <= 20 or any(not isinstance(h, str) or not HOST.fullmatch(h) or '..' in h for h in hosts):
        raise ValueError('Strapi-bron vereist expliciete geldige artikelhosts')
    if urlsplit(row['url']).hostname not in hosts:
        raise ValueError('Bronpagina valt buiten de toegestane artikelhosts')
    coverage = row.get('coverageCandidates', [])
    if not isinstance(coverage, list) or any(not isinstance(m, str) or m not in strapi_news.MUNICIPALITIES for m in coverage):
        raise ValueError('Strapi-bron heeft onbekende gemeenten')
    if row.get('municipality') and row['municipality'] not in strapi_news.MUNICIPALITIES:
        raise ValueError('Strapi-bron heeft onbekende gemeente')
    prefix = row.get('articlePathPrefix', '/')
    if not isinstance(prefix, str) or not prefix.startswith('/') or prefix.startswith('//') or len(prefix) > 500 or any(c in prefix for c in ('?', '#', '\\')):
        raise ValueError('Strapi-bron heeft ongeldig artikelpad')
    if type(row.get('maxLinks')) is not int or not 1 <= row['maxLinks'] <= 20:
        raise ValueError('Strapi-bron vereist een linklimiet tussen 1 en 20')
    return dict(row, id=row['sourceKey'], coverageCandidates=coverage, articlePathPrefix=prefix)


def import_record(source):
    """Migrate catalog facts, without turning manual archive leads into crawls."""
    host = urlsplit(source['url']).hostname
    hosts = list(dict.fromkeys([host]+source.get('articleHosts', [])))
    row = {key: source.get(key) for key in ('name', 'url', 'kind', 'feed', 'municipality')}
    row.update(sourceKey=source['id'], articleHosts=hosts,
               coverageCandidates=source.get('coverageCandidates', []),
               active=bool(source.get('feed')), reader='firecrawl',
               discovery='rss' if source.get('feed') else 'manual', articlePathPrefix='/', maxLinks=5)
    validate_source(row)
    return row


class SourceRegistryClient:
    def __init__(self, base, token, transport=None):
        self.base, self.token = base, token
        self.transport = transport or strapi_news.request_json

    @classmethod
    def from_environment(cls, environment, importing=False):
        key = 'PITO_NEWS_SOURCE_IMPORT_TOKEN' if importing else 'PITO_NEWS_SOURCE_TOKEN'
        return cls(*strapi_news._configuration(environment, key))

    def sources(self):
        payload = self.transport(self.base, '/api/pito-news/sources', self.token)
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list) or not isinstance(payload.get('meta'), dict):
            raise ValueError('Strapi-bronnenregister is ongeldig')
        rows, meta = payload['data'], payload['meta']
        if len(rows) > 5000 or meta.get('complete') is not True or meta.get('schemaVersion') != 1 or type(meta.get('total')) is not int or meta['total'] != len(rows) or 'pagination' in meta:
            raise ValueError('Strapi-bronnenregister is onvolledig')
        result = [validate_source(row) for row in rows]
        if len({row['id'] for row in result}) != len(result):
            raise ValueError('Strapi-bronnenregister bevat dubbele bronidentiteiten')
        return result

    def import_source(self, source):
        row = {k: v for k, v in validate_source(source).items() if k in SOURCE_FIELDS}
        result = self.transport(self.base, '/api/pito-news/sources/import', self.token, 'POST', {'data': row})
        data = result.get('data') if isinstance(result, dict) else None
        if not isinstance(data, dict) or data.get('sourceKey') != row['sourceKey'] or type(data.get('created')) is not bool:
            raise ValueError('Strapi-bronimport is niet bevestigd; dezelfde bron veilig opnieuw aanbieden')
        return data
