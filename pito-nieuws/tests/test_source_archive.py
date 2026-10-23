"""Real private archive, resume/version behavior, Grok contract and offline writing."""
from copy import deepcopy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import newsroom_worker as w
import publication
from archive_crawler import ArchiveCrawler
from source_archive import SourceArchive
from test_firecrawl_pipeline import source, registry
from test_newsroom_worker import Writer, html_fixture, writer_output
from test_publication import NOW
from firecrawl_client import FirecrawlClient


URL='https://www.utrecht.nl/nieuws/boekenmarkt'


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.data=Path(self.tmp.name)
        self.document=w.extract_article(html_fixture(),{'sourcePublishedAt':NOW.date().isoformat()},NOW)
        self.document['reader']='firecrawl'

    def seed(self, archive):
        archive.enqueue({'sourceUrl':URL,'sourceId':'utrecht'},'utrecht')
        return archive.save(URL,self.document,NOW)

    def test_body_revisions_are_immutable_and_identical_collection_is_deduplicated(self):
        with SourceArchive(self.data) as archive:
            first=self.seed(archive)
            self.assertEqual(first,archive.save(URL,self.document,NOW+dt.timedelta(minutes=1)))
            changed=deepcopy(self.document);changed['body']+=' Een nagekomen feit.';changed['sha256']=publication.body_digest(changed['body'])
            second=archive.save(URL,changed,NOW+dt.timedelta(minutes=2))
            self.assertNotEqual(first,second)
            self.assertEqual(self.document,archive.document(URL,first))
            self.assertEqual(changed,archive.document(URL))
            self.assertEqual(2,archive.summary()['revisions'])
            self.assertEqual(0o600,archive.path.stat().st_mode & 0o777)

    def test_old_documents_and_unselected_sources_never_become_writer_candidates(self):
        with SourceArchive(self.data) as archive:
            self.seed(archive)
            self.assertEqual([],archive.candidates({'not-utrecht'},NOW))
            self.assertEqual([],archive.candidates({'utrecht'},NOW+dt.timedelta(days=15)))
            self.assertEqual(1,len(archive.candidates({'utrecht'},NOW)))

    def test_resume_queue_and_daily_refresh_do_not_lose_documents(self):
        with SourceArchive(self.data) as archive:self.seed(archive)
        with SourceArchive(self.data) as archive:
            self.assertEqual([],archive.pending({'utrecht'},NOW))
            self.assertEqual(1,archive.refresh(NOW+dt.timedelta(days=1,minutes=1)))
            self.assertEqual(1,len(archive.pending({'utrecht'},NOW+dt.timedelta(days=1,minutes=1))))
            self.assertIsNotNone(archive.document(URL))

    def test_writing_from_archive_uses_no_source_or_firecrawl_requests(self):
        with SourceArchive(self.data) as archive:self.seed(archive)
        writer=Writer()
        def forbidden(*args,**kwargs):raise AssertionError('The writer must use saved source evidence')
        worker=w.NewsroomWorker(self.data,writer=writer,fetcher=forbidden,now=lambda:NOW,
            sources=[dict(source(),id='utrecht')],environment={'PITO_DOCUMENT_SOURCE':'archive','PITO_WRITER_PROVIDER':'xai'})
        report=worker.run(limit=1)
        self.assertEqual({'drafted':1},report['statuses'],report)
        self.assertEqual(0,report['firecrawlRequests'])
        self.assertEqual(1,len(writer.calls))
        self.assertEqual([],publication.read_published(self.data))
        self.assertEqual(self.document['body'],writer.calls[0]['source']['body'])

    def test_damaged_archive_cannot_enter_article(self):
        with SourceArchive(self.data) as archive:
            revision=self.seed(archive)
            corrupt=deepcopy(self.document);corrupt['body']+=' CORRUPT'
            archive.db.execute('UPDATE revisions SET document=? WHERE revision=?',(json.dumps(corrupt),revision));archive.db.commit()
            with self.assertRaises(ValueError):archive.document(URL)


class GrokTests(unittest.TestCase):
    def test_deferred_writer_is_disabled_even_with_credentials(self):
        self.assertIsNone(w.writer_from_environment({'PITO_WRITER_ENABLED':'0','PITO_WRITER_PROVIDER':'xai','XAI_API_KEY':'test','PITO_WRITER_MODEL':'grok-test'}))
    def test_xai_selection_uses_only_xai_key_and_fixed_host(self):
        self.assertIsNone(w.writer_from_environment({'PITO_WRITER_PROVIDER':'xai','OPENAI_API_KEY':'private-openai','PITO_WRITER_API_KEY':'also-openai','PITO_WRITER_MODEL':'grok-test'}))
        writer=w.writer_from_environment({'PITO_WRITER_PROVIDER':'xai','XAI_API_KEY':'private-xai','PITO_WRITER_MODEL':'grok-test'})
        self.assertEqual('api.x.ai',writer.host)
        self.assertEqual('xAI Grok Responses API',writer.provider)
        with self.assertRaises(w.WorkerError):w.writer_from_environment({'PITO_WRITER_PROVIDER':'wrong'})

    def test_grok_http_contract_requests_strict_schema_and_parses_result(self):
        class Response:
            status=200
            def read(self,limit):return json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(writer_output())}]}]}).encode()
        class Connection:
            sock=None
            def request(self,method,path,body,headers):self.body=json.loads(body);self.path=path;self.headers=headers
            def getresponse(self):return Response()
            def close(self):pass
        connection=Connection()
        with patch('newsroom_worker.http.client.HTTPSConnection',return_value=connection) as factory:
            result=w.GrokWriter('private-xai','grok-test')({'source':{'body':'source evidence'}})
        self.assertEqual('api.x.ai',factory.call_args.args[0])
        self.assertEqual('/v1/responses',connection.path)
        self.assertTrue(connection.body['text']['format']['strict'])
        self.assertFalse(connection.body['store'])
        self.assertEqual('draft',result['decision'])
        self.assertNotIn('private-xai',json.dumps(connection.body))


class CrawlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.data=Path(self.tmp.name);self.requests=[]
        def transport(token,body):
            self.requests.append(body)
            return {'success':True,'data':{'rawHtml':html_fixture().decode(),'links':[],
                'metadata':{'sourceURL':body['url'],'statusCode':200}}}
        self.client=FirecrawlClient('test-key',max_requests=1,transport=transport,validate_url=lambda u:u)
        self.fetches=[]

    def fetch(self,url,**kwargs):
        self.fetches.append(url)
        if url.endswith('/robots.txt'):return b'User-agent: *\nAllow: /\n'
        return ('<rss><channel><item><title>Boekenmarkt</title><link>'+URL+'</link><pubDate>2026-10-16T09:00:00+00:00</pubDate></item></channel></rss>').encode()

    def crawler(self,rows=None):
        return ArchiveCrawler(self.data,environment={},registry=registry(rows or [source()]),fetcher=self.fetch,
            firecrawl=self.client,now=lambda:NOW)

    def test_discover_all_is_free_and_collect_resumes_without_any_writer(self):
        report=self.crawler().run(collect=False)
        self.assertEqual(0,len(self.requests))
        self.assertEqual(1,report['remaining'])
        result=self.crawler().run(discover=False)
        self.assertEqual(1,result['archive']['documents'])
        self.assertEqual(1,result['firecrawlRequests'])
        self.assertEqual(0,result['writerRequests'])
        self.assertEqual('collected',result['status'])
        self.assertEqual([],publication.read_published(self.data))

    def test_manual_sources_are_only_queued_when_all_sources_is_explicit(self):
        rows=[source(active=False,discovery='manual',feed=None,url=URL)]
        report=self.crawler(rows).run(collect=False)
        self.assertEqual(0,report['sourcesSelected'])
        report=self.crawler(rows).run(collect=False,include_inactive=True)
        self.assertEqual(1,report['remaining'])
        report=self.crawler(rows).run(discover=False,include_inactive=True)
        self.assertEqual(1,report['archive']['documents'])
        self.assertEqual(['rawHtml','links'],self.requests[0]['formats'])

    def test_per_execution_provider_budget_leaves_remaining_work_resumable(self):
        with SourceArchive(self.data) as archive:
            archive.enqueue({'sourceUrl':URL,'sourceId':'utrecht'},'utrecht')
            archive.enqueue({'sourceUrl':URL+'-2','sourceId':'utrecht'},'utrecht')
        report=self.crawler().run(discover=False)
        self.assertEqual(1,report['firecrawlRequests'])
        self.assertEqual(1,report['remaining'])
        self.assertEqual('incomplete',report['status'])

    def test_downloaded_page_can_be_reparsed_without_another_paid_request(self):
        with SourceArchive(self.data) as archive:archive.enqueue({'sourceUrl':URL,'sourceId':'utrecht'},'utrecht')
        with patch('archive_crawler.extract_article',side_effect=w.WorkerError('Geen artikel')):
            report=self.crawler().run(discover=False)
        self.assertEqual(1,report['archive']['rawPages'])
        with SourceArchive(self.data) as archive:self.assertEqual(1,archive.retry_parsing())
        self.client=FirecrawlClient('test-key',max_requests=1,transport=lambda *a: (_ for _ in ()).throw(AssertionError('No paid request')),validate_url=lambda u:u)
        report=self.crawler().run(discover=False)
        self.assertEqual(0,report['firecrawlRequests'])
        self.assertEqual(1,report['archive']['documents'])

    def test_sidebar_articles_do_not_make_one_real_article_ambiguous(self):
        raw=html_fixture().decode().replace('<aside>','<aside><article>').replace('</aside>','</article></aside>')
        doc=w.extract_article(raw.encode(),{'sourcePublishedAt':NOW.date().isoformat()},NOW)
        self.assertNotIn('zijbalk',doc['body'])


if __name__=='__main__':unittest.main()
