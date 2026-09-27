"""C7 bounded byte-preserving capture; C6 unreaped anchor/EOF cleanup pattern."""
import base64,json,os,select,signal,subprocess,sys,time
from pathlib import Path
from django_eval_contract import put,require,OLD
HERE=OLD

def supervise(spec,out):
    s=json.loads(Path(spec).read_bytes());child=None;data=bytearray();streams={'stdout':bytearray(),'stderr':bytearray()};error=None
    started=time.time();signal_errors=[];absent=False
    try:
        require(started<s['deadline'],'capture deadline before spawn')
        status=Path(out).with_name(Path(out).name+'.payload')
        child=subprocess.Popen([sys.executable,str(HERE/'c6_anchor.py'),spec,str(status)],
            env=s['env'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        os.set_blocking(child.stdout.fileno(),False);os.set_blocking(child.stderr.fileno(),False)
        put(Path(out).parent,Path(out).name+'.owner',dict(pid=child.pid,started=started))
        while True:
            require(time.time()<s['deadline'],'capture deadline')
            ready=select.select([sys.stdin,child.stdout,child.stderr],[],[],.02)[0]
            if sys.stdin in ready:require(os.read(sys.stdin.fileno(),1)!=b'','driver EOF')
            def drain(stream,name):
                while True:
                    try:block=os.read(stream.fileno(),65536)
                    except BlockingIOError:break
                    if not block:break
                    require(len(data)+len(block)<=s['output_cap'],'streamed output cap')
                    data.extend(block);streams[name].extend(block)
            for name in ('stdout','stderr'):
                stream=getattr(child,name)
                if stream in ready:drain(stream,name)
            if status.exists():
                for name in ('stdout','stderr'):drain(getattr(child,name),name)
                break
    except BaseException as e:error=repr(e)
    finally:
        if child is not None:
            # Do not poll/reap anchor until all owned group members are absent.
            for sig in (signal.SIGTERM,signal.SIGKILL):
                try:os.killpg(child.pid,sig)
                except OSError as e:signal_errors.append(repr(e))
                if sig==signal.SIGTERM:time.sleep(.03)
            try:
                end=time.monotonic()+2
                while time.monotonic()<end:
                    rows=subprocess.check_output(['ps','-axo','pid=,pgid=,stat='],text=True,timeout=1).splitlines()
                    group=[r for r in rows if len(r.split())>=3 and int(r.split()[1])==child.pid and not r.split()[2].startswith('Z')]
                    if not group:absent=True;break
                    time.sleep(.01)
            except BaseException as e:error=error or repr(e)
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:error=error or 'anchor reap unconfirmed'
            child.stdout.close();child.stderr.close()
            if not absent:error=error or 'owned group cleanup unconfirmed'
        value=dict(started=started,finished=time.time(),error=error,
            returncode=json.loads(status.read_bytes())['returncode'] if child is not None and status.exists() else None,
            raw_base64=base64.b64encode(data).decode(),
            stdout_base64=base64.b64encode(streams['stdout']).decode(),stderr_base64=base64.b64encode(streams['stderr']).decode(),
            stdout_bytes=len(streams['stdout']),stderr_bytes=len(streams['stderr']),bytes_retained=len(data),output_cap=s['output_cap'],
            child_reaped=child is None or child.returncode is not None,owned_group_absent=child is None or absent,
            signal_errors=signal_errors)
        put(Path(out).parent,Path(out).name,json.dumps(value).encode())

class Runner:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.count=0;self.check=lambda:None
    def run(self,argv,deadline,cwd=None,env=None,cap=1024**2,accept_nonzero=False,stdin_path=None,clean_env=False):
        self.check();require(time.time()<deadline,'capture operation deadline');self.count+=1
        spec=self.root/('%04d.spec.json'%self.count);out=self.root/('%04d.result.json'%self.count)
        value=dict(argv=argv,cwd=None if cwd is None else str(cwd),env=None,deadline=deadline,
            output_cap=cap,stdin_path=None if stdin_path is None else str(stdin_path))
        put(self.root,spec.name,value)
        child_env=dict(env or {}) if clean_env else dict(os.environ,**(env or {}))
        with (self.root/('%04d.stderr'%self.count)).open('xb') as err:
            proc=subprocess.Popen([sys.executable,__file__,str(spec),str(out)],env=child_env,
                stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err,start_new_session=True)
        try:
            while proc.poll() is None:
                self.check();require(time.time()<deadline+.5,'capture guardian deadline');time.sleep(.01)
        finally:
            proc.stdin.close()
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:raise RuntimeError('capture guardian cleanup unconfirmed')
        require(out.stat().st_size<=4*cap+8192,'bounded capture receipt')
        result=json.loads(out.read_bytes())
        require(result['error'] is None,result['error'] or 'capture error')
        require(result['owned_group_absent'] and result['child_reaped'],'capture cleanup unconfirmed')
        require(accept_nonzero or result['returncode']==0,'process exit '+str(result['returncode']))
        result['output']=base64.b64decode(result['raw_base64']).decode(errors='replace')
        return result

if __name__=='__main__':supervise(sys.argv[1],sys.argv[2])
