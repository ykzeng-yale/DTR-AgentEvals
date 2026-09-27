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
        child = subprocess.Popen(s['argv'], cwd=s['cwd'], env=s['env'],
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
                elif child.poll() is not None:
                    break
            if child.poll() is not None and child.stdout not in ready:
                # Drain buffered pipe bytes before accepting process completion.
                continue
    except BaseException as e:
        error = repr(e)
    finally:
        if child is not None:
            # Child is still held by Popen. Kill its exact new group before reaping.
            # No caller-selected PID and no grep-based termination.
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                until = time.monotonic()+.2
                while child.poll() is None and time.monotonic()<until:
                    time.sleep(.01)
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
            child.stdout.close()
        receipt = dict(started=started, finished=time.time(), error=error,
            returncode=None if child is None else child.returncode,
            output=output.decode('utf-8', errors='replace'), bytes_retained=len(output),
            output_cap=s['output_cap'], child_reaped=child is None or child.returncode is not None)
        put(Path(out).parent, Path(out).name, receipt)

class Runner:
    def __init__(self, root, check=lambda:None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.count = 0
        self.events = []
        self.check = check

    def run(self, argv, deadline, cwd=None, env=None, cap=1024*1024, accept_nonzero=False):
        self.check()
        require(time.time()<deadline, 'operation deadline')
        self.count += 1
        spec = self.root / (str(self.count)+'.spec.json')
        out = self.root / (str(self.count)+'.result.json')
        # Do not persist the environment: it may contain credentials.
        s = dict(argv=argv,cwd=None if cwd is None else str(cwd),env=None,
                 deadline=deadline,output_cap=cap)
        put(self.root, spec.name, s)
        child_env = dict(os.environ, **(env or {}))
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
        r = json.loads(out.read_text())
        self.events.append({k:v for k,v in r.items() if k!='output'})
        require(r['error'] is None, r['error'] or 'process failure')
        require(accept_nonzero or r['returncode']==0, 'process exit '+str(r['returncode']))
        return r

if __name__ == '__main__':
    require(sys.argv[1]=='guard', 'internal guardian mode')
    supervise(sys.argv[2], sys.argv[3])
