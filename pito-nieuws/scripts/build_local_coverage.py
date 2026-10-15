import json,html,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import os;os.chdir(ROOT)
import media_library
bank=media_library.load()
cities=json.load(open('data/municipalities.json'));sports=json.load(open('data/sports-sources.json'));report=[]
for city in cities:
 m=city['slug'];photos=[(k,v) for k,v in bank.items() if m in v.get('municipalities',[]) and v.get('kind') in ('photo','commons-photo') and media_library.eligible(v)];clubs=[c for c in sports if c['municipality']==m]
 report.append(dict(**city,eligibleTaggedPhotos=len({media_library.identity(v) for k,v in photos}),photoKeys=[k for k,v in photos],clubs=clubs,remaining=['Meer clubs inventariseren; deze startlijst is niet volledig','Club- en sportparkfoto’s met expliciete rechten verzamelen','Toewijzing op club, sport, locatie en datum; niet alleen onderwerp']))
Path('reports/municipal-photo-sport-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
e=html.escape
rows=''.join('<tr><td>'+e(r['name'])+'</td><td>'+str(r['eligibleTaggedPhotos'])+'</td><td>'+''.join('<p><a href="'+e(c['url'])+'">'+e(c['name'])+'</a> — '+e(c['feedStatus'])+'</p>' for c in r['clubs'])+'</td></tr>' for r in report)
Path('static/source-audit/local-sport-photos.html').write_text('<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Gemeentebeeldbank en clubs</title><style>body{font:16px/1.5 Arial;color:#2C2C2C;max-width:1100px;margin:40px auto;padding:0 20px}h1,a{color:#1050C2}table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #EDE8DF;padding:12px}p{margin:4px 0}</style><h1>Beeldbank en amateursport per gemeente</h1><p>Controle 14 oktober 2026. Startinventaris, geen volledige clubdekking. Feed bereikbaar betekent nog niet automatisch geïmporteerd. Clubfoto’s zijn niet automatisch vrij te gebruiken.</p><p>Beeldtelling: unieke toegelaten echte foto’s vanaf 2022 met expliciete gemeentetag. Algemene stock en nog niet geografisch getagde beelden tellen niet mee. Een geschikte kandidaat vereist ook inhoudelijke aansluiting.</p><table><tr><th>Gemeente</th><th>Lokale foto’s</th><th>Clubs en feedcontrole</th></tr>'+rows+'</table></html>')
