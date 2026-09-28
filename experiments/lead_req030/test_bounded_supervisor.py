import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
SUP=Path(__file__).with_name('bounded_supervisor.py').resolve()
class SupervisorTests(unittest.TestCase):
 def case(self,code,seconds,expected,disconnect=False):
  with tempfile.TemporaryDirectory() as d:
   r,w=os.pipe();p=subprocess.Popen([sys.executable,str(SUP),'--owner-fd',str(r),'--out',d+'/out','--receipt',d+'/receipt','--seconds',str(seconds),'--cap','4096','--',sys.executable,'-c',code],pass_fds=(r,));os.close(r)
   if disconnect:time.sleep(.2);os.close(w)
   try:p.wait(timeout=6)
   finally:
    if not disconnect:os.close(w)
    if p.poll() is None:p.kill();p.wait()
   x=json.loads(Path(d+'/receipt').read_text());self.assertEqual(x['reason'],expected);self.assertLessEqual(x['retained_bytes'],4096)
   if x['pid']:
    with self.assertRaises(ProcessLookupError):os.kill(x['pid'],0)
 def test_timeout(self):self.case('import time;time.sleep(10)',.2,'deadline')
 def test_overflow(self):self.case('import os,time;os.write(1,b"x"*100000);time.sleep(10)',2,'output_limit')
 def test_owner_death(self):self.case('import time;time.sleep(10)',3,'owner_eof',True)
 def test_normal(self):self.case('pass',2,'exited')
if __name__=='__main__':unittest.main()
