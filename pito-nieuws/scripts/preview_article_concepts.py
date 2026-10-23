"""Read-only, loopback preview of an explicit saved Strapi draft snapshot.

Drafts retain their real review/publication states. This separate process never
changes the public CMS adapter, approves content, or reads service credentials.
"""
import argparse
from copy import deepcopy
from html import escape
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path,
                        default=ROOT/'data/newsroom/artikelconcepten/strapi-preview.json')
    parser.add_argument('--port', type=int, default=4213)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Kies een lokale poort tussen 1024 en 65535.')
    snapshot = json.loads(args.snapshot.read_text())
    rows = snapshot['articles']
    if (snapshot.get('savedFrom') != 'local-strapi-database-readback' or not rows
            or any(a.get('publicationStatus') != 'draft'
                   or a.get('reviewStatus') != 'needs_review'
                   or a.get('humanReviewed') is not False for a in rows)):
        parser.error('Deze voorvertoning vereist een expliciete CMS-conceptsnapshot.')
    media_path = args.snapshot.parent/'preview-media.json'
    media = json.loads(media_path.read_text()) if media_path.exists() else {}
    for article in rows:
        selection = media.get('articles', {}).get(article['slug'], {})
        for field in ('imageKey', 'imageTopics', 'imageContextLabel', 'illustrationOnly'):
            if field in selection:
                article[field] = selection[field]
    # No service credentials or production configuration in this process.
    for key in tuple(os.environ):
        if key.startswith(('PITO_', 'FIRECRAWL_')) or key in ('XAI_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(key)
    os.environ.update(PITO_STANDALONE='1', PITO_SITE_MODE='local',
                      PITO_PUBLIC_URL='http://127.0.0.1:'+str(args.port))
    sys.path.insert(0, str(ROOT))
    import news
    import weather
    import app_content
    import server
    import media_library

    news.articles = lambda: deepcopy(rows)
    if media.get('images'):
        image_library = dict(media_library.load(), **media['images'])
        original_read = news.read
        news.read = lambda name: deepcopy(image_library) if name == 'images' else original_read(name)
        media_library.load = lambda: deepcopy(image_library)
    original_artwork = news.artwork

    def artwork(article, detail=False):
        markup = '' if article.get('illustrationOnly') else original_artwork(article, detail)
        if markup:
            return markup
        # A missing photo or a duplicate on the same page gets a clearly
        # labelled editorial illustration, never an unrelated photograph.
        cover = ROOT/'static/editorial-covers'/(article['slug']+'.svg')
        if not cover.is_file():
            return ''
        image = ('<img src="/news-static/editorial-covers/'+escape(article['slug'], quote=True)
                 +'.svg" alt="Illustratie bij '+escape(article['title'], quote=True)
                 +'" width="960" height="540" loading="lazy">')
        if not detail:
            image = '<a href="'+news.url(article)+'" tabindex="-1" aria-hidden="true">'+image+'</a>'
        return ('<figure class="news-visual editorial-cover">'+image
                +'<figcaption>Redactionele illustratie · PITO</figcaption></figure>')

    news.artwork = artwork
    weather.get = lambda: {'status': 'unavailable', 'station': 'De Bilt', 'source': 'KNMI'}
    app_content.get = lambda: ([], 'unavailable')
    original_layout = news.layout
    description = snapshot.get('description') or 'Geschreven op basis van de opgeslagen Firecrawl-bronteksten.'

    def layout(title, body, *positional, **keywords):
        notice = ('<aside class="notice" role="note" style="border:2px solid #1765a6;'
                  'padding:16px;margin:20px 0;background:#eff7ff;color:#153a57">'
                  '<strong>Conceptpreview · '+str(len(rows))+' artikelen uit lokaal Strapi</strong>'
                  '<br>'+escape(description)+' '
                  'Deze concepten zijn nog niet menselijk beoordeeld of gepubliceerd.</aside>')
        return original_layout(title, notice+body, *positional, **keywords)

    news.layout = layout

    class PreviewHandler(server.Handler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if (path.startswith(('/nieuws/redactie', '/nieuws/onderzoek', '/nieuws/beeldbibliotheek',
                                 '/api/', '/news-static/source-audit', '/news-static/local-audit'))
                    or path in ('/nieuws/feed.xml', '/nieuws/sitemap.xml', '/sitemap.xml')):
                return self.send('Niet beschikbaar in de conceptpreview.', status=404)
            return super().do_GET()

        def do_POST(self):
            return self.send('Deze conceptpreview is alleen-lezen.', status=405)

    print('Conceptpreview: http://127.0.0.1:'+str(args.port)
          +'/nieuws/utrecht/utrechtse-heuvelrug', flush=True)
    with ThreadingHTTPServer(('127.0.0.1', args.port), PreviewHandler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    main()
