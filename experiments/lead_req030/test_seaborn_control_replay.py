import unittest
from .seaborn_control_replay import bindings,replay,sha
class Replay(unittest.TestCase):
 def test_all_declarations_and_mutations(self):
  d,_=bindings();f=d['FAIL_TO_PASS'];p=d['PASS_TO_PASS']
  for mode in ('baseline','reference'):
   lines=[f'{"FAILED" if mode=="baseline" else "PASSED"} {x}' for x in f]+[f'PASSED {x}' for x in p]
   raw=('>>>>> Start Test Output\n'+'\n'.join(lines)+'\n>>>>> End Test Output\n').encode()
   rec={'raw_sha256':sha(raw),'raw_bytes':len(raw),'supervisor':{'reason':'exited','returncode':1 if mode=='baseline' else 0}}
   self.assertTrue(replay(raw,rec,mode)['accepted'])
   for i in range(len(lines)):
    mutated=lines[:i]+lines[i+1:];b=('>>>>> Start Test Output\n'+'\n'.join(mutated)+'\n>>>>> End Test Output\n').encode();rec['raw_sha256']=sha(b);rec['raw_bytes']=len(b)
    self.assertFalse(replay(b,rec,mode)['accepted'])
if __name__=='__main__':unittest.main()
