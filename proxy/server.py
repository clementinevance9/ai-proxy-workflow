import json,os
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.request import Request,urlopen
UPSTREAM=os.getenv('UPSTREAM_BASE_URL','https://argolink.io/v1').rstrip('/')
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  if self.path not in ('/responses','/chat/completions','/images/generations'):
   self.send_error(404);return
  n=int(self.headers.get('Content-Length','0'))
  if n>2_000_000:self.send_error(413);return
  raw=self.rfile.read(n); key=os.getenv('UPSTREAM_API_KEY')
  if not key:self.send_error(500,'UPSTREAM_API_KEY missing');return
  req=Request(UPSTREAM+self.path,data=raw,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'ai-proxy-workflow/1.0'})
  try:
   with urlopen(req,timeout=90) as r: out=r.read();code=r.status
  except Exception as exc:self.send_error(502,str(exc));return
  self.send_response(code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(out)
 def log_message(self,*args):return
if __name__=='__main__':HTTPServer((os.getenv('LISTEN_HOST','127.0.0.1'),int(os.getenv('LISTEN_PORT','8080'))),Handler).serve_forever()
