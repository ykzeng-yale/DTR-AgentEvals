"""Inert loopback server; commands are fixed strings and are NEVER evaluated."""
import json,signal,sys,time
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from c6_protocol import ROOT,encode,rendered,initial
from c5_contract import native_expected

def main(root,port):
    signal.alarm(60);root=Path(root)
    template=(ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/chat_template.jinja').read_text()
    count=0
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.respond()
        def do_POST(self):self.respond()
        def respond(self):
            nonlocal count
            n=int(self.headers.get('Content-Length','0'))
            payload=json.loads(self.rfile.read(n)) if 0<n<=1024*1024 else None
            status=200
            if self.path=='/health':value={'status':'ok'}
            elif self.path=='/props':value={'chat_template':template}
            elif self.path=='/apply-template':value={'prompt':rendered(payload['messages'])}
            elif self.path=='/tokenize':value={'tokens':native_expected()['token_ids'] if payload['content']==rendered(initial()) else list(range(10))}
            elif self.path=='/v1/chat/completions':
                count+=1
                (root/('physical-%02d.json'%count)).write_bytes(encode(payload))
                if (root/'hang').exists():time.sleep(59);return
                mode=(root/'mode').read_text() if (root/'mode').exists() else 'normal'
                command='fixture-submit' if count==2 and mode!='cap' else 'fixture-action'
                content='```mswea_bash_command\n'+command+'\n```'
                if mode=='invalid':content='<think>'+content
                value={'choices':[{'message':{'role':'assistant','content':content},'finish_reason':'stop'}],
                       'usage':{'prompt_tokens':1530 if payload['messages']==initial() else 10,'completion_tokens':12}}
            else:status=404;value={}
            raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    server=HTTPServer(('127.0.0.1',port),Handler)
    try:server.serve_forever(.02)
    finally:server.server_close()

if __name__=='__main__':main(sys.argv[1],int(sys.argv[2]))
