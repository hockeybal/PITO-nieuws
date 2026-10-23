"""Explicit secret-file loading, without executing shell expressions."""
import os
from pathlib import Path
import re
import shlex
import stat


def load_env_file(path):
    if path is None:
        return
    file = Path(path)
    mode = file.stat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise ValueError('Instellingenbestand moet privé zijn: chmod 600')
    values = {}
    for line in file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not re.fullmatch(r'(?:PITO_[A-Z0-9_]+|FIRECRAWL_API_KEY|OPENAI_API_KEY|XAI_API_KEY)', key) or key in values:
            raise ValueError('Ongeldige of dubbele instelling in privébestand')
        parts = shlex.split(value, comments=True)
        if len(parts) > 1:
            raise ValueError('Instellingswaarde met spaties moet tussen aanhalingstekens staan')
        values[key] = parts[0] if parts else ''
    os.environ.update(values)
