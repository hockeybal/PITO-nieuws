#!/bin/zsh
# macOS: dubbelklik om de zelfstandige nieuws-preview te openen.
set -u
cd -- "${0:A:h}" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  print 'Python 3.9 of nieuwer ontbreekt. Installeer Python en open dit bestand opnieuw.'
  exit 1
fi

export PITO_STANDALONE=1
export PITO_SITE_MODE=preview

exec python3 -B - <<'PY'
import errno
import os
import shutil
import subprocess
import sys
import threading

if sys.version_info < (3, 9):
    print('Python 3.9 of nieuwer is nodig voor deze lokale preview.', flush=True)
    sys.exit(1)

try:
    port = int(os.environ.get('PORT', '4198'))
    if not 1 <= port <= 65535:
        raise ValueError
except ValueError:
    print('PORT moet een nummer tussen 1 en 65535 zijn.', flush=True)
    sys.exit(1)

import server

url = f'http://127.0.0.1:{port}/nieuws/utrecht'
try:
    http = server.ThreadingHTTPServer(('127.0.0.1', port), server.Handler)
except OSError as error:
    if error.errno == errno.EADDRINUSE:
        print(f'Poort {port} wordt al gebruikt.', flush=True)
        print(f'Draait PITO al? Open dan {url}', flush=True)
        print('Sluit de eerdere server met Ctrl+C, of kies een andere poort:', flush=True)
        print('  PORT=4200 ./start-local.command', flush=True)
    else:
        print(f'De lokale server kon niet starten: {error}', flush=True)
    sys.exit(1)

print(f'PITO Nieuws staat lokaal op {url}', flush=True)
print('Laat dit Terminal-venster open. Stoppen: Ctrl+C.', flush=True)

def open_preview():
    if sys.platform == 'darwin' and shutil.which('open'):
        subprocess.run(['open', url], check=False)

opener = threading.Timer(0.5, open_preview)
opener.daemon = True
opener.start()
try:
    http.serve_forever()
except KeyboardInterrupt:
    print('\nDe lokale PITO-server is gestopt.', flush=True)
finally:
    opener.cancel()
    http.server_close()
PY
