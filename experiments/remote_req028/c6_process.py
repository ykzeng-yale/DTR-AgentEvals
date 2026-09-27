"""Finite subprocess guardian. Bounded streamed output, private EOF cancellation.

Internal transport only: callers supply fixed Git/HTTP/qualified-adapter argv, never
model text as host argv. The sandbox adapter receives command text as JSON data.
"""
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from c6_protocol import put, require

def supervise(spec, out):
    s = json.loads(Path(spec).read_text())
    child = None
    output = bytearray()
    error = None
    started = time.time()
    try:
        require(started < s['deadline'], 'process deadline before spawn')
        status=Path(out).with_name(Path(out).name+'.payload')
        child = subprocess.Popen([sys.executable,str(Path(__file__).with_name('c6_anchor.py')),spec,str(status)], env=s['env'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True)
        os.set_blocking(child.stdout.fileno(), False)
        put(Path(out).parent, Path(out).name+'.owner', {'pid':child.pid,'started':started})
        while True:
            require(time.time() < s['deadline'], 'process deadline')
            ready = select.select([sys.stdin, child.stdout], [], [], .02)[0]
            if sys.stdin in ready:
                require(os.read(sys.stdin.fileno(), 1) != b'', 'driver EOF')
            if child.stdout in ready:
                chunk = os.read(child.stdout.fileno(), 65536)
                if chunk:
                    require(len(output)+len(chunk) <= s['output_cap'], 'streamed output cap')
                    output.extend(chunk)
            if status.exists():
                # Drain currently available data, then stop ALL owned descendants,
                # including background children holding the pipe open.
                while True:
                    try:chunk=os.read(child.stdout.fileno(),65536)
                    except BlockingIOError:break
                    if not chunk:break
                    require(len(output)+len(chunk)<=s['output_cap'],'streamed output cap')
                    output.extend(chunk)
                break
    except BaseException as e:
        error = repr(e)
    finally:
        if child is not None:
            # NEVER poll/wait/reap the anchor before whole-group cleanup. Even if
            # it dies early, its unreaped PID cannot be reused for a foreign group.
            signal_errors=[]
            try:os.killpg(child.pid,signal.SIGTERM)
            except OSError as e:signal_errors.append(repr(e))
            time.sleep(.03)
            try:os.killpg(child.pid,signal.SIGKILL)
            except OSError as e:signal_errors.append(repr(e))
            until=time.monotonic()+2
            group=[]
            group_absent=False
            try:
                while time.monotonic()<until:
                    rows=subprocess.check_output(['ps','-axo','pid=,pgid=,stat='],text=True,timeout=1).splitlines()
                    group=[row for row in rows if len(row.split())>=3 and int(row.split()[1])==child.pid and not row.split()[2].startswith('Z')]
                    if not group:group_absent=True;break
                    time.sleep(.01)
            except BaseException as e:error=error or 'cleanup observation failed: '+repr(e)
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:error=error or 'anchor reaping unconfirmed'
            if not group_absent:error=error or 'owned live group remains: '+repr(signal_errors)
            child.stdout.close()
        receipt = dict(started=started, finished=time.time(), error=error,
            returncode=json.loads(status.read_text())['returncode'] if child is not None and status.exists() else None,
            output=output.decode('utf-8', errors='replace'), bytes_retained=len(output),
            output_cap=s['output_cap'], child_reaped=child is None or child.returncode is not None,
            owned_group_absent=child is None or group_absent)
        receipt['signal_errors']=[] if child is None else signal_errors
        # Runtime receipt may encode up to 1MiB captured text with JSON escaping.
        # It is not a wire envelope; retain the overflow error after cleanup.
        put(Path(out).parent, Path(out).name, json.dumps(receipt).encode())

class Runner:
    def __init__(self, root, check=lambda:None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.count = 0
        self.events = []
        self.check = check

    def run(self, argv, deadline, cwd=None, env=None, cap=1024*1024, accept_nonzero=False,stdin_path=None,clean_env=False):
        self.check()
        require(time.time()<deadline, 'operation deadline')
        self.count += 1
        spec = self.root / (str(self.count)+'.spec.json')
        out = self.root / (str(self.count)+'.result.json')
        # Do not persist the environment: it may contain credentials.
        s = dict(argv=argv,cwd=None if cwd is None else str(cwd),env=None,
                 deadline=deadline,output_cap=cap,stdin_path=None if stdin_path is None else str(stdin_path))
        put(self.root, spec.name, s)
        child_env = dict(env or {}) if clean_env else dict(os.environ, **(env or {}))
        with (self.root/(str(self.count)+'.guardian.stderr')).open('xb') as err:
            guardian = subprocess.Popen([sys.executable,__file__,'guard',str(spec),str(out)],
                stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err,env=child_env,start_new_session=True)
        try:
            while guardian.poll() is None:
                self.check()
                require(time.time()<deadline+.5, 'guardian cancellation deadline')
                time.sleep(.01)
        finally:
            guardian.stdin.close()
            # EOF remains independently actionable if the driver is SIGKILLed.
            try:
                guardian.wait(timeout=3)
            except subprocess.TimeoutExpired:
                raise RuntimeError('guardian cleanup unconfirmed; no replay')
        require(out.stat().st_size<=6*cap+8192,'bounded process receipt')
        r = json.loads(out.read_text())
        self.events.append({k:v for k,v in r.items() if k!='output'})
        require(r['error'] is None, r['error'] or 'process failure')
        require(r['owned_group_absent'],'owned process group cleanup unconfirmed')
        require(accept_nonzero or r['returncode']==0, 'process exit '+str(r['returncode']))
        return r

if __name__ == '__main__':
    require(sys.argv[1]=='guard', 'internal guardian mode')
    supervise(sys.argv[2], sys.argv[3])
