"""Start two isolated local editions; never copy credentials or write live data.

python scripts/start_local_test.py             # create once, start both
python scripts/start_local_test.py --refresh   # stop, refresh code/data, start
python scripts/start_local_test.py --status
python scripts/start_local_test.py --stop
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'work' / 'local-test'
SITE = LOCAL / 'site'
STATE = LOCAL / 'processes.json'


def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def owned_process(pid):
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='],
                            capture_output=True, text=True)
    return result.returncode == 0 and str(SITE) in result.stdout


def stop():
    for record in state().values():
        pid = record['pid']
        if owned_process(pid):
            os.killpg(pid, signal.SIGTERM)
    for _ in range(50):
        if not any(owned_process(r['pid']) for r in state().values()):
            break
        time.sleep(.1)
    STATE.unlink(missing_ok=True)


def copy_site():
    if SITE.exists():
        if SITE.is_symlink():
            raise RuntimeError('De lokale testmap mag geen symlink zijn.')
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True, exist_ok=True)
    for path in ROOT.glob('*.py'):
        shutil.copy2(path, SITE / path.name)
    shutil.copytree(ROOT / 'scripts', SITE / 'scripts', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(ROOT / 'data', SITE / 'data', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.lock', '*.tmp', '*.sqlite*', '*.db*'))
    # Use SQLite's backup protocol, never copy a database during a transaction.
    for source in (ROOT / 'data').glob('*.sqlite*'):
        if source.suffix not in ('.sqlite', '.sqlite3'):
            continue
        with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as src:
            with sqlite3.connect(SITE / 'data' / source.name) as dst:
                src.backup(dst)
    for name in ('static', 'portable-assets'):
        target = SITE / name
        if not target.exists():
            target.symlink_to(ROOT / name, target_is_directory=True)


def status():
    result = {}
    for name, port in (('preview', 4200), ('production', 4201)):
        record = state().get(name, {})
        running = bool(record.get('pid') and owned_process(record['pid']))
        entry = dict(record, running=running, url=f'http://127.0.0.1:{port}/nieuws/utrecht')
        if running:
            try:
                with urlopen(entry['url'], timeout=15) as response:
                    entry['httpStatus'] = response.status
            except (OSError, URLError) as exc:
                entry['httpStatus'] = 'unavailable'
        result[name] = entry
    return result


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    if args.stop or args.refresh:
        stop()
    if args.stop:
        print('Lokale testservers gestopt.')
        return
    if args.status:
        print(json.dumps(status(), indent=2))
        return
    if args.refresh or not (SITE / 'server.py').exists():
        copy_site()
    records = state()
    python = ROOT / '.venv/bin/python'
    if not python.exists():
        parser.error('Installeer eerst requirements-runtime.txt en requirements-intake.txt in .venv.')
    for name, port in (('preview', 4200), ('production', 4201)):
        if records.get(name) and owned_process(records[name]['pid']):
            continue
        # Do not inherit a live app token, paid writer key, edition override or
        # production database path into this local test environment.
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('PITO_', 'OPENAI_', 'GUNICORN_'))}
        env.update(PITO_STANDALONE='1', PITO_SITE_MODE=name,
                   PITO_PUBLIC_URL='https://pitonieuws.nl' if name == 'production'
                   else f'http://127.0.0.1:{port}', PYTHONDONTWRITEBYTECODE='1',
                   PORT=str(port), PITO_WEATHER_CACHE=str(SITE / 'data/weather-cache.json'))
        if name == 'production':
            env['PITO_LOCAL_TEST'] = '1'
            command = [str(python), '-m', 'gunicorn', '--bind', f'127.0.0.1:{port}',
                       '--no-control-socket',
                       '--workers', '2', '--timeout', '45', '--chdir', str(SITE),
                       '--access-logfile', str(LOCAL / 'production-access.log'),
                       'production_app:create_app()']
        else:
            command = [str(python), '-B', str(SITE / 'server.py')]
        with (LOCAL / (name + '.log')).open('ab') as log:
            child = subprocess.Popen(command, cwd=SITE, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        records[name] = {'pid': child.pid, 'port': port}
        STATE.write_text(json.dumps(records, indent=2))
    time.sleep(1)
    result = status()
    print(json.dumps(result, indent=2))
    if any(not entry['running'] or entry.get('httpStatus') != 200 for entry in result.values()):
        sys.exit(1)


if __name__ == '__main__':
    main()
