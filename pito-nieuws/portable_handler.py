"""Portable news-only preview. No Laravel/CMS emulation or local user paths."""
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,unquote
import mimetypes
ROOT=Path(__file__).parent/'portable-assets'
class Handler(BaseHTTPRequestHandler):
 def send(self,data,typ='text/html; charset=utf-8',status=200):
  if isinstance(data,str):data=data.encode()
  self.send_response(status);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def file(self,base,rel):
  target=(Path(base)/rel).resolve()
  if Path(base).resolve() not in target.parents or not target.is_file():return self.send('Niet gevonden',status=404)
  return self.send(target.read_bytes(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
 def do_GET(self):
  u=urlsplit(self.path);p=unquote(u.path)
  if p=='/' and not u.query:return self.redirect('/nieuws/utrecht')
  if p in ('/','/organisaties','/ontdek'):return self.redirect('https://pito.app'+self.path)
  if p=='/style.css' or p.startswith(('/build/','/media/','/preview-assets/')):
   target=(ROOT/p.lstrip('/')).resolve()
   if ROOT.resolve() in target.parents and target.is_file():return self.send(target.read_bytes(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
  return self.send('Niet gevonden',status=404)
