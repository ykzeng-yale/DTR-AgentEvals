"""Explicitly injected fake production executable, no exec_seen marker."""
import json,signal,sys,time
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from c5_contract import native_expected,ROOT,REQUEST_PATH
from c4_http import body
def main(root,port):
    signal.alarm(60);root=Path(root);expected=body(json.loads((ROOT/REQUEST_PATH).read_text())['messages']);binding=native_expected()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.respond('GET')
        def do_POST(self):self.respond('POST')
        def respond(self,method):
            n=int(self.headers.get('Content-Length','0'));payload=json.loads(self.rfile.read(n)) if 0<n<=1024*1024 else None;status=400;value={'error':'strict fake production API'}
            if method=='GET' and self.path=='/health':status=200;value={'status':'ok'}
            elif method=='GET' and self.path=='/props':status=200;value={'chat_template':(ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/chat_template.jinja').read_text()}
            elif method=='POST' and self.path=='/apply-template' and payload==expected:status=200;value={'prompt':binding['rendered']}
            elif method=='POST' and self.path=='/tokenize' and payload=={'content':binding['rendered'],'add_special':True,'parse_special':True,'with_pieces':False}:status=200;value={'tokens':binding['token_ids']}
            elif method=='POST' and self.path=='/v1/chat/completions' and payload==expected:
                with (root/'physical_calls.jsonl').open('a') as f:f.write('{"physical":1}\n')
                if (root/'hang').exists():time.sleep(59);return
                status=200;value={'choices':[{'message':{'role':'assistant','content':'fixed fixture, not model inference'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1530,'completion_tokens':7,'total_tokens':1537},'timings':{'prompt_ms':1,'predicted_ms':2}}
            raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    server=HTTPServer(('127.0.0.1',port),Handler)
    try:server.serve_forever(.05)
    finally:server.server_close()
if __name__=='__main__':main(sys.argv[1],int(sys.argv[2]))
