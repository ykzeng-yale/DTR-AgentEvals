"""Fake clock tests; no sleeps, model loads or external resource changes."""
import unittest
from admission_window import bounded_window
from mechanics_admitted import build_command
from mechanics_followup import build_command as original
class AdmissionTests(unittest.TestCase):
    def simulate(self,values,window=1800):
        clock=[0];reads=[];launches=[];items=iter(values)
        def sample():
            good=next(items,False)
            return {'pressure_level':1,'free_percent':80 if good else 73,'foreign_inference':[],'disk_free_bytes':20*1024**3}
        def observe(s,r,n,k,d):reads.append((clock[0],r,k))
        result=bounded_window(sample,lambda:clock[0],lambda x:clock.__setitem__(0,clock[0]+x),observe,lambda:launches.append(clock[0]),window)
        return result,reads,launches
    def test_two_readings_sixty_seconds(self):
        result,reads,launches=self.simulate([True,True,True])
        self.assertEqual(launches,[60]);self.assertEqual(result,('DISPATCHED',3))
        self.assertEqual([x[0] for x in reads],[0,60,60])
    def test_reset_after_failure(self):
        _,_,launches=self.simulate([True,False,True,True,True])
        self.assertEqual(launches,[180])
    def test_expiry_without_launch(self):
        result,reads,launches=self.simulate([False]*40)
        self.assertEqual(result,('ADMISSION_WINDOW_EXPIRED',31));self.assertFalse(launches)
        self.assertEqual(reads[-1][0],1800)
    def test_final_recheck_failure(self):
        result,reads,launches=self.simulate([True,True,False,True,True,True])
        self.assertEqual(launches,[180]);self.assertEqual(reads[2][2],'final_recheck')
    def test_exactly_once(self):
        _,_,launches=self.simulate([True]*100)
        self.assertEqual(len(launches),1)
    def test_no_launch_at_expiry(self):
        result,_,launches=self.simulate([True,True,True],window=60)
        self.assertEqual(result[0],'ADMISSION_WINDOW_EXPIRED');self.assertFalse(launches)
    def test_unchanged_cli(self):
        self.assertEqual(build_command('token',123,'A2R'),original('token',123,'A2'))
        self.assertEqual(build_command('token',123,'A3R'),original('token',123,'A3'))
if __name__=='__main__':unittest.main()
