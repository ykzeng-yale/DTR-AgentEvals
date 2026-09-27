"""C1 offline source/artifact diagnosis; never loads a model or executes returned text."""
import hashlib,json,os,re,resource,signal,subprocess,sys,tarfile,time,unittest
from pathlib import Path
import c0_protocol
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/c1_boundary_20260927'
C0=ROOT/'results/remote_req028/mechanics_c0_20260927'
SOURCE=ROOT.parent/'assets/llama.cpp-4fea119de30f6a923992780f6fd5ccb0bee5d47d'
RANGES={'common/common.h':[(417,424),(648,651)],'common/arg.cpp':[(3665,3690)],'common/chat.cpp':[(1325,1346)],'common/chat-diff-analyzer.cpp':[(461,503)],'common/chat-auto-parser-generator.cpp':[(100,169)],'tools/server/server-common.cpp':[(1317,1363)],'tools/server/server-context.cpp':[(1450,1472),(1952,1961)],'tools/server/server-task.cpp':[(412,427)]}
def sha(data):return hashlib.sha256(data).hexdigest()
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def inspect_arm(arm):
    p=C0/arm
    prompt=json.loads((p/'prompt_1.json').read_text());raw=json.loads((p/'call_1.response.json').read_text());receipt=json.loads((p/'call_1.receipt.json').read_text())
    content=raw['choices'][0]['message']['content'];log=(p/'server_0.stderr.log').read_text()
    generated=[{'line':i,'n_gen':int(m[1]),'token_id':int(m[2]),'text_line':line} for i,line in enumerate(log.splitlines(),1) if (m:=re.search(r'n_gen = (\d+), n_remaining = \d+, next token:\s+(\d+)',line))]
    endpoints=json.loads(json.dumps(c0_protocol.analyze(content,raw['choices'][0]['finish_reason'])))
    assert all(receipt[k]==v for k,v in endpoints.items())
    assert len(generated)==raw['usage']['completion_tokens']
    assert prompt['rendered'].endswith('<|im_start|>assistant\n') and '<think>' not in prompt['rendered']
    return {'rendered_sha256':sha(prompt['rendered'].encode()),'token_ids_sha256':sha(json.dumps(prompt['token_ids']).encode()),'prefix_suffix':prompt['rendered'][-24:],'prefix_contains_think':False,'content':content,'first_generated':generated[0],'last_generated':generated[-1],'think_open_emitted':any(x['token_id']==151667 for x in generated),'think_close_emitted':any(x['token_id']==151668 for x in generated),'finish_reason':raw['choices'][0]['finish_reason'],'usage':raw['usage'],'endpoints_unchanged':endpoints,'log_evidence':[{'line':i,'text':line} for i,line in enumerate(log.splitlines(),1) if any(x in line for x in ('reasoning_mode:','reasoning_start:','reasoning_end:','generated parser:','stopped by EOS','reasoning budget:'))]}
def diagnose():
    resource.setrlimit(resource.RLIMIT_CPU,(300,300))
    started=time.time()
    manifest=json.loads((C0/'sha256.json').read_text())
    for name,digest in manifest.items():assert sha((C0/name).read_bytes())==digest,name
    traces=[]
    archive=SOURCE.parent/'llama-4fea119de30f6a923992780f6fd5ccb0bee5d47d.tar.gz'
    baseline=json.loads((ROOT/'results/remote_req028/mechanics_20260927/manifest.json').read_text())
    assert sha(archive.read_bytes())==baseline['runner_archive_sha256']
    with tarfile.open(archive) as tar:
        for name,ranges in RANGES.items():
            data=(SOURCE/name).read_bytes();member=next(m for m in tar.getmembers() if m.name.endswith('/'+name))
            assert tar.extractfile(member).read()==data,name
            lines=data.decode().splitlines()
            traces.append({'path':name,'sha256':sha(data),'archive_equal':True,'excerpts':[{'start':a,'end':b,'text':'\n'.join(f'{i}: {lines[i-1]}' for i in range(a,b+1))} for a,b in ranges]})
    write('source_evidence.json',traces)
    arms={arm:inspect_arm(arm) for arm in ('klear','qwen')}
    canonical=ROOT/'results/remote_req028/b1_artifact_20260927/canonical'
    tokenizer=json.loads((canonical/'tokenizer_config.json').read_text())
    template=(C0/'klear/chat_template.jinja').read_text()
    assert tokenizer['chat_template']==template
    meta={'canonical_template_equals_gguf':True,'canonical_template_sha256':sha(template.encode()),'canonical_readme':(canonical/'README.md').read_text(),'canonical_config_eos':json.loads((canonical/'config.json').read_text())['eos_token_id'],'token_mapping':{i:v for i,v in tokenizer['added_tokens_decoder'].items() if int(i) in (151645,151667,151668)},'archived_source_hashes':{n:sha((canonical/n).read_bytes()) for n in ('tokenizer_config.json','config.json','README.md','community_README.md')},'interpretation':'canonical metadata/template agrees; README only license, no documented safe action meaning for unclosed thinking; weight/converter provenance unresolved'}
    write('canonical_evidence.json',meta);write('arm_comparison.json',arms)
    # Freeze exact sources and line-bearing template/parser/proposal evidence.
    evidence={}
    paths=[Path(__file__),Path(c0_protocol.__file__),Path(__file__).with_name('b4_protocol.py'),Path(__file__).with_name('b4_parser_source.json'),Path(__file__).with_name('split_host_proposal.md')]
    for arm in ('klear','qwen'):paths.append(C0/arm/'chat_template.jinja')
    for path in paths:
        data=path.read_bytes();evidence[str(path.relative_to(ROOT))]={'sha256':sha(data),'text':data.decode()}
    write('local_source_evidence.json',evidence)
    tests=unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures)
    import io
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(tests)
    write('fixtures.json',{'tests':result.testsRun,'passed':result.wasSuccessful(),'output':log.getvalue()});assert result.wasSuccessful()
    write('execution.json',{'started':started,'finished':time.time(),'archive_hashes_verified':len(manifest),'single_compute_thread':True,'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'no_model_load':True,'no_network':True,'no_generated_commands_executed':True})
class Fixtures(unittest.TestCase):
    def test_klear_observed(self):
        r=inspect_arm('klear')
        self.assertEqual(r['first_generated']['token_id'],151667);self.assertEqual(r['last_generated']['token_id'],151645)
        self.assertFalse(r['think_close_emitted']);self.assertTrue(r['endpoints_unchanged']['parser_accepted']);self.assertFalse(r['endpoints_unchanged']['interface_gate'])
    def test_qwen_observed(self):
        r=inspect_arm('qwen')
        self.assertEqual(r['first_generated']['token_id'],3617);self.assertEqual(r['last_generated']['token_id'],151645)
        self.assertFalse(r['think_open_emitted']);self.assertTrue(r['endpoints_unchanged']['interface_gate'])
    def test_existing_gate_distinguishes_parser_from_boundary(self):
        fence='```mswea_bash_command\nfixture_only\n```'
        for content,accepted,gate in [(fence,True,True),('<think>'+fence,True,False),('<think>x</think>'+fence,True,True),(fence+fence,False,False)]:
            r=c0_protocol.analyze(content,'stop');self.assertEqual(r['parser_accepted'],accepted);self.assertEqual(r['interface_gate'],gate)
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();peak=0;count=0
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
    with (OUT/'worker.log').open('x') as log:
        child=subprocess.Popen([sys.executable,__file__,'--worker'],stdout=log,stderr=subprocess.STDOUT,env=env)
        try:
            while child.poll() is None:
                result=subprocess.run(['ps','-p',f'{os.getpid()},{child.pid}','-o','rss='],capture_output=True,text=True,timeout=2)
                rss=sum(int(x) for x in result.stdout.split())*1024;peak=max(peak,rss);count+=1
                if rss>2*1024**3 or time.monotonic()-started>300:raise RuntimeError('C1 resource cap')
                time.sleep(.05)
        except BaseException:
            child.kill();child.wait();raise
    write('resource_monitor.json',{'child_returncode':child.returncode,'elapsed_seconds':time.monotonic()-started,'combined_sampled_peak_rss_bytes':peak,'samples':count,'rss_cap_bytes':2*1024**3,'wall_cap_seconds':300,'method':'single-thread Python compute worker, parent samples own+child RSS; CPU RLIMIT300 in worker; no model/network subprocess'})
    assert child.returncode==0
    write('sha256.json',{p.name:sha(p.read_bytes()) for p in OUT.iterdir() if p.is_file()})
if __name__=='__main__':
    if '--worker' in sys.argv:diagnose()
    else:main()
