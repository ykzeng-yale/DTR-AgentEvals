"""Test-only loopback process <=60 seconds; scripted text, fake tokenizer, no model."""
import json,signal,sys,time
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from comparator_contract import encode,rendered,template

def main(root,port):
    signal.alarm(60);root=Path(root);r=json.loads((root/'fixture.release.json').read_bytes())
    mode=(root/'mode').read_text();arm=r['arm'];count=0
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_GET(self):self.respond()
        def do_POST(self):self.respond()
        def respond(self):
            nonlocal count
            n=int(self.headers.get('Content-Length','0'))
            payload=json.loads(self.rfile.read(n)) if 0<n<=1024**2 else None
            status=200
            if self.path=='/health':v={'status':'ok'}
            elif self.path=='/props':
                t=template(arm);t=t[:-1] if arm=='klear' else t
                if mode=='template':t+='substituted'
                v=dict(chat_template=t,total_slots=1,default_generation_settings={'n_ctx':32768})
            elif self.path=='/apply-template':v={'prompt':rendered(payload['messages'],arm)}
            elif self.path=='/tokenize':v={'tokens':list(range(31233 if mode=='context' else 10))}
            elif self.path=='/v1/chat/completions':
                count+=1;(root/('physical-%02d.json'%count)).write_bytes(encode(payload))
                if mode=='hang':time.sleep(59);return
                command='exit0' if mode=='cap' else ('exit1' if count==1 else 'fixture-submit')
                if mode=='nonzero':command='nonzero-submit' if count==1 else 'fixture-submit'
                if mode=='overflow':command='overflow'
                content='<think>complete original thinking prose\n'+chr(96)*3+'mswea_bash_command\n'+command+'\n'+chr(96)*3
                if mode=='invalid':content+='\n'+chr(96)*3+'mswea_bash_command\nsecond\n'+chr(96)*3
                v=dict(choices=[dict(message=dict(role='assistant',content=content),finish_reason='length' if mode=='length' else 'stop')],
                       usage=dict(prompt_tokens=10,completion_tokens=12,total_tokens=22))
            else:status=404;v={}
            raw=json.dumps(v).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    server=HTTPServer(('127.0.0.1',port),Handler)
    try:server.serve_forever(.02)
    finally:server.server_close()
if __name__=='__main__':main(sys.argv[1],int(sys.argv[2]))
