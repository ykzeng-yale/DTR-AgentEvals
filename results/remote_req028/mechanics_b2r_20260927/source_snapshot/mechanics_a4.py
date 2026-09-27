"""Exactly four released REQ-028A calls with restart, receipts and owned cleanup."""
import hashlib,json,os,re,socket,subprocess,sys,time,urllib.error,urllib.request,uuid,tarfile
from pathlib import Path
import guard,gguf_meta
from a4_protocol import freeze_prompts, recover, call_indices
ROOT=Path(__file__).resolve().parents[2]
VARIANT='A4'
OUT=ROOT/('results/remote_req028/mechanics_'+VARIANT.lower()+'_20260927')
ASSETS=ROOT.parent/'assets'
MODEL=ASSETS/'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
SOURCE=ASSETS/'llama.cpp-4fea119de30f6a923992780f6fd5ccb0bee5d47d'
SERVER=SOURCE/'build/bin/llama-server'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def phase_write(path,deadline):
    temp=path.with_suffix('.next')
    temp.write_text(json.dumps({'deadline':deadline}));temp.replace(path)
def http(port,path,body=None,timeout=5):
    request=urllib.request.Request('http://127.0.0.1:'+str(port)+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        return response.status,response.read()
def build_command(token,port,variant):
    assert variant=='A4'
    cache='f16'
    return [str(SERVER),'-m',str(MODEL),'--alias',token,'--host','127.0.0.1','--port',str(port),'--ctx-size','32768','--parallel','1','--cache-type-k',cache,'--cache-type-v',cache,'--cache-ram','0','--no-cache-prompt','--no-cache-idle-slots','--no-context-shift','--jinja','--seed','20260927028','--temp','0','--n-predict','128','--threads','2','--threads-batch','2','--threads-http','2','--n-gpu-layers','99','--flash-attn','on','--no-warmup','--batch-size','128','--ubatch-size','32','--verbose']
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    baseline=json.loads((ROOT/'results/remote_req028/mechanics_20260927/manifest.json').read_text())
    archive=ASSETS/'llama-4fea119de30f6a923992780f6fd5ccb0bee5d47d.tar.gz'
    assert sha(archive)==baseline['runner_archive_sha256']
    with tarfile.open(archive) as tar:
        member=next(x for x in tar.getmembers() if x.name.endswith('/tools/server/server-common.cpp'))
        assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==sha(SOURCE/'tools/server/server-common.cpp')
    for name,digest in baseline['runner_binary_hashes'].items():assert sha(SERVER.parent/name)==digest,name
    for name,digest in baseline['runner_source_files'].items():assert sha(SOURCE/name)==digest,name
    assert sha(SERVER)=='fd4de7db51a60ad4710725b5e2d2da9060a0b56bf7759767ba81ac719abc4222'
    assert MODEL.stat().st_size==2497281120
    assert sha(MODEL)=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
    metadata=gguf_meta.read(MODEL);write('model_metadata.json',metadata)
    template=metadata['tokenizer.chat_template']
    (OUT/'chat_template.jinja').write_text(template)
    help_result=subprocess.run([str(SERVER),'--help'],capture_output=True,text=True,timeout=30,check=True)
    (OUT/'server_help.txt').write_text(help_result.stdout+help_result.stderr)
    for flag in ('--cache-ram','--no-cache-prompt','--cache-type-k','--cache-type-v','--parallel','--ctx-size','--jinja','--no-warmup','--batch-size','--ubatch-size','--verbose'):
        assert flag in help_result.stdout,flag
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    token='req028-'+uuid.uuid4().hex
    command=build_command(token,port,VARIANT)
    # No warmup avoids unrecorded token generation; load/health is still verified.
    prompts=['Reply with exactly the text DTR_READY and nothing else.','Return exactly one fenced code block labelled mswea_bash_command containing the command printf DTR_READY. Do not add any other text.']
    bodies=[{'model':token,'messages':[{'role':'system','content':"Follow the user's formatting instructions exactly."},{'role':'user','content':prompts[i%2]}],'temperature':0,'seed':20260927028,'max_tokens':128,'stream':False,'cache_prompt':False,'timings_per_token':True} for i in range(4)]
    manifest={'request':'DTR-REQ-028'+VARIANT,'effective_seed_uint32':20260927028 % 2**32,'batch_size':128,'ubatch_size':32,'kv_type':'f16','frozen_at':time.time(),'ownership_token':token,'port':port,'command':command,'short_request_plan':bodies,'logical_calls':6,'prompt_manifest_state':'pending loaded tokenizer; freeze before first generation','response_schema':{'choices':'list; choices[0].message.content literal text','usage':'prompt_tokens/completion_tokens/total_tokens','timings':'runner-reported prompt/prediction timings when provided'},'source_commit':'4fea119de30f6a923992780f6fd5ccb0bee5d47d','repo_baseline':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'model_sha256':sha(MODEL),'model_revision':'a06e946bb6b655725eafa393f4a9745d460374c9','model_bytes':MODEL.stat().st_size,'server_sha256':sha(SERVER),'template_sha256':sha(OUT/'chat_template.jinja'),'source_hashes':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},'runner_source_files':{str(p.relative_to(SOURCE)):sha(p) for p in [SOURCE/'common/arg.cpp',SOURCE/'tools/server/server-schema.cpp',SOURCE/'tools/server/server-context.cpp']},'limits':{'phase_seconds':900,'load_seconds':180,'request_seconds':180,'rss_bytes':11*1024**3,'swap_growth_mib':512,'minimum_free_metric':20,'admission_free_metric':75},'format_scoring':'literal equality DTR_READY; fenced block exact label, command body equals printf DTR_READY after trimming body whitespace; strict literal fence match also recorded'}
    manifest['runner_binary_hashes']={p.name:sha(p) for p in (SOURCE/'build/bin').iterdir() if p.is_file()}
    manifest['runner_archive_sha256']=sha(ASSETS/'llama-4fea119de30f6a923992780f6fd5ccb0bee5d47d.tar.gz')
    manifest['cmake_distribution_sha256']='d1449f969c54d5c00886d5b643340d493dfb3c81cb39ee29b35453395c11ebf7'
    manifest['model_metadata_sha256']=sha(OUT/'model_metadata.json')
    snapshot=OUT/'source_snapshot';snapshot.mkdir()
    for name,digest in manifest['source_hashes'].items():
        data=(Path(__file__).parent/name).read_bytes();assert hashlib.sha256(data).hexdigest()==digest
        (snapshot/name).write_bytes(data)
    manifest['tokenizer_binding']={'render':'/apply-template via oaicompat_chat_params_parse','tokenize':'/tokenize add_special=true parse_special=true, matching chat completion input path','binding_source_sha256':sha(SOURCE/'tools/server/server-context.cpp'),'helper_source_sha256':sha(SOURCE/'tools/server/server-common.cpp')}
    write('manifest.json',manifest)
    initial_admission=guard.sample();write('initial_admission.json',initial_admission)
    start=time.time();global_deadline=min(start+900,float(os.environ['REQ028_PROGRAM_DEADLINE']));calls=[];lifecycles=[];status='RUNNING'
    try:
        for cycle in range(2):
            if cycle==1:
                recovery_started=time.time()
                def observe_recovery(sample,reason,kind):
                    with (OUT/'recovery.jsonl').open('a') as f:f.write(json.dumps({'time':time.time(),'sample':sample,'reason':reason,'kind':kind})+'\n')
                recover(guard.sample,time.time,time.sleep,observe_recovery,min(global_deadline,recovery_started+180),initial_admission['swap_used_mib'])
                write('recovery.json',{'started':recovery_started,'finished':time.time(),'qualified':True})
            admission=guard.sample()
            assert admission['pressure_level']==1 and admission['free_percent']>=75 and not admission['foreign_inference'] and admission['disk_free_bytes']>=12*1024**3,admission
            prefix='server_'+str(cycle)
            phase=OUT/(prefix+'.phase.json')
            phase_write(phase,min(global_deadline,time.time()+180))
            assert time.time()<global_deadline,'mechanics deadline before launch'
            with (OUT/(prefix+'.stdout.log')).open('xb') as stdout,(OUT/(prefix+'.stderr.log')).open('xb') as stderr:
                child=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True,env={k:v for k,v in os.environ.items() if not k.startswith('LLAMA_ARG_')})
            record={'pid':child.pid,'parent':os.getpid(),'identity':guard.ps(child.pid),'deadline':global_deadline,'phase_deadline_file':str(phase),'swap_baseline':initial_admission['swap_used_mib'],'ownership_token':token,'admission':admission}
            owner=OUT/(prefix+'.ownership.json');owner.write_text(json.dumps(record,indent=2))
            watchdog=subprocess.Popen([sys.executable,str(Path(guard.__file__)),'watch',str(owner)],start_new_session=True)
            loaded=time.time();life={'cycle':cycle,'pid':child.pid,'watchdog_pid':watchdog.pid,'load_started':loaded};lifecycles.append(life)
            print(json.dumps(dict(event='SERVER_START',**life)),flush=True)
            try:
                ready=owner.with_suffix('.watchdog_ready.json')
                until=time.time()+5
                while not ready.exists() and time.time()<until:time.sleep(.05)
                assert ready.exists() and json.loads(ready.read_text())['owned_identity_verified'],'watchdog identity handshake failed'
                assert watchdog.poll() is None,'watchdog exited before load'
                while True:
                    if child.poll() is not None:raise RuntimeError('server exited during load: '+str(child.returncode))
                    if time.time()-loaded>180:raise TimeoutError('load deadline')
                    try:
                        code,raw=http(port,'/health')
                        if code==200:break
                    except (urllib.error.URLError,TimeoutError):pass
                    time.sleep(.5)
                life['load_seconds']=time.time()-loaded
                _,props_raw=http(port,'/props');(OUT/(prefix+'.props.json')).write_bytes(props_raw)
                props=json.loads(props_raw)
                assert props['total_slots']==1,props.get('total_slots')
                assert props['default_generation_settings']['n_ctx']==32768,props['default_generation_settings']
                life['healthy']=True
                if cycle==0:
                    phase_write(phase,min(global_deadline,time.time()+180))
                    def bound_http(path,body):
                        assert watchdog.poll() is None and guard.same(record),'tokenizer watchdog/ownership lost'
                        assert not owner.with_suffix('.abort.json').exists(),'tokenizer resource abort'
                        assert time.time()<global_deadline,'tokenizer global deadline'
                        code,raw=http(port,path,body,timeout=min(30,global_deadline-time.time()))
                        assert code==200
                        return json.loads(raw)
                    bodies,bindings=freeze_prompts(token,bound_http,OUT)
                    write('prompt_manifest.json',{'frozen_at':time.time(),'requests':bodies,'bindings':bindings,'no_generation_yet':True,'preload_manifest_sha256':sha(OUT/'manifest.json')})
                    prompt_manifest_hash=sha(OUT/'prompt_manifest.json')
                else:
                    assert sha(OUT/'prompt_manifest.json')==prompt_manifest_hash,'prompt manifest changed'
                    for body,binding in zip(bodies,bindings):
                        rendered=bound_http('/apply-template',body)['prompt']
                        assert hashlib.sha256(rendered.encode()).hexdigest()==binding['rendered_sha256'],'restart template mismatch'
                for index in call_indices(cycle):
                    assert watchdog.poll() is None,'watchdog exited before request'
                    assert json.loads(ready.read_text())['owned_identity_verified'] and guard.same(record),'ownership lost before request'
                    if owner.with_suffix('.abort.json').exists():raise RuntimeError('resource watchdog abort')
                    assert time.time()<global_deadline,'program deadline before request'
                    phase_write(phase,min(global_deadline,time.time()+180))
                    entry={'call':index+1,'cycle':cycle,'started':time.time(),'status':'STARTED'}
                    write('call_'+str(index+1)+'.request.json',bodies[index])
                    write('call_'+str(index+1)+'.start.json',entry)
                    calls.append(entry)
                    print(json.dumps({'event':'INFERENCE_START','call':index+1,'pid':child.pid}),flush=True)
                    try:
                        code,raw=http(port,'/v1/chat/completions',bodies[index],timeout=min(180,global_deadline-time.time()))
                        (OUT/('call_'+str(index+1)+'.response.json')).write_bytes(raw)
                        response=json.loads(raw);content=response['choices'][0]['message']['content']
                        entry.update(status='TERMINAL',http_status=code,content=content,usage=response.get('usage'),timings=response.get('timings'),finish_reason=response['choices'][0].get('finish_reason'))
                        entry['bound_prompt_tokens']=bindings[index]['rendered_tokens']
                        entry['token_binding_valid']=response['usage']['prompt_tokens']==bindings[index]['rendered_tokens']
                        assert entry['token_binding_valid'],'prompt token binding mismatch'
                        if index not in (1,3):entry['format_compliant']=content=='DTR_READY'
                        else:
                            match=re.fullmatch(r'```mswea_bash_command\n(.*?)\n```',content,re.S)
                            entry['format_compliant']=bool(match and match.group(1).strip()=='printf DTR_READY')
                            entry['literal_fence_match']=content=='```mswea_bash_command\nprintf DTR_READY\n```'
                    except Exception as e:
                        if isinstance(e,urllib.error.HTTPError):
                            (OUT/('call_'+str(index+1)+'.error_response.txt')).write_bytes(e.read())
                        entry.update(status='FAILED',error=repr(e));raise
                    finally:
                        entry['finished']=time.time();entry['response_seconds']=entry['finished']-entry['started']
                        write('call_'+str(index+1)+'.receipt.json',entry)
                    if owner.with_suffix('.abort.json').exists():raise RuntimeError('resource watchdog abort')
            finally:
                guard.stop(record);child.wait(timeout=10);watchdog.wait(timeout=10)
                life.update(released=not guard.same(record),returncode=child.returncode,finished=time.time())
                write(prefix+'.lifecycle.json',life)
            assert life['released']
            assert watchdog.returncode==0,'watchdog failed'
            if owner.with_suffix('.abort.json').exists():raise RuntimeError('resource watchdog abort during cleanup')
        status='COMPLETE'
    except BaseException as error:
        status='FAILED';write('failure.json',{'exception':repr(error),'time':time.time()})
    finally:
        write('status.json',{'status':status,'started':start,'finished':time.time(),'manifest_sha256':sha(OUT/'manifest.json'),'calls_recorded':len(calls),'calls':calls,'lifecycles':lifecycles,'after':guard.sample(),'interpretation':'serving mechanics only; no coding competence or full-context throughput claim'})
        write('sha256.json',{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and not p.name.endswith('.phase.json')})
        print(json.dumps({'event':'QUALIFICATION_END','status':status,'calls':len(calls)}),flush=True)
    return 0 if status=='COMPLETE' else 1
if __name__=='__main__':sys.exit(main())
