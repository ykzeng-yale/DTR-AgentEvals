"""Actual new lifecycle/guardian entrypoints, inert HTTP and fake Docker only."""
import json,os,subprocess,sys,tempfile,threading,time,unittest
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
    def test_actual_driver_sigkill_cleanup(self):
        for mode in ('model','sandbox'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                with (root/'driver.log').open('xb') as log:
                    p=subprocess.Popen([sys.executable,str(HERE/'recovery_fixture_driver.py'),mode,str(root)],stdout=log,stderr=log)
                    try:
                        until=time.monotonic()+15
                        while not (root/'ready').exists():
                            self.assertIsNone(p.poll());self.assertLess(time.monotonic(),until);time.sleep(.03)
                        p.kill();p.wait(timeout=3)
                        report=root/('model/supervisor_exit.json' if mode=='model' else 'sandbox/state/terminal.json')
                        until=time.monotonic()+8
                        while not report.exists():
                            self.assertLess(time.monotonic(),until);time.sleep(.03)
                        value=json.loads(report.read_text());self.assertTrue(value['cleanup']['owned_absent'],value)
                        if mode=='model':
                            record=json.loads((root/'model/owner.json').read_text());self.assertFalse(alive(record))
                        else:self.assertFalse((root/'sandbox/fake/container.json').exists())
                    finally:
                        if p.poll() is None:p.kill();p.wait(timeout=3)
    def test_real_git_source_approval_and_mutation(self):
        from recovery_launch import authorize
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);r,pin=release();pins=inventory()
            def git(*args):
                return subprocess.check_output(['git',*args],cwd=root,env=dict(os.environ,GIT_AUTHOR_NAME='Yukang Zeng',GIT_AUTHOR_EMAIL='ykzeng2019@gmail.com',GIT_COMMITTER_NAME='Yukang Zeng',GIT_COMMITTER_EMAIL='ykzeng2019@gmail.com'),stderr=subprocess.DEVNULL).decode().strip()
            git('init','-q')
            for name in pins:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
            git('add','.');git('commit','-qm','inert source fixture');source=git('rev-parse','HEAD')
            r.update(worker_commit=source,controller_commit=source,source_hashes=pins)
            path='docs/req029o_inert_approval.json';(root/'docs').mkdir(exist_ok=True);raw=encode(r);(root/path).write_bytes(raw)
            git('add',path);git('commit','-qm','inert approval fixture');approval=git('rev-parse','HEAD')
            with patch('recovery_launch.ROOT',root):
                actual,pin=authorize(approval,path,sha(raw));self.assertEqual(actual,r)
                with self.assertRaises(Exception):authorize(approval,path,'0'*64)
                # Changed committed source cannot be smuggled behind correct release hash.
                wrong=dict(r,worker_commit=approval,controller_commit=approval)
                changed=next(iter(pins));(root/changed).write_text('fixture mutation')
                git('add',changed);git('commit','-qm','inert mutation');wrong['worker_commit']=wrong['controller_commit']=git('rev-parse','HEAD')
                wr=encode(wrong);(root/path).write_bytes(wr);git('add',path);git('commit','-qm','inert bad approval')
                with self.assertRaises(Exception):authorize(git('rev-parse','HEAD'),path,sha(wr))
if __name__=='__main__':unittest.main()
