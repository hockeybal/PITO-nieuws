"""Exercise untrusted HTTP requests without changing the editorial database."""
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

import server


class HttpSecurityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
  cls.thread.start()
  cls.host=f'127.0.0.1:{cls.http.server_port}'

 @classmethod
 def tearDownClass(cls):
  cls.http.shutdown();cls.http.server_close();cls.thread.join()

 def request(self,path,body=None,headers=None,method='GET'):
  client=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
  try:
   client.request(method,path,body=body,headers=headers or {})
   response=client.getresponse()
   return response.status,dict(response.getheaders()),response.read()
  finally:client.close()

 def post_headers(self):
  return {'Origin':'http://'+self.host,'X-Pito-CSRF':server.TOKEN,'Content-Type':'application/json'}

 def test_browser_protections_and_preview_indexing(self):
  status,headers,_=self.request('/robots.txt')
  self.assertEqual(status,200)
  self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
  self.assertEqual(headers['X-Frame-Options'],'DENY')
  self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
  self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
  self.assertIn('noindex',headers['X-Robots-Tag'])

 def test_unauthorized_request_is_rejected_without_waiting_for_body(self):
  client=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=2)
  try:
   client.putrequest('POST','/api/news/review')
   client.putheader('Origin','https://untrusted.example')
   client.putheader('Content-Length','29999')
   client.endheaders() # No body: authorization must run first.
   response=client.getresponse()
   self.assertEqual(response.status,403)
   response.read()
  finally:client.close()

 def test_unknown_post_returns_response(self):
  status,_,_=self.request('/api/unknown',b'{}',method='POST')
  self.assertEqual(status,404)

 def test_json_array_and_invalid_text_types_are_rejected(self):
  for data in ([],{'reviewer':123},{'confirmed':'true','reviewStatus':'approved','title':'t','summary':'s','body':'b','reviewer':'r','reviewNote':'n'}):
   with self.subTest(data=data):
    status,_,body=self.request('/api/news/review',json.dumps(data),self.post_headers(),'POST')
    self.assertEqual(status,400)
    self.assertIn('error',json.loads(body))

 def test_content_type_and_size_are_bounded(self):
  headers=self.post_headers();headers['Content-Type']='text/plain'
  self.assertEqual(self.request('/api/news/review',b'{}',headers,'POST')[0],415)
  self.assertEqual(self.request('/api/news/review',b'x'*30000,self.post_headers(),'POST')[0],400)

 def test_private_files_and_path_traversal_are_not_served(self):
  for path in ('/data/community.json','/data/articles.json','/server.py','/news-static/%2e%2e/data/community.json','/news-static/%2e%2e/server.py'):
   with self.subTest(path=path):self.assertEqual(self.request(path)[0],404)

 def test_production_mode_closes_local_management(self):
  with patch.dict(os.environ,{'PITO_SITE_MODE':'production'}):
   for path in ('/nieuws/redactie','/nieuws/redactie/signalen','/nieuws/onderzoek','/api/news','/api/media-library','/news-static/source-audit/index.html'):
    with self.subTest(path=path):self.assertEqual(self.request(path)[0],404)
   self.assertEqual(self.request('/api/community/submit',b'{}',self.post_headers(),'POST')[0],403)

 def test_preview_executable_refuses_production_mode(self):
  result=subprocess.run([sys.executable,'-B',str(Path(server.__file__))],env=dict(os.environ,PITO_STANDALONE='1',PITO_SITE_MODE='production'),capture_output=True,text=True,timeout=5)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('alleen voor lokale preview',result.stderr)


if __name__=='__main__':unittest.main()
