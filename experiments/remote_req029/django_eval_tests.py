"""Executed synthetic tests only: never Docker, model or official Django tests."""
import ast,base64,copy,json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import django_eval_contract as c
from django_eval_contract import *
from django_eval_grade import grade,bindings
from django_eval_evaluate import run
from django_eval_guardian import Guardian,verify_baseline
from django_eval_fixture import Fake,launch
from django_eval_process import Runner
from c3r_arbiter import identity
from c6_r_fixtures import descendant_alive
OUT=Path(os.environ['DJANGO_EVAL_FIXTURE_OUT']);OUT.mkdir(parents=True,exist_ok=True)

def release():
    r=template();r.update(run_id='dje029i-fixture',expires_at=time.time()+90,source_commit='a'*40,source_hashes=inventory())
    r['sandbox']['docker_sha256']='b'*64
    return r
def spec(root,mode='baseline'):
    now=time.time();r=release()
    return dict(root=str(root),mode=mode,reference_patch_sha256=PATCH_SHA,release=r,release_sha256='fixture-pin',
        driver_pid=os.getpid(),driver_identity=identity(os.getpid()),run_started=now,total_deadline=now+90,
        created_at=now,preflight_deadline=now+40,name='dtr-fixture',label='a'*64)
def rawlog(mode='reference',extra=True):
    data,_,_=inputs();lines=['>>>>> Start Test Output']
    for t in data['FAIL_TO_PASS']+data['PASS_TO_PASS']:
        lines.append(t+' ... '+('FAIL' if mode=='baseline' and t in data['FAIL_TO_PASS'] else 'ok'))
    if extra:lines+=['test_extra (postgres_tests.test_constraints.Extra.test_extra) ... skipped fixture','FAIL: test_eq (extra.alias)','Ran 75 tests in 0.001s']
    return ('\n'.join(lines+['>>>>> End Test Output'])+'\n').encode()
def waitfor(path,seconds=10):
    end=time.monotonic()+seconds
    while not path.exists() and time.monotonic()<end:time.sleep(.02)
    assert path.exists(),str(path)

class Tests(unittest.TestCase):
    def setUp(self):
        self.root=OUT/self._testMethodName;self.root.mkdir()
    def guardian(self,mode='',write_fail=False):
        root=self.root/'arm';root.mkdir();fake=root/'fake';fake.mkdir()
        (fake/'archive').write_bytes(b'inert archive');(fake/'mode').write_text(mode)
        s=spec(root);b=Fake(root/'docker',s['release']['sandbox'],fake);g=Guardian(s,b)
        if mode=='hang':
            evaluate=b.evaluate
            def timed(cid,op,payload,deadline):
                if op=='test':
                    g.current_deadline=time.time()+.4;g.deadline=g.current_deadline+15
                    deadline=g.current_deadline
                return evaluate(cid,op,payload,deadline)
            b.evaluate=timed
        if write_fail:
            original=g.save
            def fail(name,value):
                if name=='helper.prepare.raw.json':raise OSError('injected journal failure')
                return original(name,value)
            g.save=fail
        return g,b,fake

    def test_01_pinned_registry_command_and_full_inputs(self):
        data,reference,pins=inputs();ns,stock=bindings()
        self.assertEqual(len(set(data['FAIL_TO_PASS']+data['PASS_TO_PASS'])),74)
        self.assertIs(ns['MAP_REPO_TO_PARSER']['django/django'],ns['parse_log_django'])
        self.assertEqual(stock,data['stock_eval_script'])
        self.assertEqual(len(reference),10747)

    def test_02_all_declared_separate_from_extra_aliases(self):
        r=grade(rawlog(),0,'reference','fixture')
        self.assertTrue(r['control_accepted']);self.assertEqual(r['declared_observed_count'],74)
        self.assertEqual(r['parser_map_size'],76);self.assertEqual(r['raw_runner_totals'],[75])
        self.assertEqual(r['extra_statuses']['test_eq'],'FAILED')
        self.assertEqual(len(r['extra_postgres_statuses']),1)

    def test_03_parser_failed_error_skipped_missing_multiline_names(self):
        ns,_=bindings();parser=ns['MAP_REPO_TO_PARSER']['django/django']
        value=parser('test_eq (A.test_eq) ... FAIL\ntest_eq (B.test_eq) ... ERROR\nFAIL: test_eq (A.test_eq)\nname ... skipped why\nmultiline ... Internal Server Error: /a/\nok\n',None)
        self.assertEqual(value['test_eq (A.test_eq)'],'FAILED')
        self.assertEqual(value['test_eq (B.test_eq)'],'ERROR')
        self.assertEqual(value['name'],'SKIPPED');self.assertEqual(value['multiline'],'PASSED')
        self.assertNotIn('missing',value);self.assertEqual(value['test_eq'],'FAILED')
        t=inputs()[0]['FAIL_TO_PASS'][0]
        for suffix in ('skipped reason','expected failure','ERROR','FAIL'):
            r=grade(rawlog().replace((t+' ... ok').encode(),(t+' ... '+suffix).encode()),1,'reference','fixture')
            self.assertFalse(r['control_accepted'])
        r=grade(rawlog().replace((t+' ... ok\n').encode(),b''),0,'reference','fixture')
        self.assertEqual(r['declared_statuses'][t],'MISSING');self.assertFalse(r['control_accepted'])

    def test_04_bad_markers_empty_parser_unknown(self):
        for raw in (b'no markers',b'>>>>> Start Test Output\n>>>>> End Test Output',
                    rawlog()+b'>>>>> End Test Output',rawlog()+b'>>>>> Reset Failed',
                    b'>>>>> End Test Output\n>>>>> Start Test Output'):
            r=grade(raw,0,'reference','fixture')
            self.assertTrue(r['outcome'].startswith('unknown'));self.assertFalse(r['control_accepted'])
        for why in ('timeout','overflow','setup'):
            self.assertFalse(grade(rawlog(),0,'reference','fixture',why)['control_accepted'])

    def test_05_source_task_input_arm_asset_substitutions(self):
        r=release();r['execution_authorized']=True
        validate(r)
        for key,value in [('task','astropy__astropy-14598'),('modes',['reference']),('inputs_sha256','f'*64),
            ('reference_patch_sha256','f'*64),('test_patch_sha256','f'*64),('command','true'),('source_hashes',{}),
            ('protocol','REQ-029C'),('model_free',False),('output_cap',1)]:
            x=copy.deepcopy(r);x[key]=value
            with self.assertRaises(Exception):validate(x)
        for key in ('image','head','archive_sha256','python'):
            x=copy.deepcopy(r);x['sandbox'][key]='wrong'
            with self.assertRaises(Exception):validate(x)
        with self.assertRaises(Exception):validate(template())
        self.assertFalse((self.root/'docker').exists())

    def test_06_bundle_substitution_rejected(self):
        import shutil
        b=self.root/'bundle';shutil.copytree(BUNDLE,b)
        (b/'reference.diff').write_bytes((b/'reference.diff').read_bytes()+b' ')
        with self.assertRaises(Exception):inputs(b)

    def test_07_prepared_exact_normalization_and_substitution(self):
        data,ref,_=inputs()
        f=dict(source_diff=ref.decode(),mode='reference',reference_patch_sha256=PATCH_SHA,
            test_patch_sha256=sha(data['test_patch'].encode()),head=HEAD,base=BASE,python=SANDBOX['python'],
            import_path='/testbed/django/__init__.py',omitted_install=OMITTED,untouched_stock_harness=False,
            test_command=COMMAND,test_paths=TEST_PATHS)
        self.assertEqual(bind_prepared(f,'reference'),ref)
        indexed=ref.replace(b'--- a/',b'index 1234567..abcdef0 100644\n--- a/')
        self.assertEqual(normalized(indexed),normalized(ref))
        for changed in (ref.replace(b'violation_error_code=None',b'violation_error_code=0',1),
                        ref.replace(b'@@ -32,6',b'@@ -31,6',1),ref.replace(b'100644',b'100755')+b'\n'):
            with self.assertRaises(Exception):bind_prepared(dict(f,source_diff=changed.decode()),'reference')
        with self.assertRaises(Exception):bind_prepared(f,'baseline')
        self.assertEqual(bind_prepared(dict(f,source_diff='',mode='baseline'),'baseline'),b'')

    def test_08_full_fake_pair_gates_and_no_repeat(self):
        r=release()
        reports=run(r,'fixture-pin',{},self.root/'pair',launch)
        self.assertEqual([x['mode'] for x in reports],MODES)
        self.assertTrue(all(x['control_accepted'] and x['cleanup']['owned_absent'] for x in reports))
        self.assertEqual(reports[0]['outcome'],'unresolved');self.assertEqual(reports[1]['outcome'],'resolved')
        self.assertIsNotNone(reports[1]['baseline_receipt_sha256'])
        with self.assertRaises(FileExistsError):run(r,'fixture-pin',{},self.root/'pair',launch)
        for mode in MODES:
            root=self.root/'pair'/mode
            self.assertFalse((root/'fake/container.json').exists())
            probe=json.loads((root/'preflight.probe.json').read_bytes())
            self.assertEqual(probe['uname']['system'],'INERT')
            self.assertTrue((root/'test.stderr').stat().st_size>0)
        # Substitution after accepted baseline fails independent reference gate.
        root=self.root/'pair/reference';s=json.loads((root/'spec.json').read_bytes())
        s['baseline_receipt_sha256']='0'*64
        with self.assertRaises(Exception):verify_baseline(s)

    def test_09_unexpected_baseline_stops_reference(self):
        reports=run(release(),'fixture-pin',{},self.root/'pair',lambda s,p:launch(s,p,'unexpected'))
        self.assertEqual(len(reports),1);self.assertFalse(reports[0]['control_accepted'])
        self.assertFalse((self.root/'pair/reference').exists())

    def test_10_prepare_failure_no_test_dispatch(self):
        g,b,f=self.guardian('wrong-diff');r=g.run()
        self.assertTrue(r['outcome'].startswith('unknown'));self.assertTrue(r['cleanup']['owned_absent'])
        self.assertFalse((f/'stage-test').exists());self.assertTrue((f/'removed').exists())

    def test_11_timeout_cleanup_and_no_retry(self):
        g,b,f=self.guardian('hang');r=g.run()
        self.assertTrue(r['outcome'].startswith('unknown'));self.assertTrue(r['cleanup']['owned_absent'])
        self.assertTrue((f/'stage-test').exists());self.assertIsNotNone(r['capture'])
        events=[json.loads(p.read_text()) for p in f.glob('event-*')]
        self.assertEqual(sum(v['argv'][0]=='create' for v in events),1)

    def test_12_actual_stream_4mib_overflow_cleanup(self):
        g,b,f=self.guardian('overflow');r=g.run()
        self.assertTrue(r['outcome'].startswith('unknown'));self.assertTrue(r['cleanup']['owned_absent'])
        self.assertIn('output cap',r['infrastructure_error'])
        self.assertLessEqual(r['raw_output_bytes'],OUTPUT_CAP);self.assertGreater(r['raw_output_bytes'],OUTPUT_CAP-65537)

    def test_13_journal_failure_cleanup_not_gated_by_writes(self):
        g,b,f=self.guardian(write_fail=True);r=g.run()
        self.assertTrue(r['cleanup']['owned_absent']);self.assertTrue((f/'removed').exists())
        self.assertFalse((f/'stage-test').exists())

    def test_14_external_driver_death_independent_cleanup(self):
        approval=self.root/'fixture.json';approval.write_text(json.dumps(release()))
        p=subprocess.Popen([sys.executable,str(HERE/'django_eval_fixture.py'),'driver',str(approval),str(self.root/'pair')],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            waitfor(self.root/'pair/baseline/fake/stage-test',15)
            gp=int((self.root/'guardian.pid').read_text())
            os.kill(p.pid,signal.SIGKILL);p.wait(timeout=3)
            waitfor(self.root/'pair/baseline/terminal.json',10)
            report=json.loads((self.root/'pair/baseline/terminal.json').read_bytes())
            self.assertTrue(report['cleanup']['owned_absent']);self.assertFalse(report['control_accepted'])
            self.assertFalse((self.root/'pair/reference').exists())
            end=time.monotonic()+3
            while descendant_alive(gp) and time.monotonic()<end:time.sleep(.03)
            self.assertFalse(descendant_alive(gp))
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=3)

    def test_15_actual_capture_stdout_stderr(self):
        r=Runner(self.root/'capture').run([sys.executable,'-c',"import os;os.write(1,b'OUT');os.write(2,b'ERR')"],time.time()+5)
        self.assertEqual(base64.b64decode(r['stdout_base64']),b'OUT')
        self.assertEqual(base64.b64decode(r['stderr_base64']),b'ERR')
        self.assertTrue(r['owned_group_absent'])

    def test_16_temp_git_prepare_both_arms_no_global_writes(self):
        from django_eval_container import CODE
        ns={'__name__':'inert_functions'};exec(compile(CODE,'container-data','exec'),ns)
        original=Path.cwd()
        try:
            for mode in MODES:
                d=self.root/mode;d.mkdir();os.chdir(d)
                env=dict(os.environ,GIT_AUTHOR_NAME='Yukang Zeng',GIT_AUTHOR_EMAIL='ykzeng2019@gmail.com',
                    GIT_COMMITTER_NAME='Yukang Zeng',GIT_COMMITTER_EMAIL='ykzeng2019@gmail.com')
                def git(*args):return subprocess.check_output(['git',*args],env=env,stderr=subprocess.STDOUT)
                git('init');(d/'source.txt').write_text('old\n');(d/'test.txt').write_text('test\n')
                git('add','.');git('commit','-m','inert base');base=git('rev-parse','HEAD').decode().strip()
                git('commit','--allow-empty','-m','inert setup');head=git('rev-parse','HEAD').decode().strip()
                ns.update(BASE=base,HEAD=head,TEST_PATHS=['test.txt'],steps=[])
                ref=b'diff --git a/source.txt b/source.txt\n--- a/source.txt\n+++ b/source.txt\n@@ -1 +1 @@\n-old\n+new\n'
                tests=b'diff --git a/test.txt b/test.txt\n--- a/test.txt\n+++ b/test.txt\n@@ -1 +1 @@\n-test\n+inert\n'
                diff=ns['prepare'](dict(mode=mode,reference=ref.decode(),test_patch=tests.decode(),
                    reference_patch_sha256=sha(ref),test_patch_sha256=sha(tests)))
                self.assertEqual(normalized(diff),b'' if mode=='baseline' else normalized(ref))
                self.assertEqual((d/'source.txt').read_text(),'old\n' if mode=='baseline' else 'new\n')
                self.assertEqual((d/'test.txt').read_text(),'inert\n')
                self.assertTrue(all('--global' not in step['argv'] for step in ns['steps']))
                self.assertEqual(ns['env']['GIT_CONFIG_GLOBAL'],'/dev/null')
        finally:os.chdir(original)

    def test_17_approval_git_exact_bytes_old_namespace_rejected(self):
        r=release();r['execution_authorized']=True;raw=json.dumps(r,indent=2).encode()
        def read(*args):
            key=args[1]
            if key.endswith(':docs/req029i_fixture.json'):return raw
            return (ROOT/key.split(':',1)[1]).read_bytes()
        with patch.object(c,'git',side_effect=read):
            self.assertEqual(authorize('c'*40,'docs/req029i_fixture.json',sha(raw)),r)
            with self.assertRaises(Exception):authorize('c'*40,'docs/req029c_fixture.json',sha(raw))
            with self.assertRaises(Exception):authorize('c'*40,'docs/req029i_fixture.json','0'*64)
        self.assertFalse((self.root/'docker').exists())

    def test_18_actual_guardian_entrypoint_rejects_arm_before_backend(self):
        import django_eval_guardian as g
        r=release();s=spec(runtime(r)/'wrong');s.update(mode='wrong',approval_args=dict(pin='fixture-pin'),release=r)
        p=self.root/'spec.json';p.write_text(json.dumps(s))
        with patch.object(g,'authorize',return_value=r),patch.object(g,'Backend') as b:
            with self.assertRaises(Exception):g.main(p)
            b.assert_not_called()

    def test_19_no_second_dispatch_after_indeterminate_guardian(self):
        class Failed:
            returncode=1
            def wait(self,timeout):return 1
        calls=[]
        def bad(s,p):calls.append(s['mode']);return Failed()
        with self.assertRaises(Exception):run(release(),'fixture-pin',{},self.root/'pair',bad)
        self.assertEqual(calls,['baseline'])
        with self.assertRaises(FileExistsError):run(release(),'fixture-pin',{},self.root/'pair',bad)
        self.assertEqual(calls,['baseline'])

    def test_20_limits_readonly_and_identity_checked(self):
        g,b,f=self.guardian();r=g.run()
        self.assertTrue(r['control_accepted'])
        events=[json.loads(p.read_text()) for p in f.glob('event-*')]
        create=next(e['argv'] for e in events if e['argv'][0]=='create')
        self.assertIn('--read-only',create);self.assertIn('--pull=never',create)
        self.assertIn('/testbed:rw,exec,nosuid,nodev,size=512m',create)
        self.assertNotIn('--mount',create);self.assertIn(SANDBOX['image'],create)
        self.assertEqual(r['cleanup']['label'],'a'*64)

    def test_21_unknown_baseline_stops_reference(self):
        reports=run(release(),'fixture-pin',{},self.root/'pair',lambda s,p:launch(s,p,'wrong-diff'))
        self.assertEqual(len(reports),1);self.assertTrue(reports[0]['outcome'].startswith('unknown'))
        self.assertFalse((self.root/'pair/reference').exists())

    def test_22_write_failure_in_independent_guardian_subprocess(self):
        reports=run(release(),'fixture-pin',{},self.root/'pair',lambda s,p:launch(s,p,'journal-fail'))
        self.assertEqual(len(reports),1);self.assertTrue(reports[0]['cleanup']['owned_absent'])
        self.assertIn('injected journal',reports[0]['infrastructure_error'])
        self.assertFalse((self.root/'pair/baseline/fake/stage-test').exists())

if __name__=='__main__':unittest.main()
