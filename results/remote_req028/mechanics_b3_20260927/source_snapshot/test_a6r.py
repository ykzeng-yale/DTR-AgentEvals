import unittest
from a6r_gate import admit,setup_then_run
from mechanics_a6r import build_command
from mechanics_a6 import build_command as previous
class A6RTests(unittest.TestCase):
    def simulate(self,values,cross_final=False,popen_fail=False):
        clock=[0];reads=[];launches=[];it=iter(values)
        def sample():
            free=next(it,74)
            if cross_final and len(reads)==2:clock[0]=901
            return {'free_percent':free,'pressure_level':1,'foreign_inference':[],'disk_free_bytes':20*1024**3}
        def launch(s):
            launches.append(clock[0])
            if popen_fail:raise OSError('fake Popen failure')
            return 'child'
        try:
            result=admit(sample,lambda:clock[0],lambda x:clock.__setitem__(0,clock[0]+x),lambda *x:reads.append(x),launch,900)
        except (TimeoutError,OSError) as e:result=e
        return result,reads,launches,clock[0]
    def test_final_dip_resets_same_deadline(self):
        result,reads,launches,_=self.simulate([75,75,74,75,75,75])
        self.assertEqual(result,'child');self.assertEqual(launches,[180]);self.assertEqual(len(reads),6)
    def test_perpetual74_expires_no_popen(self):
        result,reads,launches,t=self.simulate([74]*40)
        self.assertIsInstance(result,TimeoutError);self.assertEqual(launches,[]);self.assertEqual(t,900);self.assertLessEqual(len(reads),31)
    def test_deadline_crossing_final_never_launches(self):
        result,_,launches,_=self.simulate([75,75,75],cross_final=True)
        self.assertIsInstance(result,TimeoutError);self.assertEqual(launches,[])
    def test_success_once(self):
        result,_,launches,_=self.simulate([75]*40)
        self.assertEqual(result,'child');self.assertEqual(launches,[60])
    def test_popen_failure_never_retries(self):
        result,_,launches,_=self.simulate([75]*40,popen_fail=True)
        self.assertIsInstance(result,OSError);self.assertEqual(launches,[60])
    def test_setup_failure_never_calls_gate(self):
        calls=[]
        def setup():calls.append('setup');raise ValueError('setup failed')
        with self.assertRaises(ValueError):setup_then_run(setup,lambda _:calls.append('gate'))
        self.assertEqual(calls,['setup'])
    def test_configuration_unchanged(self):
        self.assertEqual(build_command('alias',123,'A6R'),previous('alias',123,'A6'))
if __name__=='__main__':unittest.main()
