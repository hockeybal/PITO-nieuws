"""Run after feed/article import to regenerate the editorial photo shopping list."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import news,media_coverage
report=media_coverage.audit(news.articles())
(ROOT/'reports/image-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('missing','missingTopics')},ensure_ascii=False))
