"""Human-authored fixed-JSON loopback fixture, no payload execution, max60sec."""
import json,signal,sys,time
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from c3_adapter import CONTRACT
def server(ready,mode):
    signal.alarm(60)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.do_POST()
        def do_POST(self):
            size=int(self.headers.get('Content-Length','0'))
            if size>1024*1024:self.send_error(413);return
            if size:self.rfile.read(size)
            if self.path=='/v1/chat/completions':Path(ready).with_name('request_seen.json').write_text(json.dumps({'received':True}))
            if mode=='hang' and self.path=='/v1/chat/completions':time.sleep(59);return
            from c3_fakes import HTTP
            if self.path=='/props':obj={'chat_template':(Path(__file__).resolve().parents[2]/'results/remote_req028/mechanics_c0_20260927/qwen/chat_template.jinja').read_text()}
            elif self.path=='/apply-template':obj={'prompt':'FIXED_JSON_FIXTURE'}
            elif self.path=='/tokenize':obj={'tokens':[1,2,3]}
            else:obj=json.loads(HTTP().begin_generate({'fixture':True},1).poll())
            raw=json.dumps(obj).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    http=HTTPServer(('127.0.0.1',0),Handler)
    Path(ready).write_text(json.dumps({'host':'127.0.0.1','port':http.server_address[1]}))
    try:http.serve_forever(poll_interval=.05)
    finally:http.server_close()
if __name__=='__main__':server(sys.argv[2],sys.argv[3])
