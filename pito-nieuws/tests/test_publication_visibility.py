"""Public renderers consume durable releases, never legacy preview flags."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import news
import publication
import strapi_news
from test_publication import fixture, NOW


class PublicationVisibilityTests(unittest.TestCase):
    def test_json_flags_cannot_publish_and_retraction_cannot_revive_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            bundle = fixture()
            store = publication.PublicationStore(data, now=lambda: NOW)
            draft = store.submit(bundle)
            store.review(draft['id'], actor='Test editor', decision='approve',
                         note='Lokale test: alle zes controles met het testdocument uitgevoerd.',
                         checks={k: True for k in ('facts', 'geography', 'dates', 'privacy', 'rights', 'wording')})
            store.publish(draft['id'], actor='Test editor')
            article = publication.read_published(data)[0]
            (data / 'articles.json').write_text(json.dumps([article]))
            with patch.object(news, 'DATA', data), patch.object(news.search_visibility, 'production', return_value=True), patch.object(news.search_visibility, 'published', return_value=True):
                # Local SQLite releases are now private history and cannot
                # publish to any public renderer without a CMS publication.
                self.assertEqual(news.articles(), [])
                store.retract(draft['id'], actor='Test editor', reason='Test intrekking')
                self.assertEqual(news.articles(), [])

    def test_own_publication_date_and_automated_author_are_distinct_from_source(self):
        article = dict(news.read('articles')[0], authorName='PITO Nieuws · automatisch samengesteld',
                       humanReviewed=False, authorship={'kind': 'automated'},
                       publicationStatus='published', webPublishedAt='2026-10-16T11:00:00Z',
                       sourcePublishedAt='2026-10-15')
        with patch('weather.get', return_value={'status': 'unavailable'}):
            html = news.detail(article)
        self.assertIn('Gepubliceerd 16-10-2026', html)
        self.assertIn('Bronpublicatie 15-10-2026', html)
        self.assertIn('automatisch samengesteld', html)
        self.assertNotIn('"@type": "Person", "name": "PITO Nieuws', html)


if __name__ == '__main__':
    unittest.main()
