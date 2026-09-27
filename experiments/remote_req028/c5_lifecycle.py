"""Same supervisor for exact production plan and separately explicit inert test plan."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
from http.client import HTTPConnection
from c2_relay import encode,require
from c3r_arbiter import identity
from c3r_hooks import alive
HERE=Path(__file__).parent
def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
class Lifecycle:
    def __init__(self,root,spec):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.spec=dict(spec,root=str(self.root),driver_pid=os.getpid(),driver_identity=identity(os.getpid()));self.proc=None;self.record=None;self.endpoint={'host':'127.0.0.1','port':spec['port']}
    def launch(self):
        require(self.proc is None,'one load only');(self.root/'supervisor.json').write_bytes(encode(self.spec))
        with (self.root/'supervisor.stderr').open('xb') as log:
            self.proc=subprocess.Popen([sys.executable,str(HERE/'c5_supervisor.py'),str(self.root/'supervisor.json')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,start_new_session=True)
        self.supervisor_record={'pid':self.proc.pid,'identity':identity(self.proc.pid),'command':[str(self.root/'supervisor.json')]}
    def check(self):
        require(self.proc is not None and self.proc.poll() is None,'supervisor stopped');require(time.time()<self.spec['phase_deadline'],'phase expired')
        if (self.root/'owner.json').exists():self.record=json.loads((self.root/'owner.json').read_text())
    def owned_alive(self):
        self.check();return self.record is not None and alive(self.record)
    def health(self):
        self.check();require(time.time()<self.spec['load_deadline'],'load expired')
        if not (self.root/'exec_transition.json').exists() or self.record is None:return False
        if not alive(self.record):return False
        result=subprocess.run(['lsof','-nP','-a','-p',str(self.record['pid']),'-iTCP:'+str(self.spec['port']),'-sTCP:LISTEN'],capture_output=True,text=True,timeout=min(1,self.spec['load_deadline']-time.time()))
        if result.returncode or '127.0.0.1:'+str(self.spec['port']) not in result.stdout:return False
        conn=HTTPConnection('127.0.0.1',self.spec['port'],timeout=min(1,self.spec['load_deadline']-time.time()))
        try:
            conn.request('GET','/health');response=conn.getresponse();raw=response.read(4097);require(len(raw)<=4096,'health size')
            with (self.root/'health.jsonl').open('a') as log:log.write(json.dumps({'time':time.time(),'method':'GET','status':response.status,'raw':raw.decode(errors='replace')})+'\n')
            if response.status==503:return False
            require(response.status==200 and json.loads(raw).get('status')=='ok','health response')
            (self.root/'health_ready.json').write_bytes(encode({'time':time.time(),'owned_listener_pid':self.record['pid']}));return True
        except (ConnectionRefusedError,ConnectionResetError):return False
        finally:conn.close()
    def stop(self):
        if self.proc is None:return {'owned_absent':True}
        if self.proc.stdin and not self.proc.stdin.closed:self.proc.stdin.close()
        self.proc.wait(timeout=15);receipt=json.loads((self.root/'supervisor_exit.json').read_text());require(receipt['cleanup']['owned_absent'],'cleanup unconfirmed')
        if self.record:self.assert_absent()
        return receipt
    def assert_absent(self):require(not alive(self.record),'owned child still alive')
