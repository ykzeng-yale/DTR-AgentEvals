import json, os, subprocess, sys, time, unittest
import guard

class GuardTests(unittest.TestCase):
    def test_deadline_and_guards(self):
        s={'pressure_level':1,'free_percent':82,'swap_used_mib':233,'owned_rss_bytes':1024,'foreign_inference':[],'disk_free_bytes':20*1024**3}
        self.assertIsNone(guard.violation(s,233,time.time()+10))
        self.assertEqual(guard.violation(s,233,time.time()-1),'deadline')
        self.assertEqual(guard.violation(s,233,time.time()+10,False),'owner_parent_exited')
        for field,value,expected in [('pressure_level',2,'adverse_pressure'),('free_percent',19,'free_metric_below_20'),('swap_used_mib',746,'swap_growth'),('owned_rss_bytes',12*1024**3,'owned_rss'),('foreign_inference',[1],'foreign_inference')]:
            self.assertEqual(guard.violation(dict(s,**{field:value}),233,time.time()+10),expected)
    def test_owned_cleanup_and_decoy(self):
        owned=subprocess.Popen(['/bin/sleep','20'],start_new_session=True)
        decoy=subprocess.Popen(['/bin/sleep','20'],start_new_session=True)
        try:
            record={'pid':owned.pid,'identity':guard.ps(owned.pid)}
            self.assertFalse(guard.stop(dict(record,identity='wrong ownership')))
            self.assertIsNone(owned.poll())
            self.assertTrue(guard.stop(record));owned.wait(timeout=3)
            self.assertIsNone(decoy.poll())
        finally:
            for p in (owned,decoy):
                if p.poll() is None:p.terminate();p.wait()
if __name__=='__main__':unittest.main()
