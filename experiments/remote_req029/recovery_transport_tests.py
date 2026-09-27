import sys,tempfile,time,unittest
from pathlib import Path
from recovery_transport import Transport
from recovery_contract import sha
from recovery_tests import Tests as EngineTests,BAD
HELPER=Path(__file__).with_name('recovery_mailbox.py').resolve()
class Tests(unittest.TestCase):
    def transport(self,root,role='controller',pin=None):
        mailbox=root/'mailbox';mailbox.mkdir(exist_ok=True)
        return Transport(root/(role+'-state'),str(mailbox),str(HELPER),pin or sha(HELPER.read_bytes()),role,time.time()+40,python=sys.executable,fixture=True,interval=0)
    def test_actual_helper_unicode_and_conflict_poison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=self.transport(root);b=self.transport(root,'worker')
            payload={'text':'λ漢字','value':3}
            obj=a.publish('request',payload,1)
            self.assertEqual(b.read('request',1),(payload,obj))
            with self.assertRaises(Exception):a.publish('request',{'changed':1},1)
            calls=a.calls
            with self.assertRaises(Exception):a.read('response',1)
            self.assertEqual(a.calls,calls)
            self.assertTrue(all(e['owned_group_absent'] for e in a.runner.events+b.runner.events))
    def test_wrong_helper_pin_fails_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=self.transport(root,pin='0'*64)
            with self.assertRaises(Exception):a.publish('request',{},1)
            self.assertFalse((root/'mailbox/request-01.json').exists())
    def test_two_engines_actual_helper_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ts={role:self.transport(root,role) for role in ('worker','controller')}
            case=EngineTests();case.wire_factory=lambda role:ts[role]
            w,c,m,s,_=case.pair([BAD]*3)
            self.assertEqual(len(m.sent),3);self.assertEqual(s.actions,[])
            self.assertEqual(c.terminal['status'],'repeated_format_error')
            self.assertTrue(all(e['owned_group_absent'] for t in ts.values() for e in t.runner.events))
if __name__=='__main__':unittest.main()
