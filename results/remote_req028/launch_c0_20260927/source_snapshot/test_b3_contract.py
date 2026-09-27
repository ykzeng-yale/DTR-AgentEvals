import unittest
import guard,b3_stop
from mechanics_b3 import build_command
from mechanics_b2r import build_command as prior
class B3ContractTests(unittest.TestCase):
    def test_only_two_cache_flags_change(self):
        expected=prior('alias',123,'B2R')
        for flag in ('--cache-type-k','--cache-type-v'):expected[expected.index(flag)+1]='q4_0'
        self.assertEqual(build_command('alias',123,'B3'),expected)
    def test_watchdog_uses_unchanged_guard(self):
        self.assertIs(b3_stop.guard.violation,guard.violation)
        self.assertIs(b3_stop.guard.sample,guard.sample)
        s={'pressure_level':1,'free_percent':75,'swap_used_mib':0,'owned_rss_bytes':0,'foreign_inference':[],'disk_free_bytes':20*1024**3}
        cases=[('pressure_level',2,'adverse_pressure'),('free_percent',19,'free_metric_below_20'),('swap_used_mib',513,'swap_growth'),('owned_rss_bytes',11*1024**3+1,'owned_rss'),('foreign_inference',[1],'foreign_inference'),('disk_free_bytes',12*1024**3-1,'disk_reserve')]
        for field,value,reason in cases:self.assertEqual(b3_stop.guard.violation(dict(s,**{field:value}),0,float('inf')),reason)
if __name__=='__main__':unittest.main()
