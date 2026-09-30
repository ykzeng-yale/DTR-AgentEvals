"""Finite supervisor; owner pipe EOF cancels a separately owned process group."""
import argparse,json,os,re,selectors,signal,subprocess,time

MAX_SECONDS = 3600
MAX_OUTPUT_BYTES = 4 * 1024 * 1024

def run(fd,command,out,receipt,seconds,cap):
    sel=selectors.DefaultSelector();sel.register(fd,selectors.EVENT_READ,'owner')
    p=None;reason='internal_error';count=0;started=time.monotonic();error=None
    try:
        if sel.select(0):
            reason='owner_absent_before_start';return
        p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
        os.set_blocking(p.stdout.fileno(),False);sel.register(p.stdout,selectors.EVENT_READ,'output')
        out_fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(out_fd,'wb') as f:
            while True:
                if time.monotonic()-started>=seconds:reason='deadline';break
                if p.poll() is not None and not any(k.data=='output' for k in sel.get_map().values()):
                    reason='exited';break
                for key,_ in sel.select(.05):
                    if key.data=='owner':
                        if os.read(fd,4096)==b'':reason='owner_eof';break
                    else:
                        b=os.read(p.stdout.fileno(),65536)
                        if not b:sel.unregister(p.stdout)
                        if b:
                            remain=cap-count;f.write(b[:remain]);f.flush();count+=min(len(b),remain)
                            if len(b)>remain:reason='output_limit';break
                if reason in ('owner_eof','output_limit'):break
    except Exception as exc:
        message=re.sub(r"(?<![A-Za-z0-9])/(?:[^\s\"']+)","<private-path>",str(exc))
        error={'type':type(exc).__name__,'message':message[:1000],
               'errno':getattr(exc,'errno',None),'strerror':getattr(exc,'strerror',None)}
        raise
    finally:
        if p is not None:
            # Clean same-group descendants even if direct child has already exited.
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:p.wait(timeout=2)
            except subprocess.TimeoutExpired:pass
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            p.wait(timeout=2)
        sel.close()
        receipt_data=dict(reason=reason,pid=p.pid if p else None,returncode=p.returncode if p else None,
                          retained_bytes=count,elapsed=time.monotonic()-started,error=error)
        receipt_fd=os.open(receipt,os.O_WRONLY|os.O_TRUNC|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(receipt_fd,'w') as f:f.write(json.dumps(receipt_data))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--owner-fd',type=int,required=True);a.add_argument('--out',required=True);a.add_argument('--receipt',required=True);a.add_argument('--seconds',type=float,required=True);a.add_argument('--cap',type=int,default=1048576);a.add_argument('command',nargs=argparse.REMAINDER);n=a.parse_args()
    cmd=n.command[1:] if n.command[:1]==['--'] else n.command
    assert 0<n.seconds<=MAX_SECONDS and 0<n.cap<=MAX_OUTPUT_BYTES and cmd
    run(n.owner_fd,cmd,n.out,n.receipt,n.seconds,n.cap)
