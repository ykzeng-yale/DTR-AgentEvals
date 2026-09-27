"""Actual new lifecycle/guardian entrypoints, inert HTTP and fake Docker only."""
import tempfile,threading,time,unittest
from pathlib import Path
from recovery_contract import *
from recovery_fixtures import release,InertModel,Sandbox
from recovery_engine import Worker,Controller
from recovery_transport import Transport
from c3r_hooks import alive
class Tests(unittest.TestCase):
    def test_actual_wrappers_inert_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);mail=root/'mail';mail.mkdir();r,pin=release(seconds=58)
            helper=HERE/'recovery_mailbox.py'
            ts={role:Transport(root/(role+'-net'),str(mail),str(helper),sha(helper.read_bytes()),role,r['expires_at'],interval=0,fixture=True) for role in ('worker','controller')}
            w=Worker(root/'worker',r,pin,ts['worker']);c=Controller(root/'controller',r,pin,ts['controller'])
            m=InertModel(root/'model');s=Sandbox(root/'sandbox',r);errors=[]
            def worker():
                try:w.run(m)
                except BaseException as e:errors.append(repr(e))
            t=threading.Thread(target=worker);t.start()
            try:
                c.run(s);t.join(60)
                self.assertFalse(t.is_alive());self.assertEqual(errors,[])
                self.assertEqual(c.terminal['status'],'submitted',c.terminal)
                self.assertEqual((w.claims,c.claims,m.loads),(2,2,1))
                self.assertFalse(alive(m.life.record))
                self.assertFalse((s.fake_root/'container.json').exists())
                self.assertTrue(c.terminal['cleanup']['owned_absent'])
            finally:
                if m.life:m.stop()
                if s.guardian and s.guardian.poll() is None:s.close()
    def test_old_release_and_approval_path_rejected(self):
        from comparator_fixtures import release as old_release
        from recovery_launch import authorize
        from unittest.mock import patch
        old,_=old_release()
        with self.assertRaises(Exception):validate(old)
        with patch('recovery_launch.git') as git:
            with self.assertRaises(Exception):authorize('a'*40,'docs/req029e_django_qwen_approval_20260927.json','b'*64)
            git.assert_not_called()
if __name__=='__main__':unittest.main()
