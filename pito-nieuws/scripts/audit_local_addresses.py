"""Audit municipal service links; default dry-run, explicit --apply to merge.

Failed checks live in a separate report and never replace last verified details.
Run with --report PATH to save diagnostics during a dry-run. Applying also keeps
a backup and an audit report alongside the address data.
"""
import argparse
import concurrent.futures
import copy
import datetime
import fcntl
import json
import os
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
SERVICES = [('municipality', ['contact']), ('waste', ['afval']),
            ('report', ['melding openbare', 'melding doen', 'iets melden'])]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.href, self.text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href, self.text = dict(attrs).get('href'), []

    def handle_data(self, text):
        if self.href:
            self.text.append(text)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.links.append((self.href, ' '.join(' '.join(self.text).split())))
            self.href = None


def safe_url(url):
    if not isinstance(url, str) or any(ord(c) < 33 for c in url):
        return False
    try:
        parsed = urlparse(url)
        _ = parsed.port
        return parsed.scheme == 'https' and bool(parsed.hostname) and not (parsed.username or parsed.password)
    except ValueError:
        return False


def fetch(url):
    if not safe_url(url):
        return 1, ''
    try:
        p = subprocess.run(['curl', '--silent', '--show-error', '--location', '--fail',
                            '--proto', '=https', '--proto-redir', '=https', '--max-redirs', '5',
                            '--max-time', '12', '--max-filesize', '2000000', url],
                           capture_output=True, timeout=15)
        return p.returncode, p.stdout.decode(errors='replace')
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''


def inspect(c):
    base = c['homepage']
    status, body = fetch(base)
    parser = Links()
    if status == 0:
        parser.feed(body)
    out = dict(municipality=c['municipality'], name=c['name'], homepage=base,
               checkedAt=datetime.date.today().isoformat(), homepageReachable=status == 0, services={})
    for key, words in SERVICES:
        candidates = [(urljoin(base, href), label) for href, label in parser.links
                      if any(word in (label + ' ' + href).lower() for word in words)]
        candidates = [(url, label) for url, label in candidates
                      if safe_url(url) and urlparse(url).hostname == urlparse(base).hostname]
        if candidates:
            url, label = min(candidates, key=lambda x: len(x[0]))
            code, content = fetch(url)
            out['services'][key] = dict(url=url, label=label, status='verified' if code == 0 else 'fetch_failed')
            if key == 'waste' and code == 0:
                links = Links()
                links.feed(content)
                out['services'][key]['calendarCandidates'] = [dict(url=urljoin(url, href), label=label)
                    for href, label in links.links
                    if safe_url(urljoin(url, href)) and any(word in (href + ' ' + label).lower()
                        for word in ['afvalkalender', 'afvalwijzer', 'ophaaldagen', 'mijnafval', 'afval-app'])][:8]
        else:
            out['services'][key] = dict(status='not_found' if status == 0 else 'fetch_failed')
    override_path = ROOT/'data/local-address-overrides.json'
    overrides = json.loads(override_path.read_text()).get(c['municipality'], {}) if override_path.exists() else {}
    for key, url in overrides.items():
        code, _ = fetch(url)
        out['services'][key] = dict(url=url, label=key, status='verified' if code == 0 else 'fetch_failed')
    return out


def merge_records(previous, audited):
    """Merge successful checks only, retaining verified and hand-maintained data."""
    rows = copy.deepcopy(previous)
    index = {row['municipality']: row for row in rows}
    for observation in audited:
        slug = observation['municipality']
        if slug not in index:
            row = copy.deepcopy(observation)
            rows.append(row)
            index[slug] = row
            continue
        row = index[slug]
        if observation.get('homepageReachable') is True:
            for key in ('name', 'homepage', 'checkedAt', 'homepageReachable'):
                if key in observation:
                    row[key] = observation[key]
        services = row.setdefault('services', {})
        for key, result in observation.get('services', {}).items():
            if result.get('status') != 'verified' or not safe_url(result.get('url')):
                continue
            target = services.setdefault(key, {})
            for field, value in result.items():
                if value not in (None, '', [], {}):
                    target[field] = copy.deepcopy(value)
            target['checkedAt'] = observation.get('checkedAt')
    return rows


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def apply_verified(data_path, observations):
    # Audits can take minutes. Merge against the latest data under a shared
    # writer lock so a second audit cannot restore an older snapshot.
    with data_path.with_suffix('.json.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current = json.loads(data_path.read_text()) if data_path.exists() else []
        merged = merge_records(current, observations)
        if data_path.exists():
            atomic_json(data_path.with_suffix('.json.bak'), current)
        atomic_json(data_path, merged)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Merge verified results into the address data')
    parser.add_argument('--report', type=Path, help='Separate JSON diagnostics file (dry-run otherwise writes no files)')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8:
        parser.error('--workers must be between 1 and 8')
    data_path = ROOT/'data/local-addresses.json'
    report_path = args.report or (ROOT/'data/local-address-audit-report.json' if args.apply else None)
    protected = {data_path, data_path.with_suffix('.json.bak'), data_path.with_suffix('.json.lock'),
                 ROOT/'data/municipal-source-discovery.json', ROOT/'data/local-address-overrides.json'}
    if report_path and report_path.resolve() in {path.resolve() for path in protected}:
        parser.error('The diagnostics report must not replace source or address data')
    sources = json.loads((ROOT/'data/municipal-source-discovery.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        observations = list(pool.map(inspect, sources))
    report = dict(runAt=datetime.datetime.now(datetime.timezone.utc).isoformat(), applied=False,
                  municipalities=len(observations), observations=observations)
    if report_path:
        atomic_json(report_path, report)
    if args.apply:
        apply_verified(data_path, observations)
        report['applied'] = True
        atomic_json(report_path, report)
    for row in observations:
        print(row['name'], [(key, value['status']) for key, value in row['services'].items()])
    print('Verified changes applied; previous data backed up.' if args.apply else 'Dry run: address data unchanged. Use --apply to merge verified results.')
    if not report_path:
        print('Use --report PATH to save the complete diagnostic results separately.')
    return 1 if any(not row.get('homepageReachable') or any(service.get('status') == 'fetch_failed'
                    for service in row['services'].values()) for row in observations) else 0


if __name__ == '__main__':
    raise SystemExit(main())
