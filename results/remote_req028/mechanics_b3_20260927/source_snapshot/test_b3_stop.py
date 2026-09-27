"""Real owned inert-process tests; no model. Every created child is reaped."""
import json,os,subprocess,sys,tempfile,time,unittest,uuid
from pathlib import Path
import guard,b3_stop
from b2_protocol import execute_calls
from a6_control import owned_scope
class StopTests(unittest.TestCase):
    def capture(self,state,child,suffix=''):
        if os.environ.get('B3_TEST_RECEIPTS'):
            dest=Path(os.environ['B3_TEST_RECEIPTS']);dest.mkdir(parents=True,exist_ok=True)
            with (dest/(self._testMethodName+suffix+'.json')).open('x') as f:json.dump({'stop':state,'returncode':child.returncode,'child_exited':child.poll() is not None},f,indent=2)
    def fixture(self,d,ignore=False):
        ready=Path(d)/('ready'+uuid.uuid4().hex);token='b3-test-'+uuid.uuid4().hex
        script="import signal,time,sys;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN if sys.argv[2]=='ignore' else lambda *x:sys.exit(0));Path(sys.argv[1]).touch();time.sleep(30)"
        command=[sys.executable,'-c',script,str(ready),'ignore' if ignore else 'normal',token]
        child=subprocess.Popen(command,start_new_session=True)
        self.addCleanup(lambda:self.reap(child))
        until=time.time()+5
        while not ready.exists() and time.time()<until:time.sleep(.01)
        self.assertTrue(ready.exists())
        r={'pid':child.pid,'identity':guard.ps(child.pid),'command':command,'ownership_token':token,'parent':os.getpid(),'parent_identity':guard.ps(os.getpid()),'deadline':time.time()+30,'swap_baseline':0}
        owner=Path(d)/('owner'+uuid.uuid4().hex+'.json');owner.write_text(json.dumps(r))
        return child,owner,r
    def reap(self,child):
        if child.poll() is None:os.killpg(child.pid,9)
        child.wait(timeout=5)
    def start_stop(self,owner,actor):
        code="import b3_stop,sys;b3_stop.stop(sys.argv[1],sys.argv[2],'test',grace=.25)"
        p=subprocess.Popen([sys.executable,'-c',code,str(owner),actor]);self.addCleanup(lambda:p.wait(timeout=10));return p
    def test_simultaneous_stops_one_term(self):
        with tempfile.TemporaryDirectory() as d:
            child,owner,r=self.fixture(d,True)
            a=self.start_stop(owner,'driver');b=self.start_stop(owner,'watchdog')
            self.assertEqual(a.wait(timeout=10),0);self.assertEqual(b.wait(timeout=10),0);child.wait(timeout=5)
            state=json.loads(owner.with_suffix('.stop.json').read_text())
            self.assertEqual(sum(x['signal']=='TERM' for x in state['signals']),1)
            self.assertEqual(len(state['requests']),2);self.assertFalse(guard.same(r))
            self.capture(state,child)
    def test_normal_stop(self):
        with tempfile.TemporaryDirectory() as d:
            child,owner,r=self.fixture(d)
            state=b3_stop.stop(owner,'driver','normal',grace=.5);child.wait(timeout=5)
            self.assertEqual([x['signal'] for x in state['signals']],['TERM']);self.assertFalse(guard.same(r))
            self.capture(state,child)
    def watch_fixture(self,kind):
        with tempfile.TemporaryDirectory() as d:
            child,owner,r=self.fixture(d)
            parent=None
            if kind=='parent':
                parent=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
                r['parent']=parent.pid;r['parent_identity']=guard.ps(parent.pid);parent.kill();parent.wait()
            if kind=='deadline':r['deadline']=time.time()-1
            owner.write_text(json.dumps(r))
            sample={'time':time.time(),'pressure_level':2 if kind=='pressure' else 1,'free_percent':80,'swap_used_mib':0,'owned_rss_bytes':0,'foreign_inference':[],'disk_free_bytes':20*1024**3}
            code="import b3_stop,sys,json;b3_stop.guard.sample=lambda pid:json.loads(sys.argv[2]);b3_stop.watch(sys.argv[1])"
            w=subprocess.Popen([sys.executable,'-c',code,str(owner),json.dumps(sample)])
            self.assertEqual(w.wait(timeout=10),0);child.wait(timeout=5)
            abort=json.loads(owner.with_suffix('.abort.json').read_text());self.assertTrue(abort['owned_stop'])
            self.assertEqual(abort['reason'],{'pressure':'adverse_pressure','parent':'owner_parent_exited','deadline':'deadline'}[kind])
            self.assertFalse(guard.same(r))
            self.capture(dict(json.loads(owner.with_suffix('.stop.json').read_text()),abort=abort),child)
    def test_pressure_abort(self):self.watch_fixture('pressure')
    def test_parent_death(self):self.watch_fixture('parent')
    def test_deadline(self):self.watch_fixture('deadline')
    def test_stop_owner_dies_fallback_no_second_term(self):
        with tempfile.TemporaryDirectory() as d:
            child,owner,r=self.fixture(d,True)
            code="import b3_stop,os,sys;b3_stop.stop(sys.argv[1],'dead-owner','test',grace=.2,after_claim=lambda:os._exit(17))"
            first=subprocess.Popen([sys.executable,'-c',code,str(owner)])
            self.assertEqual(first.wait(timeout=5),17)
            state=b3_stop.stop(owner,'successor','dead-owner fallback',grace=.2);child.wait(timeout=5)
            self.assertEqual([x['signal'] for x in state['signals']],['KILL']);self.assertFalse(guard.same(r))
            self.capture(state,child)
    def test_stale_identity_refuses_live_decoy(self):
        with tempfile.TemporaryDirectory() as d:
            child,owner,r=self.fixture(d)
            bad=dict(r,identity='wrong birth identity');owner.write_text(json.dumps(bad))
            state=b3_stop.stop(owner,'driver','stale')
            self.assertEqual(state['signals'],[]);self.assertIsNone(child.poll())
            owner.write_text(json.dumps(r))
            # New key/journal is required; never reinterpret the stale journal.
            proper=Path(d)/'proper.json';proper.write_text(json.dumps(r))
            b3_stop.stop(proper,'test-cleanup','normal',grace=.5);child.wait(timeout=5)
            self.capture(dict(stale_refusal=state,cleanup=json.loads(proper.with_suffix('.stop.json').read_text())),child)
    def test_first_abort_skips_rest_and_cleans(self):
        with tempfile.TemporaryDirectory() as d:
            child,owner,r=self.fixture(d);calls=[]
            def dispatch(i):calls.append(i);raise RuntimeError('first infrastructure failure')
            with self.assertRaises(RuntimeError):
                with owned_scope(lambda:b3_stop.stop(owner,'driver','failure',grace=.5)):execute_calls(dispatch)
            child.wait(timeout=5);self.assertEqual(calls,[0]);self.assertFalse(guard.same(r))
            self.capture(dict(json.loads(owner.with_suffix('.stop.json').read_text()),calls=calls),child)
if __name__=='__main__':unittest.main()
