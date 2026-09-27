"""Fixed inert executable. No alarm for idle child; strict HTTP bounded to60sec."""
import json,signal,sys,time
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from c2_relay import encode,sha
from c3_fakes import HTTP
def run(root,mode):
    root=Path(root);(root/'exec_seen.json').write_text(json.dumps({'executed':True}))
    if mode=='idle':
        while True:time.sleep(.1) # supervisor must clean; no child alarm fallback
    signal.alarm(60);expected=json.loads((root/'expected_body.json').read_text());calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.handle_request('GET')
        def do_POST(self):self.handle_request('POST')
        def handle_request(self,method):
            size=int(self.headers.get('Content-Length','0'));valid=0<=size<=1024*1024
            try:payload=json.loads(self.rfile.read(size)) if size and valid else None
            except Exception:payload='invalid';valid=False
            calls.append({'method':method,'path':self.path,'body':payload});(root/'server_calls.json').write_text(json.dumps(calls))
            obj={'error':'strict fixture rejected method/path/body'};status=400
            if method=='GET' and self.path=='/props' and payload is None:
                template=Path(__file__).resolve().parents[2]/'results/remote_req028/mechanics_c0_20260927/qwen/chat_template.jinja';obj={'chat_template':template.read_text()};status=200
            elif method=='POST' and self.path=='/apply-template' and valid and payload==expected:obj={'prompt':'C4_STRICT_FIXED_NATIVE'};status=200
            elif method=='POST' and self.path=='/tokenize' and payload=={'content':'C4_STRICT_FIXED_NATIVE','add_special':True,'parse_special':True,'with_pieces':False}:obj={'tokens':[1,2,3]};status=200
            elif method=='POST' and self.path=='/v1/chat/completions' and valid and payload==expected:
                (root/'request_seen.json').write_text('{}')
                if mode=='hang':time.sleep(59);return
                if mode=='error':obj={'error':'fixed backend failure'};status=503
                else:obj=json.loads(HTTP().begin_generate({},1).poll());status=200
            raw=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    server=HTTPServer(('127.0.0.1',0),Handler);(root/'ready.json').write_text(json.dumps({'host':'127.0.0.1','port':server.server_address[1]}))
    try:server.serve_forever(.05)
    finally:server.server_close()
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
