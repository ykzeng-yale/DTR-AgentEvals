"""Regression tests for telemetry FD lifetime and one-shot terminal reporting."""
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from recovery_transport import Transport
from recovery_contract import sha
ROOT=Path(__file__).resolve().parents[2]
class Tests(unittest.TestCase):
    def test_actual_low_fd_samples(self):
        code='''import resource,sys,time,json
from pathlib import Path
from c3r_hooks import ProcessHandle
from c3_adapter import PENDING
from recovery_supervisor import completed_sample
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
handles=[]
for i in range(320):
 h=ProcessHandle([sys.executable,'-c','import time;time.sleep(.02)'],3)
 handles.append(h)
 while completed_sample(h,handles) is PENDING:time.sleep(.005)
 assert not handles and h.error_file.closed and h.child.poll()==0
print(json.dumps({'completed':320,'live_handles':len(handles),'fd_limit':64}))
'''
        p=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True,timeout=120)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['completed'],320)
    def test_original_retention_exhausts_same_fd_limit(self):
        code='''import resource,sys,time
from c3r_hooks import ProcessHandle
from c3_adapter import PENDING
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
handles=[]
try:
 for i in range(100):
  h=ProcessHandle([sys.executable,'-c','import time;time.sleep(.02)'],3);handles.append(h)
  while h.poll() is PENDING:time.sleep(.005)
except OSError as e:
 assert e.errno==24;print('reproduced EMFILE')
else:raise AssertionError('not reproduced')
finally:
 for h in handles:h.close()
'''
        p=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True,timeout=45)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('EMFILE',p.stdout)
    def test_poisoned_transport_terminal_once_after_guard_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);box=p/'mail';box.mkdir();helper=ROOT/'experiments/remote_req029/recovery_mailbox.py'
            t=Transport(p/'network',str(box),str(helper),sha(helper.read_bytes()),'worker',time.time()+30,fixture=True,python=sys.executable,interval=.01)
            def fail():raise RuntimeError('latched guard')
            t.runner.check=fail
            with self.assertRaises(RuntimeError):t.read('request',1)
            self.assertTrue(t.failed)
            t.runner.check=lambda:None
            terminal={'cleanup':{'owned_absent':True},'status':'terminal_or_failure'}
            t.publish('worker_terminal',terminal)
            self.assertEqual(json.loads((box/'worker_terminal.json').read_text()),terminal)
            with self.assertRaises(Exception):t.publish('response',{},1)
            with self.assertRaises(Exception):t.publish('worker_terminal',terminal)
    def test_failed_terminal_is_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);helper=ROOT/'experiments/remote_req029/recovery_mailbox.py'
            t=Transport(p/'network',str(p/'missing'),str(helper),sha(helper.read_bytes()),'worker',time.time()+30,fixture=True,python=sys.executable,interval=.01)
            with self.assertRaises(Exception):t.publish('worker_terminal',{})
            (p/'missing').mkdir()
            with self.assertRaises(Exception):t.publish('worker_terminal',{})
            with self.assertRaises(Exception):t.read('request',1)
            self.assertEqual(list((p/'missing').iterdir()),[])
    def test_poll_exception_closes_handle(self):
        from recovery_supervisor import completed_sample
        class Handle:
            closed=False
            def poll(self):raise ValueError('bad sample')
            def close(self):self.closed=True
        h=Handle();handles=[h]
        with self.assertRaises(ValueError):completed_sample(h,handles)
        self.assertTrue(h.closed);self.assertEqual(handles,[])
if __name__=='__main__':unittest.main()
