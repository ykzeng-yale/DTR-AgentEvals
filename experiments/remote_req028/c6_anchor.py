"""Unreaped session/group anchor. Only c6_process launches this internal helper.

The anchor remains alive after the payload exits, so its PID/PGID cannot be
reused while the guardian cleans descendants. Payloads never receive this
guardian's control pipe. No shell is used.
"""
import json,os,signal,subprocess,sys,time
from pathlib import Path
from c6_protocol import put

def main(spec,status):
    s=json.loads(Path(spec).read_text())
    # Catch TERM in the anchor only. exec resets this caught handler to the
    # default in the payload; SIG_IGN would incorrectly be inherited.
    signal.signal(signal.SIGTERM,lambda *_:None)
    stream=open(s['stdin_path'],'rb') if s.get('stdin_path') else subprocess.DEVNULL
    try:
        child=subprocess.Popen(s['argv'],cwd=s['cwd'],env=s['env'],stdin=stream,
                               stdout=sys.stdout,stderr=sys.stderr)
        code=child.wait()
        put(Path(status).parent,Path(status).name,{'returncode':code})
        while True:time.sleep(.1)
    finally:
        if hasattr(stream,'close'):stream.close()

if __name__=='__main__':main(sys.argv[1],sys.argv[2])
