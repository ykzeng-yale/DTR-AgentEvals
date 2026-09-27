import unittest
from matplotlib_eval_inputs import bindings,replay
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.d,cls.ns=bindings();cls.ids=cls.d['FAIL_TO_PASS']+cls.d['PASS_TO_PASS']
 def raw(self,changes={}):
  return (self.ns['START_TEST_OUTPUT']+'\n'+'\n'.join(changes.get(t,'PASSED')+' '+t for t in self.ids if changes.get(t)!='MISSING')+'\n'+self.ns['END_TEST_OUTPUT']).encode()
 def test_controls_and_provenance(self):
  kw=dict(cleanup_confirmed=True,provenance_verified=True)
  self.assertTrue(replay(self.raw(),0,'reference',**kw)['control_accepted'])
  self.assertTrue(replay(self.raw({self.ids[0]:'FAILED'}),1,'baseline',**kw)['control_accepted'])
  self.assertFalse(replay(self.raw(),0,'reference')['control_accepted'])
  self.assertFalse(replay(self.raw(),1,'reference',**kw)['control_accepted'])
  self.assertFalse(replay(self.raw()+self.ns['START_TEST_OUTPUT'].encode(),0,'reference',**kw)['control_accepted'])
 def test_each_declared_status_strictness(self):
  # Invoke the exact pinned rule for every required test; parser roundtrip separately.
  allpass=dict.fromkeys(self.ids,'PASSED');rule=self.ns['declared_outcome']
  for t in self.ids:
   for status in ('FAILED','ERROR','SKIPPED','XFAIL','MISSING'):
    mutated=dict(allpass)
    if status=='MISSING':del mutated[t]
    else:mutated[t]=status
    self.assertEqual(rule(self.d['FAIL_TO_PASS'],self.d['PASS_TO_PASS'],mutated,True),'unresolved')
  for status in ('FAILED','ERROR','SKIPPED','XFAIL'):
   parsed=self.ns['parse_log_matplotlib'](self.raw({self.ids[0]:status}).decode(),None)
   self.assertEqual(parsed[self.ids[0]],status)
if __name__=='__main__':unittest.main()
