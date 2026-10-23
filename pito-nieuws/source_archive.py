"""Private, versioned source library and resumable crawl queue (never public news)."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import publication
from scripts.intake import canonical


class SourceArchive:
    def __init__(self, data_dir):
        folder = Path(data_dir)/'newsroom'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = folder/'source-archive.sqlite3'
        self.db = sqlite3.connect(self.path, timeout=15)
        os.chmod(self.path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS queue (
            url TEXT PRIMARY KEY, kind TEXT NOT NULL, metadata TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
            checked_at TEXT, retry_after TEXT, error TEXT, not_before TEXT
          );
          CREATE TABLE IF NOT EXISTS source_links (
            source_key TEXT NOT NULL, url TEXT NOT NULL REFERENCES queue(url),
            PRIMARY KEY(source_key,url)
          );
          CREATE TABLE IF NOT EXISTS revisions (
            revision TEXT PRIMARY KEY, url TEXT NOT NULL REFERENCES queue(url),
            document TEXT NOT NULL, collected_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS documents (
            url TEXT PRIMARY KEY REFERENCES queue(url), revision TEXT NOT NULL REFERENCES revisions(revision),
            published_at TEXT NOT NULL, title TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS source_runs (
            source_key TEXT PRIMARY KEY, checked_at TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS raw_pages (
            url TEXT PRIMARY KEY REFERENCES queue(url), html BLOB NOT NULL, sha256 TEXT NOT NULL,
            links TEXT, collected_at TEXT NOT NULL
          );
        ''')

    def __enter__(self): return self
    def __exit__(self, *args): self.db.close()

    def enqueue(self, row, source_key, seed=False, not_before=None):
        url = canonical(row['sourceUrl'])
        with self.db:
            created = self.db.execute('INSERT OR IGNORE INTO queue(url,kind,metadata,not_before) VALUES(?,?,?,?)',
                (url, 'seed' if seed else 'article', json.dumps(row, ensure_ascii=False), not_before)).rowcount
            self.db.execute('INSERT OR IGNORE INTO source_links(source_key,url) VALUES(?,?)', (source_key, url))
            if not seed:
                # Prefer a dated feed record over a seed with no publication date.
                self.db.execute("UPDATE queue SET metadata=?,kind='article' WHERE url=? AND kind='seed' AND status='pending'",
                                (json.dumps(row, ensure_ascii=False), url))
        return bool(created)

    def source_status(self, key, now, status, **detail):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO source_runs VALUES(?,?,?,?)',
                (key, publication.stamp(now), status, json.dumps(detail, ensure_ascii=False)))

    def pending(self, source_keys, now):
        rows = self.db.execute("""SELECT q.*,group_concat(s.source_key) AS source_keys FROM queue q
          JOIN source_links s ON s.url=q.url WHERE q.status IN ('pending','error')
          AND (q.retry_after IS NULL OR q.retry_after<=?) AND (q.not_before IS NULL OR q.not_before<=?)
          GROUP BY q.url ORDER BY q.kind='seed',q.url""", (publication.stamp(now), publication.stamp(now))).fetchall()
        result = []
        for row in rows:
            matching = sorted(set(row['source_keys'].split(',')) & set(source_keys))
            if matching:
                result.append(dict(row, source_keys=matching, metadata=json.loads(row['metadata'])))
        return sorted(result,key=lambda row:(row['kind']!='seed',row['metadata'].get('sourceTimestamp') or row['metadata'].get('sourcePublishedAt') or '',row['url']),reverse=True)

    def finish(self, url, now, status, error=None):
        retry = publication.stamp(now+dt.timedelta(hours=1)) if status == 'error' else None
        with self.db:
            self.db.execute('UPDATE queue SET status=?,attempts=attempts+1,checked_at=?,retry_after=?,error=? WHERE url=?',
                            (status, publication.stamp(now), retry, error, canonical(url)))

    def save(self, url, document, now):
        url = canonical(url)
        if publication.body_digest(document['body']) != document['sha256']:
            raise ValueError('Bronarchief: tekst en vingerafdruk komen niet overeen')
        published = publication._date(document['publishedAt'])
        if published > now+dt.timedelta(minutes=5):
            raise ValueError('Bronarchief: toekomstige publicatiedatum')
        data = json.dumps(document, ensure_ascii=False, sort_keys=True)
        revision = hashlib.sha256((url+'\n'+data).encode()).hexdigest()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO revisions VALUES(?,?,?,?)', (revision, url, data, publication.stamp(now)))
            self.db.execute('''INSERT INTO documents VALUES(?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
              revision=excluded.revision,published_at=excluded.published_at,title=excluded.title,last_seen_at=excluded.last_seen_at''',
              (url, revision, published.isoformat(), document['title'], publication.stamp(now), publication.stamp(now)))
            self.db.execute("UPDATE queue SET status='collected',attempts=attempts+1,checked_at=?,retry_after=NULL,error=NULL WHERE url=?",
                            (publication.stamp(now), url))
        return revision

    def save_raw(self,url,html,links,now):
        if not isinstance(html,bytes) or not html or len(html)>2_000_000:raise ValueError('Ongeldige ruwe bronpagina')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO raw_pages VALUES(?,?,?,?,?)',
                (canonical(url),html,hashlib.sha256(html).hexdigest(),json.dumps(links) if links is not None else None,publication.stamp(now)))

    def raw(self,url,now):
        row=self.db.execute('SELECT * FROM raw_pages WHERE url=? AND collected_at>=?',
            (canonical(url),publication.stamp(now-dt.timedelta(hours=24)))).fetchone()
        if row is None:return None
        raw=bytes(row['html'])
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Ruwe bronpagina is beschadigd')
        return {'rawHtml':raw,'links':json.loads(row['links']) if row['links'] is not None else []}

    def retry_parsing(self):
        """Retry only pages already downloaded, without spending credits again."""
        with self.db:
            return self.db.execute("UPDATE queue SET status='pending',retry_after=NULL WHERE status IN ('blocked','error') AND url IN (SELECT url FROM raw_pages)").rowcount

    def document(self, url, revision=None):
        url = canonical(url)
        row = self.db.execute('SELECT document FROM revisions WHERE url=? AND revision=?', (url, revision)).fetchone() if revision else self.db.execute(
            'SELECT r.document FROM documents d JOIN revisions r ON r.revision=d.revision WHERE d.url=?', (url,)).fetchone()
        if not row: return None
        document = json.loads(row['document'])
        if publication.body_digest(document['body']) != document['sha256']:
            raise ValueError('Bronarchief: opgeslagen bronbewijs is beschadigd')
        return document

    def candidates(self, source_keys, now):
        rows = self.db.execute('''SELECT d.*,group_concat(s.source_key) AS source_keys FROM documents d
          JOIN source_links s ON s.url=d.url WHERE d.published_at>=? AND d.published_at<=?
          GROUP BY d.url ORDER BY d.published_at DESC,d.url''',
          (publication.stamp(now-dt.timedelta(days=14)), publication.stamp(now+dt.timedelta(minutes=5)))).fetchall()
        result = []
        for row in rows:
            matching = sorted(set(row['source_keys'].split(',')) & set(source_keys))
            if matching:
                result.append({'sourceUrl': row['url'], 'sourceId': matching[0], 'sourceIds': matching,
                    'sourceTitle': row['title'], 'sourcePublishedAt': row['published_at'][:10],
                    'sourceTimestamp': row['published_at'], 'fingerprint': row['revision'], 'archiveRevision': row['revision']})
        return result

    def refresh(self, now):
        with self.db:
            return self.db.execute("UPDATE queue SET status='pending' WHERE status='collected' AND checked_at<? AND url IN (SELECT url FROM documents WHERE published_at>=?)",
                (publication.stamp(now-dt.timedelta(hours=24)), publication.stamp(now-dt.timedelta(days=14)))).rowcount

    def library(self, limit=200):
        if type(limit) is not int or not 1<=limit<=500:raise ValueError('Bibliotheeklimiet ongeldig')
        rows=self.db.execute('''SELECT d.*,group_concat(s.source_key) AS source_keys FROM documents d
          JOIN source_links s ON s.url=d.url GROUP BY d.url ORDER BY d.published_at DESC,d.url LIMIT ?''',(limit,)).fetchall()
        return [dict(row,source_keys=row['source_keys'].split(','),document=self.document(row['url'],row['revision'])) for row in rows]

    def summary(self):
        return {'queue': dict(self.db.execute('SELECT status,count(*) FROM queue GROUP BY status').fetchall()),
                'documents': self.db.execute('SELECT count(*) FROM documents').fetchone()[0],
                'revisions': self.db.execute('SELECT count(*) FROM revisions').fetchone()[0],
                'rawPages': self.db.execute('SELECT count(*) FROM raw_pages').fetchone()[0],
                'sources': [dict(row, detail=json.loads(row['detail'])) for row in self.db.execute('SELECT * FROM source_runs ORDER BY source_key')]}
