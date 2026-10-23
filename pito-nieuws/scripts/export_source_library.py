"""Export a private searchable reading library; this never publishes source text."""
import argparse
from html import escape
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_archive import SourceArchive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[1]/'data')
    parser.add_argument('--limit',type=int,default=200)
    args=parser.parse_args()
    with SourceArchive(args.data_dir) as archive: rows,summary=archive.library(args.limit),archive.summary()
    registry=args.data_dir/'newsroom/source-registry.json'
    sources={s['id']:s for s in json.loads(registry.read_text())} if registry.exists() else {}
    names={key:s.get('name',key) for key,s in sources.items()}
    options=''.join('<option value="'+escape(key,quote=True)+'">'+escape(names.get(key,key))+'</option>' for key in sorted({key for row in rows for key in row['source_keys']}))
    cards=[]
    for row in rows:
        doc=row['document'];label=' · '.join(names.get(key,key) for key in row['source_keys'])
        cards.append('<article data-sources="'+escape('|'.join(row['source_keys']),quote=True)+'" data-date="'+row['published_at'][:10]+'"><p class="meta">'+escape(label)+' · '+row['published_at'][:10]+'</p><h2>'+escape(row['title'])+'</h2><p><a href="'+escape(row['url'],quote=True)+'" target="_blank" rel="noopener noreferrer">Originele bron openen ↗</a></p><details><summary>Lees opgeslagen brontekst</summary><pre>'+escape(doc['body'])+'</pre></details></article>')
    status=' · '.join(str(value)+' '+key for key,value in sorted(summary['queue'].items()))
    html='''<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PITO Bronnenbibliotheek</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f5f5f0;color:#202720;font:17px/1.6 system-ui,sans-serif}main{max-width:980px;margin:auto;padding:44px 24px}small{font-weight:800;letter-spacing:.14em;color:#476c49}h1{font-size:clamp(32px,6vw,54px);line-height:1.1;margin:14px 0}h2{font-size:24px;line-height:1.3;margin:8px 0}.intro{max-width:720px}.tools{display:flex;gap:14px;flex-wrap:wrap;margin:30px 0}.tools label{flex:1;min-width:170px}input,select{display:block;width:100%;padding:12px;border:1px solid #abb9ab;border-radius:6px;font:inherit;background:white}article{padding:26px;margin:20px 0;background:white;border:1px solid #dce3d9;border-radius:12px}.meta{font-size:14px;color:#527057;margin:0}a{color:#245d36}summary{cursor:pointer;font-weight:600}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;border-top:1px solid #dce3d9;padding-top:20px}[hidden]{display:none!important}.status{font-size:14px;color:#586458}</style>
<main><small>PITO · REDACTIE</small><h1>Bronnenbibliotheek</h1><p class="intro">Door Firecrawl opgehaalde bronberichten. Bekijk de inhoud en kies welke onderwerpen je tot een eigen PITO-artikel wilt verwerken. Grok kan later uit deze opgeslagen teksten schrijven.</p>'''
    html+='<p class="status">'+str(summary['documents'])+' opgeslagen documenten · '+escape(status)+'. Dit bestand toont maximaal '+str(args.limit)+' documenten.</p>'
    html+='<div class="tools"><label>Zoeken<input id="search" type="search" placeholder="Titel, onderwerp of tekst"></label><label>Bron<select id="source"><option value="">Alle opgehaalde bronnen</option>'+options+'</select></label><label>Vanaf datum<input id="date" type="date"></label></div><p id="count"></p>'+''.join(cards)
    html+='''</main><script>const cards=[...document.querySelectorAll('article')];function filter(){let count=0;const q=document.querySelector('#search').value.toLocaleLowerCase('nl'),s=document.querySelector('#source').value,d=document.querySelector('#date').value;for(const card of cards){card.hidden=!(card.textContent.toLocaleLowerCase('nl').includes(q)&&(!s||card.dataset.sources.split('|').includes(s))&&(!d||card.dataset.date>=d));if(!card.hidden)count++}document.querySelector('#count').textContent=count+' bronberichten zichtbaar'}document.querySelectorAll('input,select').forEach(el=>el.addEventListener('input',filter));filter();</script></html>'''
    path=args.data_dir/'newsroom/bronnenbibliotheek.html';path.write_text(html);path.chmod(0o600)
    print(json.dumps({'path':str(path.resolve()),'documents':summary['documents'],'shown':len(rows)},ensure_ascii=False))


if __name__=='__main__':main()
