import unittest,threading,urllib.request
import server,news
class HandoffTests(unittest.TestCase):
 def test_share_identity(self):
  html=news.detail(news.articles()[0])
  for part in ['rel="apple-touch-icon"','pito-icon-180.png','rel="icon"','property="og:image"','property="og:site_name"']:self.assertIn(part,html)
 def test_portable_assets(self):
  http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
  try:
   for path in ['/nieuws/utrecht/woerden','/style.css','/news-static/pito-icon-180.png','/news-static/pito-icon-32.png','/preview-assets/c9440ef71f7605f9968e.webp','/build/assets/poppins-latin-400-normal-cpxAROuN.woff2']:
    with urllib.request.urlopen('http://127.0.0.1:'+str(http.server_port)+path) as r:self.assertEqual(r.status,200);self.assertTrue(r.read())
  finally:http.shutdown();http.server_close();t.join()
