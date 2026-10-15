"""Branded subject artwork for stories without an eligible photograph; never repeats headlines."""
import json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COLORS={'Bestuur':'#1050C2','Veiligheid':'#3F3F40','Verkeer':'#009CE5','Wonen':'#178A6E','Samenleving':'#6840BE'}
LABELS={'Bestuur':'Politiek & bestuur','Veiligheid':'Veiligheid','Verkeer':'Verkeer & OV','Wonen':'Wonen & bouwen','Samenleving':'In de buurt'}
ICONS={
'Bestuur':'<path d="M350 210l130-75 130 75zM365 360h230M350 385h260M380 235v105m65-105v105m70-105v105m65-105v105"/>',
'Veiligheid':'<path d="M480 130l120 50v95c0 80-120 130-120 130s-120-50-120-130v-95zM430 270l35 35 70-80"/>',
'Verkeer':'<rect x="365" y="155" width="230" height="200" rx="32"/><path d="M365 265h230M385 355v35m190-35v35M400 195h160"/><circle cx="410" cy="310" r="8"/><circle cx="550" cy="310" r="8"/>',
'Wonen':'<path d="M330 255l150-125 150 125M365 225v160h230V225M450 385v-100h60v100"/>',
'Samenleving':'<circle cx="435" cy="210" r="43"/><circle cx="550" cy="225" r="35"/><path d="M350 370v-35c0-95 170-95 170 0v35M525 285c85-10 100 40 100 85"/>'}
def build():
 out=ROOT/'static/editorial-covers';out.mkdir(exist_ok=True)
 for a in json.loads((ROOT/'data/articles.json').read_text()):
  cat=a['category'];color=COLORS.get(cat,'#0072FF')
  svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540"><rect width="960" height="540" fill="{color}"/><circle cx="850" cy="70" r="270" fill="white" opacity=".045"/><circle cx="30" cy="510" r="250" fill="white" opacity=".045"/><g fill="none" stroke="white" stroke-width="10" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(cat,ICONS['Samenleving'])}</g><text x="480" y="465" text-anchor="middle" fill="white" font-family="Arial,sans-serif" font-size="26">{html.escape(LABELS.get(cat,cat))}</text><text x="870" y="510" fill="white" opacity=".7" font-family="Arial,sans-serif" font-size="22" font-weight="700">PITO</text></svg>'''
  (out/(a['slug']+'.svg')).write_text(svg)
 (out/'default.svg').write_text(svg.replace(html.escape(LABELS.get(cat,cat)),'Lokaal nieuws'))
 return len(list(out.glob('*.svg')))
if __name__=='__main__':print(build())
