"""Integration-test driver: real Strapi, controlled Firecrawl and writer outputs."""
import datetime as dt
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from firecrawl_client import FirecrawlClient
import publication
from archive_crawler import ArchiveCrawler
from newsroom_worker import NewsroomWorker
from source_registry import SourceRegistryClient, import_record
from test_newsroom_worker import html_fixture, writer_output


def main():
    session = json.loads(Path(sys.argv[1]).read_text())
    mode = sys.argv[2]
    environment = {'PITO_LOCAL_TEST': '1', 'PITO_STRAPI_URL': session['url'],
                   'PITO_NEWS_SOURCE_TOKEN': session['sourceToken'], 'PITO_NEWS_DRAFT_TOKEN': session['draftToken'],
                   'PITO_NEWS_SOURCE_IMPORT_TOKEN': session['sourceImportToken']}
    if mode == 'website':
        from urllib.parse import urlsplit, urlencode
        os.environ.update(environment, PITO_STANDALONE='1', PITO_SITE_MODE='production',
                          PITO_PUBLIC_URL='https://pitonieuws.nl', PITO_NEWS_READ_TOKEN=session['readToken'], PITO_APP_CONTENT_URL='')
        import weather
        weather.get=lambda:{'status':'unavailable'}
        import news, production_app
        app=production_app.create_app()
        articles=news.articles();assert len(articles)==1
        article=articles[0];slug=article['slug'];title=article['title']
        def page(target):
            url=urlsplit(target);result={}
            def start(status,headers):result.update(status=int(status.split()[0]))
            result['body']=b''.join(app({'REQUEST_METHOD':'GET','HTTP_HOST':'pitonieuws.nl','PATH_INFO':url.path,
                'RAW_URI':target,'QUERY_STRING':url.query,'REMOTE_ADDR':'127.0.0.1','wsgi.url_scheme':'https'},start)).decode()
            assert result['status']==200,(target,result['status'])
            return result['body']
        positive=['/nieuws/utrecht','/nieuws/utrecht/utrecht',news.seo.topic_path('utrecht','Samenleving'),
                  '/nieuws/utrecht?q=Boekenmarkt','/nieuws/utrecht/utrecht?periode=archive&sortering=latest&onderwerp=Samenleving',
                  '/nieuws/utrecht/utrecht?sortering=relevance','/nieuws/utrecht/artikel/'+slug,
                  '/nieuws/feed.xml','/nieuws/sitemap.xml']
        for route in positive:assert slug in page(route),route
        for route in ['/nieuws/utrecht/zeist','/nieuws/utrecht?q=Boekenmarkt&onderwerp=Verkeer','/nieuws/utrecht?q=zeker-geen-overeenkomst']:
            assert title not in page(route),route
        print(json.dumps({'actualWebsiteRenderers':True,'actualStrapi':True,'positiveFilterChecks':len(positive),'negativeFilterChecks':3}))
        return
    if mode == 'catalog':
        client = SourceRegistryClient.from_environment(environment, importing=True)
        records = json.loads((Path(__file__).resolve().parents[1]/'data/sources.json').read_text())
        converted = [import_record(row) for row in records]
        created = sum(client.import_source(row)['created'] for row in converted)
        again = sum(client.import_source(row)['created'] for row in converted)
        assert again == 0
        print(json.dumps({'records': len(records), 'created': created, 'createdOnRepeat': again}))
        return
    now = dt.datetime.now(dt.timezone.utc)
    published = session['sourcePublishedAt']
    months = ('januari februari maart april mei juni juli augustus september oktober november december').split()
    label = str(now.day)+' '+months[now.month-1]
    raw = html_fixture(published).decode().replace('20 oktober', label)
    calls = []
    def transport(token, body):
        calls.append(body)
        return {'success': True, 'data': {'rawHtml': raw, 'metadata': {'sourceURL': body['url'], 'statusCode': 200}}}
    firecrawl = FirecrawlClient('isolated-firecrawl-test-key', transport=transport, validate_url=lambda u: u)
    class Writer:
        model = 'isolated-writer-fixture'
        provider = 'xAI Grok controlled test fixture'
        def __call__(self, request):
            output = json.loads(json.dumps(writer_output(), ensure_ascii=False).replace('20 oktober', label))
            output['eventDate'] = now.date().isoformat()
            return output
    def fetch(url, **kwargs):
        if url.endswith('/robots.txt'):
            return b'User-agent: *\nAllow: /\n'
        if url.endswith('/test-feed'):
            return ('<rss><channel><item><title>AFZONDERLIJKE LOKALE TEST</title>'
                    '<link>https://www.utrecht.nl/nieuws/firecrawl-isolated-test</link>'
                    '<pubDate>'+published+'</pubDate></item></channel></rss>').encode()
        raise AssertionError('Only controlled source data may be read by this integration test')
    data_dir=Path(session['appDir'])/'pipeline-data'
    crawl=ArchiveCrawler(data_dir,environment=environment,fetcher=fetch,firecrawl=firecrawl).run()
    sources=SourceRegistryClient.from_environment(environment).sources()
    report=NewsroomWorker(data_dir,environment=dict(environment,PITO_DOCUMENT_SOURCE='archive'),
        sources=sources,writer=Writer(),fetcher=fetch).run()
    assert not report['draftSync']['errors'],report
    rows = publication.PublicationStore(data_dir).list()
    assert not publication.read_published(data_dir)
    print(json.dumps({'statuses': report['statuses'], 'draftSync': report['draftSync'],
                      'firecrawlRequests': firecrawl.requests, 'privateDrafts': len(rows),
                      'archivedDocuments':crawl['archive']['documents'],'writerFirecrawlRequests':report['firecrawlRequests'],
                      'publishedLocally': 0, 'realStrapi': True, 'firecrawlAndWriter': 'controlled fixtures'}))


if __name__ == '__main__': main()
