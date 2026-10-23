"""Check the configured shared agenda without writing or printing credentials."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app_content


def main():
    _, status = app_content.get()
    print(json.dumps(app_content.diagnostics(), ensure_ascii=False, indent=2))
    return 0 if status == 'connected' else 2 if status in ('not_configured', 'local_preview') else 1


if __name__ == '__main__':
    raise SystemExit(main())
