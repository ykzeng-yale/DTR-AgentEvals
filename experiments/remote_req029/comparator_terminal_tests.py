"""Source-only terminal reserve tests. No model, Docker or network."""
import json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from comparator_engine import Base
from comparator_fixtures import release

class Wire:
    def __init__(self,fail=False):
        self.failed=False;self.deadline=100;self.calls=[];self.events=[];self.fetches=0
        self.runner=SimpleNamespace(events=[]);self.fail=fail
    def publish(self,kind,value):
        self.calls.append((kind,self.deadline,value))
        if self.fail:raise TimeoutError('fixture transport timeout')

class Tests(unittest.TestCase):
    def run_case(self,now=1000,expiry=2000,poisoned=False,fail=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        r,p=release();wire=Wire(fail);wire.failed=poisoned
        base=Base(Path(tmp.name)/'role',r,p,wire);base.r['expires_at']=expiry;base.deadline=300
        with patch('comparator_engine.time.time',return_value=now):
            result=base.finish('worker','terminal_or_failure','ADMISSION_WINDOW_EXPIRED',{'not_loaded':True,'owned_absent':True})
        return base,wire,result
    def test_expired_setup_reports_with_terminal_only_reserve(self):
        b,w,r=self.run_case();self.assertEqual(len(w.calls),1);self.assertEqual(w.calls[0][1],1015)
        self.assertEqual(b.deadline,300);self.assertEqual(w.deadline,100)
        self.assertTrue(b.chain.done);self.assertEqual(r['claims'],0);self.assertEqual(r['dispatches'],[])
        self.assertEqual(json.loads((b.root/'terminal.local.json').read_text()),r)
    def test_absolute_expiry_caps_reserve(self):
        _,w,_=self.run_case(expiry=1003);self.assertEqual(w.calls[0][1],1003)
    def test_absolute_expiry_prevents_publication(self):
        b,w,_=self.run_case(expiry=1000);self.assertEqual(w.calls,[]);self.assertTrue((b.root/'terminal.local.json').exists())
    def test_poisoned_transport_not_retried(self):
        _,w,_=self.run_case(poisoned=True);self.assertEqual(w.calls,[])
    def test_failed_publication_restores_deadline_and_preserves_local(self):
        b,w,_=self.run_case(fail=True);self.assertEqual(len(w.calls),1);self.assertEqual(w.deadline,100)
        self.assertTrue((b.root/'terminal.publication.failure.json').exists());self.assertTrue((b.root/'terminal.local.json').exists())
    def test_repeat_finish_does_not_redispatch(self):
        b,w,_=self.run_case()
        with self.assertRaises(Exception):b.finish('worker','terminal_or_failure','repeat',{})
        self.assertEqual(len(w.calls),1)

if __name__=='__main__':unittest.main()
