"""C7 inert/fake-Docker coverage only. No real evaluator, Docker, model or hidden-test run."""
import ast,copy,json,os,shutil,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from reference_contract import HERE,MODE,PROTOCOL,MANIFEST_SHA
from c6_protocol import IMAGE,sha
from c3r_arbiter import identity
from c2_relay import Rejected
from reference_contract import inputs,PINS,BUNDLE,PATCH,OUTPUT_CAP,PATCH_SHA
from reference_grade import grade,bindings
from reference_guardian import Guardian
from reference_fake import Fake,fake_launch
from reference_evaluate import run

def release():return dict(run_id='ref029c-fixture',expires_at=time.time()+100,source_commit='a'*40,
    source_hashes={'fixture':'b'*64},sandbox={'image':IMAGE})

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c7-inert-');self.root=Path(self.tmp.name)
        self.children=[];self.guards=[];self.data,self.patch=inputs()
    def tearDown(self):
        for p in self.children:
            if p.poll() is None:p.kill()
            p.wait(timeout=4)
        for g in self.guards:
            if (g.b.fake_root/'container.json').exists():g.cleanup()
        if os.environ.get('REFERENCE_FIXTURE_OUT'):
            shutil.copytree(self.root,Path(os.environ['REFERENCE_FIXTURE_OUT'])/self._testMethodName)
        self.tmp.cleanup()
    def log(self,replace=None,omit=None):
        rows=[]
        for i,t in enumerate(self.data['FAIL_TO_PASS']+self.data['PASS_TO_PASS']):
            if i!=omit:rows.append((replace if i==0 and replace else 'PASSED')+' '+t)
        return ('>>>>> Start Test Output\n'+'\n'.join(rows)+'\n>>>>> End Test Output\n').encode()
    def report(self,raw=None,code=0,**kw):return grade(self.log() if raw is None else raw,code,MODE,'ref029c-fixture',**kw)
    def guardian(self,mode='',seconds=35):
        r=release();root=self.root/'guardian';root.mkdir();fake=root/'fake';fake.mkdir();(fake/'archive').write_bytes(b'inert archive');(fake/'mode').write_text(mode)
        now=time.time();s=dict(root=str(root),mode=MODE,release=r,release_sha256='fixture-pin',
            driver_pid=os.getpid(),driver_identity=identity(os.getpid()),created_at=now,
            preflight_deadline=now+seconds,name='dtr-ref029c-fixture-owned',label='test-owner')
        g=Guardian(s,Fake(root/'docker',r['sandbox'],fake));self.guards.append(g);return g
    def test_all_pass_176_statuses(self):
        r=self.report();self.assertEqual(r['outcome'],'resolved');self.assertEqual(len(r['declared_statuses']),176)
    def test_failed_exit_one_is_valid_test_result(self):self.assertEqual(self.report(self.log('FAILED'),1)['outcome'],'unresolved')
    def test_skipped_never_pass(self):self.assertEqual(self.report(self.log('SKIPPED'))['outcome'],'unresolved')
    def test_xfail_never_pass(self):self.assertEqual(self.report(self.log('XFAIL'))['outcome'],'unresolved')
    def test_missing_never_pass(self):self.assertEqual(self.report(self.log(omit=0))['outcome'],'unresolved')
    def test_empty_map_unknown(self):self.assertEqual(self.report(b'>>>>> Start Test Output\n>>>>> End Test Output')['outcome'],'unknown_unparsable_output')
    def test_markers_missing_duplicate_reversed_unknown(self):
        for raw in (b'PASSED fake',self.log()+b'>>>>> End Test Output',b'>>>>> End Test Output\n>>>>> Start Test Output'):
            self.assertTrue(self.report(raw)['outcome'].startswith('unknown'))
    def test_collection_import_and_bad_marker_unknown(self):
        for text in (b'ERROR collecting',b'ImportError while importing',b'>>>>> Tests Timed Out',b'>>>>> Patch Apply Failed'):
            self.assertTrue(self.report(self.log()+text,1)['outcome'].startswith('unknown'))
    def test_timeout_setup_cleanup_unknown(self):
        self.assertTrue(self.report(infra_error='timeout')['outcome'].startswith('unknown'))
        self.assertTrue(self.report(cleanup_confirmed=False)['outcome'].startswith('unknown'))
        self.assertTrue(self.report(code=2)['outcome'].startswith('unknown'))
        self.assertTrue(self.report(code=1)['outcome'].startswith('unknown'))
    def test_upstream_alias_and_rule_executed(self):
        ns,c=bindings();self.assertEqual(ns['parse_log_pytest_v2']('PASSED x\ny FAILED',None),{'x':'PASSED','y':'FAILED'})
        self.assertEqual(ns['declared_outcome'](['x'],[],{'x':'XFAIL'}),'unresolved')
    def test_patch_mismatch_before_create(self):
        g=self.guardian();bad=self.root/'bad.diff';bad.write_bytes(b'substituted')
        with patch('reference_guardian.inputs',lambda:inputs(patch=bad)):
            r=g.run()
        self.assertTrue(r['outcome'].startswith('unknown'));self.assertFalse(g.create_attempted)
    def test_test_source_substitution_before_create(self):
        g=self.guardian();bundle=self.root/'bundle';shutil.copytree(BUNDLE,bundle);(bundle/'evaluation_inputs.json').write_text('{}')
        with patch('reference_guardian.inputs',lambda:inputs(bundle=bundle)):
            r=g.run()
        self.assertTrue(r['outcome'].startswith('unknown'));self.assertFalse(g.create_attempted)
    def test_nonzero_apply_stops_no_test(self):
        g=self.guardian('apply-fail');r=g.run()
        self.assertTrue(r['outcome'].startswith('unknown'));self.assertFalse((g.b.fake_root/'stage-test').exists());self.assertTrue(r['cleanup']['owned_absent'])
    def test_actual_fake_test_failure_classified(self):
        g=self.guardian('fail');r=g.run();self.assertEqual(r['outcome'],'unresolved');self.assertEqual(r['returncode'],1);self.assertTrue(r['cleanup']['owned_absent'])
    def test_actual_streamed_overflow_cleanup(self):
        g=self.guardian('overflow');r=g.run();self.assertTrue(r['outcome'].startswith('unknown'));self.assertIn('cap',r['infrastructure_error']);self.assertTrue(r['cleanup']['owned_absent'])
        raw=(g.root/'test.partial.output').read_bytes();self.assertTrue(raw);self.assertLessEqual(len(raw),OUTPUT_CAP)
        self.assertEqual(r['raw_output_sha256'],sha(raw));self.assertFalse(r['raw_output_complete'])
    def test_actual_timeout_cleanup(self):
        g=self.guardian('hang',18);r=g.run();self.assertTrue(r['outcome'].startswith('unknown'));self.assertTrue(r['cleanup']['owned_absent'])
    def test_journal_failure_after_create_cleanup(self):
        g=self.guardian();save=g.save
        def fail(name,value):
            if name=='owned.json':raise OSError('fixed journal failure')
            return save(name,value)
        g.save=fail;r=g.run();self.assertTrue(r['cleanup']['owned_absent']);self.assertTrue(r['outcome'].startswith('unknown'))
    def test_terminal_write_failure_still_cleans(self):
        g=self.guardian();save=g.save
        def fail(name,value):
            if name in ('test.output','terminal.json'):raise OSError('fixed terminal write failure')
            return save(name,value)
        g.save=fail
        with self.assertRaises(OSError):g.run()
        self.assertFalse((g.b.fake_root/'container.json').exists())
    def test_one_reference_arm_no_resume(self):
        r=release();root=self.root/'single';out=run(r,'fixture-pin',{},root,fake_launch)
        self.assertEqual(len(out),1);self.assertEqual(out[0]['mode'],MODE)
        self.assertEqual(out[0]['reference_patch_sha256'],PATCH_SHA)
        self.assertNotEqual(out[0]['applied_patch_sha256'],PATCH_SHA)
        self.assertNotIn('candidate_sha256',out[0])
        self.assertTrue((root/MODE/'fake/removed').exists())
        self.assertFalse((root/'candidate').exists());self.assertFalse((root/'baseline').exists())
        with self.assertRaises(FileExistsError):run(r,'fixture-pin',{},root,fake_launch)
    def test_wrong_prepared_diff_no_test(self):
        g=self.guardian('wrong-diff');r=g.run()
        self.assertTrue(r['outcome'].startswith('unknown'))
        self.assertIsNone(r['applied_patch_sha256'])
        self.assertFalse((g.b.fake_root/'stage-test').exists())
        self.assertTrue(r['cleanup']['owned_absent'])
    def test_no_second_when_cleanup_unconfirmed(self):
        r=release();calls=[]
        def launch(s,path):
            calls.append(s['mode']);result=self.report(cleanup_confirmed=False)
            result.update(mode=s['mode'],source_commit=r['source_commit'],release_sha256='fixture-pin',source_hashes=r['source_hashes'],cleanup={'owned_absent':False})
            (path.parent/'terminal.json').write_text(json.dumps(result))
            return SimpleNamespace(returncode=0,wait=lambda timeout:None)
        with self.assertRaisesRegex(Rejected,'cleanup unconfirmed'):run(r,'fixture-pin',{},self.root/'pair',launch)
        self.assertEqual(calls,[MODE])
    def test_no_acceptance_other_patch(self):
        r=release()
        def launch(s,path):
            result=self.report();result.update(mode=s['mode'],reference_patch_sha256='0'*64,release_sha256='fixture-pin',source_hashes=r['source_hashes'],cleanup={'owned_absent':True})
            (path.parent/'terminal.json').write_text(json.dumps(result));return SimpleNamespace(returncode=0,wait=lambda timeout:None)
        with self.assertRaisesRegex(Rejected,'report binding'):run(r,'fixture-pin',{},self.root/'pair',launch)
    def test_actual_driver_death_independent_cleanup(self):
        r=release();path=self.root/'release.json';path.write_text(json.dumps(r));root=self.root/'pair'
        p=subprocess.Popen([sys.executable,str(HERE/'reference_fake.py'),'driver',str(path),str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);self.children.append(p)
        deadline=time.time()+12
        while not (root/'reference_positive_control/fake/stage-test').exists():
            self.assertLess(time.time(),deadline);time.sleep(.03)
        p.kill();p.wait(timeout=2)
        while not (root/'reference_positive_control/terminal.json').exists():
            self.assertLess(time.time(),deadline+5);time.sleep(.03)
        result=json.loads((root/'reference_positive_control/terminal.json').read_text());self.assertTrue(result['cleanup']['owned_absent'])
        self.assertFalse((root/'candidate').exists());self.assertFalse((root/'reference_positive_control/fake/container.json').exists())
    def test_container_source_fixed_no_pip_execution(self):
        from c7_container import CODE
        ast.parse(CODE)
        self.assertIn("['apply','--check','-']",CODE);self.assertIn("['apply','-']",CODE)
        self.assertNotIn('shell=True',CODE);self.assertNotIn('pip install',CODE.split("omitted_install=")[0])

    def test_capture_preserves_non_utf8_raw_bytes(self):
        import base64
        from c7_process import Runner
        r=Runner(self.root/'capture').run([sys.executable,'-c','import os;os.write(1,bytes([0,255,254,10]))'],time.time()+3)
        self.assertEqual(base64.b64decode(r['raw_base64']),bytes([0,255,254,10]))
        self.assertTrue(r['owned_group_absent'])

    def test_capture_parent_exit_descendant_cleanup(self):
        from c7_process import Runner
        code='import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])'
        r=Runner(self.root/'capture').run([sys.executable,'-c',code],time.time()+3)
        self.assertTrue(r['owned_group_absent']);self.assertTrue(r['child_reaped'])

    def test_old_approval_cannot_activate_reference(self):
        from reference_contract import authorize
        for path in ('docs/req028_c7_test.json','docs/req028_c6_test.json'):
            with self.assertRaisesRegex(Rejected,'REQ029C approval path'):
                authorize('a'*40,path,'b'*64)

    def test_release_hold_and_inventory(self):
        from reference_contract import authorize,INPUT_SHA
        r=dict(protocol=PROTOCOL,execution_authorized=False,run_id='ref029c-test',expires_at=time.time()+100,
            reference_patch_sha256=PATCH_SHA,reference_manifest_sha256=MANIFEST_SHA,
            inputs_sha256=INPUT_SHA,modes=[MODE],sandbox_seconds=600,total_seconds=600)
        for active,expected in ((False,'execution held'),(True,'source inventory')):
            r.update(execution_authorized=active,source_hashes={});raw=json.dumps(r).encode()
            with patch('reference_contract.git',return_value=raw):
                with self.assertRaisesRegex(Rejected,expected):
                    authorize('a'*40,'docs/req029c_test.json',sha(raw))

    def test_reference_test_payload_binding(self):
        g=self.guardian();r=g.run()
        p=json.loads((g.b.fake_root/'stage-prepare').read_bytes())
        self.assertEqual(p['candidate_sha256'],PATCH_SHA)
        self.assertEqual(p['candidate'].encode(),self.patch)
        self.assertEqual(p['test_patch'],self.data['test_patch'])
        self.assertEqual(r['outcome'],'resolved')
        self.assertEqual((g.root/'reference.original.diff').read_bytes(),self.patch)
        self.assertEqual(r['applied_patch_sha256'],sha((g.root/'reference.prepared.diff').read_bytes()))
        self.assertNotIn('candidate_sha256',json.loads((g.root/'prepared.json').read_bytes()))

    def test_container_lifetime_cannot_exceed_fixed_lease(self):
        from c7_backend import Backend
        b=Backend(self.root/'backend',{})
        with patch('c7_backend.time.time',return_value=100),patch('c6_sandbox_backend.Docker.create',return_value='f'*64) as create:
            b.create('fixed-name','fixed-label',685,3000)
        self.assertEqual(create.call_args.args[-1],600)

    def test_approval_exact_inventory_and_source(self):
        import reference_contract as c
        inv=c.inventory()
        r=dict(protocol=PROTOCOL,execution_authorized=True,run_id='ref029c-approved',
            expires_at=time.time()+100,reference_patch_sha256=PATCH_SHA,
            reference_manifest_sha256=MANIFEST_SHA,inputs_sha256=c.INPUT_SHA,
            modes=[MODE],sandbox_seconds=600,total_seconds=600,source_hashes=inv,
            source_commit='b'*40,sandbox=dict(docker_executable=c.DOCKER,image=c.IMAGE,
                archive_sha256=c.ARCHIVE_SHA,archive_bytes=c.ARCHIVE_BYTES,docker_sha256='c'*64))
        def check(value,broken=False):
            raw=json.dumps(value).encode()
            def git(*args):
                if args[1].startswith('a'*40+':'):return raw
                if broken:return b'substitution'
                return (c.ROOT/args[1].split(':',1)[1]).read_bytes()
            with patch('reference_contract.git',side_effect=git):
                return c.authorize('a'*40,'docs/req029c_fixture.json',sha(raw))
        self.assertEqual(check(r),r)
        for changes in ({'modes':['baseline',MODE]},{'expires_at':0},
                        {'candidate_sha256':'f'*64},{'reference_patch_sha256':'f'*64},
                        {'total_seconds':1200},{'source_hashes':{}}):
            with self.subTest(changes=changes),self.assertRaises(Rejected):
                check(dict(r,**changes))
        with self.assertRaisesRegex(Rejected,'source commit differs'):check(r,True)

    def test_driver_guardian_timeout_no_retry(self):
        calls=[]
        def launch(s,path):
            calls.append(s['mode'])
            def wait(timeout):raise subprocess.TimeoutExpired('inert guardian',timeout)
            return SimpleNamespace(wait=wait)
        with self.assertRaisesRegex(RuntimeError,'cleanup UNKNOWN'):
            run(release(),'fixture-pin',{},self.root/'timeout',launch)
        self.assertEqual(calls,[MODE])

    def test_manifest_substitution_before_create(self):
        import reference_contract as c
        ref=self.root/'reference';ref.mkdir();(ref/'manifest.json').write_text('{}')
        g=self.guardian()
        with patch('reference_guardian.inputs',lambda:inputs(reference=ref)):
            r=g.run()
        self.assertFalse(g.create_attempted);self.assertTrue(r['outcome'].startswith('unknown'))

    def test_source_paths_and_hunks_not_normalized_away(self):
        from reference_contract import normalized
        for old,new in ((b'card.py',b'other.py'),(b'66,7',b'67,7'),(b'value.rstrip()',b'value.strip()')):
            self.assertNotEqual(normalized(self.patch),normalized(self.patch.replace(old,new)))

if __name__=='__main__':unittest.main()
