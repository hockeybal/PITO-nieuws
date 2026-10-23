"""One-time catalog import. Existing Strapi source edits are preserved."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_registry import SourceRegistryClient, import_record
from runtime_config import load_env_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=Path(__file__).resolve().parents[1]/'data/sources.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    records = [import_record(row) for row in json.loads(args.file.read_text())]
    if len({row['sourceKey'] for row in records}) != len(records):
        raise ValueError('Dubbele broncodes in import')
    result = {'sources': len(records), 'activeFeeds': sum(row['active'] for row in records), 'applied': False}
    if args.apply:
        client = SourceRegistryClient.from_environment(os.environ, importing=True)
        created = sum(client.import_source(row)['created'] for row in records)
        result.update(applied=True, created=created, preserved=len(records)-created)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError):
        print('Bronimport niet voltooid; controleer configuratie. Een herhaling behoudt bestaande CMS-bronnen.', file=sys.stderr)
        sys.exit(1)
