"""Authored process fixtures: no CUDA, model weights, task commands or jobs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from experiments.lead_req030 import req030ai_episode_worker as worker

FIXTURE = r'''
import json, os, signal, sys, time
from pathlib import Path
from experiments.lead_req030.req030ai_episode_worker import execute_worker, write_new
spec_path, directory, behavior = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
if behavior == 'ignore_term': signal.signal(signal.SIGTERM, signal.SIG_IGN)
class Tensor:
    def __init__(self, ids): self.ids=ids;self.shape=(1,len(ids))
    def to(self, device): return self
    def tolist(self): return [self.ids]
    def __getitem__(self, key):
        class Slice:
            def __init__(self, ids): self.ids=ids
            def tolist(self): return self.ids
        return Slice(self.ids[key[1]])
class Tokenizer:
    eos_token_id=2
    def apply_chat_template(self, messages, **kwargs):return '|'.join(m['content'] for m in messages)
    def __call__(self, *args, **kwargs):return {'input_ids':Tensor([11,12,13])}
    def decode(self, *args, **kwargs):
        if behavior == 'decode_stall':time.sleep(30)
        return '```mswea_bash_command\nfixture_observation\n```'
def load(release, model_root, run_dir):
    (directory / 'load_entered').write_text('inert only')
    if behavior == 'load_stall': time.sleep(30)
    class Model:
        def generate(self, **kwargs):
            if behavior in {'call_stall', 'ignore_term', 'owner_death'}: time.sleep(30)
            return Tensor(kwargs['input_ids'].ids+[42,2])
    return {m['repo']:Model() for m in release['models']['models']}, Tokenizer(), {'inert':True}
def launch(**kwargs):
    bundle = kwargs['bundle']
    public = list(bundle.rglob('*.json'))
    assert len(public) == 1 and public[0].parent.name == 'public'
    assert not (bundle / 'evaluator').exists()
    assert set(json.loads(public[0].read_bytes())) == {'instance_id','repo','base_commit','problem_statement'}
    agent_dir = kwargs['model_run_dir']; agent_dir.mkdir()
    stream = (agent_dir / 'events.jsonl').open('x')
    seq = 0
    def emit(event, **extra):
        nonlocal seq
        seq += 1
        stream.write(json.dumps({'sequence':seq,'event':event,**extra})+'\n');stream.flush();os.fsync(stream.fileno())
    emit('agent_run_start')
    if behavior == 'episode_stall': time.sleep(30)
    if behavior == 'tool_cleanup_missing': emit('action_start',index=1)
    from experiments.lead_req030.seaborn_public_input import load_pinned_agent_templates
    templates=load_pinned_agent_templates()
    config={'action_regex':r'```mswea_bash_command\s*\n(.*?)\n```',
        'observation_template':templates.observation_template,'format_error_template':templates.format_error_template}
    adapter=kwargs['model_factory_builder'](lambda event:emit(**event),config)
    adapter.query([{'role':'system','content':'frozen'},{'role':'user','content':'public task'}])
    emit('agent_run_finish',physical_model_calls=1)
    stream.close()
    if behavior == 'receipt_corrupt':
        with (agent_dir/'events.jsonl').open('a') as f:f.write('{bad JSON}\n')
    if behavior == 'lifecycle_corrupt':
        with (directory/'lifecycle.jsonl').open('a') as f:f.write('{bad JSON}\n')
    if behavior == 'missing_native': (agent_dir/'events.jsonl').unlink()
    assert 'evaluator' not in kwargs
    (kwargs['event_parent'] / 'patch.diff').write_bytes(b'authored inert patch')
    return {'agent_exit_status':'Submitted','submission_eligible':True,'physical_calls':1,'inert':True}
execute_worker(json.loads(spec_path.read_bytes()), directory, components=(load, launch))
'''


def spec_for(tmp_path):
    inputs = tmp_path / 'inputs'; inputs.mkdir()
    task = {'instance_id':'fixture__repo-1','repo':'fixture/repo','base_commit':'a'*40,
            'problem_statement':'Public inert task; no evaluator or reference data.'}
    public = inputs/'public.json'; public.write_bytes(worker.canonical(task))
    def pin(path): return {'path':str(path), 'sha256':worker.digest_file(path)}
    files = {}
    for name in ('image.sif','source.tar','apptainer'):
        path=inputs/name;path.write_bytes(b'inert fixture');files[name]=pin(path)
    model_root=inputs/'models';model_root.mkdir()
    from experiments.lead_req030.req030ai_schedule_adapter import MODEL_PINS
    models=[dict(pin,files=[]) for pin in MODEL_PINS.values()]
    return {'schema':'dtr.req030ai.episode.v1','release_sha256':'d'*64,
        'model_release':{'release_id':'inert-unreleased','models':{'models':models},
                         'runtime':{'gpu_model_aliases':[]},'resource_cap':{'gpu_model':'inert'},
                         'tasks':[{k:v for k,v in task.items() if k!='problem_statement'} |
                                  {'public_projection_sha256':worker.digest_file(public)}]},
        'model_id':models[0]['repo'],'schedule':None,'public_projection':pin(public),'image':files['image.sif'],
        'source_tar':files['source.tar'],'apptainer':files['apptainer'],
        'model_root':str(model_root),'expected_image_head':'e'*40,
        'source_pins':{rel:worker.digest_file(worker.ROOT/rel) for rel in worker.REQUIRED_SOURCES}}


def prepare(tmp_path, behavior='success'):
    spec=spec_for(tmp_path)
    run=tmp_path/'run';run.mkdir()
    spec_path=tmp_path/'spec.json';spec_path.write_bytes(worker.canonical(spec))
    fixture=tmp_path/'fixture.py';fixture.write_text(FIXTURE)
    command=[sys.executable,str(fixture),str(spec_path),str(run),behavior]
    return spec,run,command


def deadlines(**kwargs):
    return worker.Deadlines(**({'load':1,'call':.15,'episode':1,'outer':3,
                               'term_grace':.08,'kill_grace':.5,'cleanup_grace':.12}|kwargs))


def guard(run, command, limits=None, *, owner_absent=False):
    read_fd,owner_fd=os.pipe()
    if owner_absent:os.close(owner_fd)
    try:
        return worker.guard_worker(owner_fd=read_fd,command=command,directory=run,
                                   deadlines=limits or deadlines())
    finally:
        if not owner_absent:os.close(owner_fd)


def assert_dead(pid):
    with pytest.raises(ProcessLookupError):os.kill(pid,0)


def test_complete_worker_pipeline_is_public_only_and_parent_does_not_import_torch(tmp_path,monkeypatch):
    _,run,command=prepare(tmp_path)
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    before='torch' in sys.modules
    receipt=guard(run,command)
    assert receipt['status']=='episode_complete'
    assert receipt['submission_eligible'] is True
    assert receipt['worker_reaped'] and receipt['cleanup_verified']
    assert not receipt['abort_batch']
    assert ('torch' in sys.modules)==before
    assert_dead(receipt['worker_pid'])


@pytest.mark.parametrize('behavior,reason',[('call_stall','call_deadline'),('ignore_term','call_deadline'),('decode_stall','call_deadline'),
                                          ('episode_stall','episode_deadline')])
def test_hard_deadline_reaps_worker_and_forbids_harvest(tmp_path,monkeypatch,behavior,reason):
    _,run,command=prepare(tmp_path,behavior)
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    receipt=guard(run,command,deadlines(episode=.3))
    assert receipt['reason']==reason
    assert receipt['status']=='operational_time_limit'
    assert receipt['outcome']['grade']['graded'] and receipt['outcome']['grade']['resolved'] is False
    assert not receipt['submission_eligible']
    assert not (run/'episode'/'patch.diff').exists()
    assert receipt['worker_reaped'] and receipt['cleanup_verified']
    assert_dead(receipt['worker_pid'])
    if behavior=='ignore_term':assert receipt['kill_sent']


def test_load_stall_is_setup_unknown_and_reaped(tmp_path,monkeypatch):
    _,run,command=prepare(tmp_path,'load_stall');monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    receipt=guard(run,command,deadlines(load=.2))
    assert receipt['reason']=='load_deadline' and receipt['status']=='infrastructure_unknown'
    assert receipt['worker_reaped'] and not receipt['submission_eligible']
    assert_dead(receipt['worker_pid'])


@pytest.mark.parametrize('behavior',['receipt_corrupt','lifecycle_corrupt','missing_native','tool_cleanup_missing'])
def test_unverifiable_evidence_never_becomes_success(tmp_path,monkeypatch,behavior):
    _,run,command=prepare(tmp_path,behavior);monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    receipt=guard(run,command)
    assert receipt['status']=='infrastructure_unknown' and not receipt['submission_eligible']
    assert receipt['abort_batch'] and not receipt['cleanup_verified']
    assert receipt['worker_reaped']


def test_dead_owner_before_start_cannot_launch_worker(tmp_path):
    _,run,command=prepare(tmp_path)
    receipt=guard(run,command,owner_absent=True)
    assert receipt['reason']=='owner_absent_before_start'
    assert receipt['worker_pid'] is None
    assert not (run/'load_entered').exists()


def test_real_owner_sigkill_triggers_independent_guardian_cleanup(tmp_path,monkeypatch):
    _,run,command=prepare(tmp_path,'owner_death')
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    guardian_script=tmp_path/'guardian.py'
    guardian_script.write_text(
        'import json,sys\nfrom pathlib import Path\n'
        'from experiments.lead_req030.req030ai_episode_worker import guard_worker,Deadlines\n'
        'guard_worker(owner_fd=int(sys.argv[1]),directory=Path(sys.argv[2]),command=json.loads(sys.argv[3]),'
        'deadlines=Deadlines(load=2,call=5,episode=6,outer=9,term_grace=.08,kill_grace=.5,cleanup_grace=.12))\n')
    owner_script=tmp_path/'owner.py'
    owner_script.write_text(
        'import json,os,subprocess,sys,time\n'
        'read_fd,owner_fd=os.pipe()\n'
        'p=subprocess.Popen([sys.executable,sys.argv[1],str(read_fd),sys.argv[2],sys.argv[3]],'
        'pass_fds=(read_fd,),start_new_session=True)\n'
        'os.close(read_fd)\n'
        'time.sleep(30)\n')
    owner=subprocess.Popen([sys.executable,str(owner_script),str(guardian_script),str(run),json.dumps(command)])
    try:
        until=time.monotonic()+3
        while not (run/'episode'/'agent'/'events.jsonl').exists():
            assert time.monotonic()<until
            time.sleep(.02)
        owner.kill();owner.wait(timeout=1)
        result=run/'guardian_result.json'
        until=time.monotonic()+3
        while not result.exists():
            assert time.monotonic()<until
            time.sleep(.02)
        receipt=json.loads(result.read_bytes())
        assert receipt['reason']=='owner_eof' and receipt['status']=='infrastructure_unknown'
        assert receipt['worker_reaped'] and receipt['cleanup_verified']
        assert not receipt['submission_eligible']
        assert_dead(receipt['worker_pid'])
    finally:
        if owner.poll() is None:owner.kill();owner.wait(timeout=1)


def test_next_untouched_episode_can_run_after_verified_deadline_cleanup(tmp_path,monkeypatch):
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    first=tmp_path/'first';first.mkdir();_,run1,cmd1=prepare(first,'ignore_term')
    a=guard(run1,cmd1)
    second=tmp_path/'second';second.mkdir();_,run2,cmd2=prepare(second)
    b=guard(run2,cmd2)
    assert a['status']=='operational_time_limit' and not a['abort_batch']
    assert b['status']=='episode_complete'
    assert a['worker_pid']!=b['worker_pid']
    assert not (run1/'episode'/'patch.diff').exists()


def test_spec_rejects_evaluator_injection_and_source_pin_mismatch(tmp_path):
    spec=spec_for(tmp_path)
    worker.validate_spec(spec)
    spec['evaluator']={'reference_patch':'forbidden'}
    with pytest.raises(ValueError,match='public-only'):worker.validate_spec(spec)
    del spec['evaluator']
    spec['source_pins'][worker.REQUIRED_SOURCES[0]]='0'*64
    with pytest.raises(ValueError,match='source hash'):worker.validate_spec(spec)


@pytest.mark.parametrize('schedule', [None, 'SL'])
@pytest.mark.parametrize('malformed', ['duplicate', 'missing', 'wrong_revision', 'wrong_repo', 'extra'])
def test_nonfrozen_model_pair_is_rejected_before_loading(tmp_path, schedule, malformed):
    spec=spec_for(tmp_path);spec['schedule']=schedule
    models=spec['model_release']['models']['models']
    if malformed=='duplicate':models[1]=dict(models[0])
    elif malformed=='missing':models.pop()
    elif malformed=='wrong_revision':models[1]['revision']='0'*40
    elif malformed=='wrong_repo':models[1]['repo']='unfrozen/model'
    else:models.append(dict(models[0]))
    run=tmp_path/'rejected';run.mkdir()
    entered=[]
    def must_not_load(*args, **kwargs):
        entered.append('load');raise AssertionError('invalid pair reached model loading')
    def must_not_launch(*args, **kwargs):
        entered.append('launch');raise AssertionError('invalid pair reached launch')
    with pytest.raises(ValueError, match='two unique frozen model identities'):
        worker.execute_worker(spec, run, components=(must_not_load, must_not_launch))
    assert entered==[]
    events=[json.loads(line) for line in (run/'lifecycle.jsonl').read_text().splitlines()]
    assert [event['event'] for event in events]==['worker_start', 'worker_error']
    assert not (run/'public_bundle').exists()


def test_default_deadlines_are_frozen_and_invalid_limits_rejected():
    cap=worker.Deadlines()
    assert (cap.load,cap.call,cap.episode,cap.outer)==(600,600,2700,3600)
    with pytest.raises(ValueError):worker.Deadlines(load=float('nan'))
    with pytest.raises(ValueError):worker.Deadlines(outer=10)


REAL_LAUNCH = r'''
import json, os, sys, types
from pathlib import Path
from experiments.lead_req030 import req030ai_episode_worker as w
from experiments.lead_req030 import req030ag_screen as screen
from experiments.lead_req030 import req030ag_seaborn_apptainer_runner as runner
spec_path,directory,behavior=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
readlink=os.readlink
runner.os.readlink=lambda p,*a,**kw:'net:[inert]' if str(p)=='/proc/self/ns/net' else readlink(p,*a,**kw)
sys.modules['torch']=types.SimpleNamespace(cuda=types.SimpleNamespace(synchronize=lambda:None,
    reset_peak_memory_stats=lambda:None,max_memory_allocated=lambda:123,max_memory_reserved=lambda:456))
def make_workspace(source,seed,dest,**kwargs):
    assert source==Path(json.loads(spec_path.read_bytes())['source_tar']['path'])
    dest.write_bytes(b'inert workspace seed')
screen.make_workspace=make_workspace
class Tensor:
    def __init__(self,ids):self.ids=ids;self.shape=(1,len(ids))
    def to(self,device):return self
    def tolist(self):return [self.ids]
    def __getitem__(self,key):
        class Slice:
            def __init__(self,ids):self.ids=ids
            def tolist(self):return self.ids
        return Slice(self.ids[key[1]])
class Tokenizer:
    eos_token_id=2
    def __init__(self):self.turn=0
    def apply_chat_template(self,messages,**kwargs):
        self.turn=sum(m['role']=='assistant' for m in messages)+1
        return '|'.join(m['content'] for m in messages)
    def __call__(self,*a,**kw):return {'input_ids':Tensor([11,12,13])}
    def decode(self,*a,**kw):
        command='echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT' if self.turn==10 else 'fixture_observation'
        return '```mswea_bash_command\n'+command+'\n```'
def load(release,model_root,run_dir):
    class Model:
        def generate(self,**kw):return Tensor(kw['input_ids'].ids+[42,2])
    return {m['repo']:Model() for m in release['models']['models']},Tokenizer(),{'inert':True}
w.execute_worker(json.loads(spec_path.read_bytes()),directory,components=(load,screen.launch_agent_episode))
'''


def full_launch_fixture(tmp_path, schedule='SL', behavior='success'):
    spec=spec_for(tmp_path)
    from experiments.lead_req030.req030ai_schedule_adapter import MODEL_PINS
    spec['model_release']['models']['models']=[dict(pin,files=[]) for pin in MODEL_PINS.values()]
    spec['model_id']=MODEL_PINS[schedule[0]]['repo'];spec['schedule']=schedule
    fake=Path(spec['apptainer']['path'])
    preflight='DTR_PREFLIGHT\t'+'e'*40+'\t'+'a'*40+'\t'+'f'*40+'\t'+'f'*40+'\t134217728\t67108864\n'
    fake.write_text(f'''#!{sys.executable}
import os,sys,time
args=sys.argv[1:]
if args==['--version']:print('Apptainer inert fixture');raise SystemExit(0)
assert '--containall' in args and '--no-home' in args and args[args.index('--network')+1]=='none'
command=args[-1]
if 'DTR_PREFLIGHT' in command:print({preflight!r},end='')
elif command=='fixture_observation':
    # Authored inert workspace mutation; the fake never executes model text.
    workspace=__import__('pathlib').Path(args[args.index('--bind')+1].split(':/testbed:')[0])
    with workspace.open('ab') as image:image.write(b'|inert observation')
    if {behavior!r}=='state_unavailable9' and workspace.read_bytes().count(b'|inert observation')==8:workspace.unlink()
    print('authored observation')
elif command=='echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT':print('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')
elif command=='/tmp/harvest.sh':
    if {behavior!r}=='harvest_stall':print(os.getpid(),flush=True);time.sleep(30)
    print('authored inert patch')
else:raise SystemExit('unapproved fixture')
''')
    fake.chmod(0o700);spec['apptainer']['sha256']=worker.digest_file(fake)
    run=tmp_path/'run';run.mkdir(mode=0o700)
    spec_path=tmp_path/'spec.json';spec_path.write_bytes(worker.canonical(spec))
    fixture=tmp_path/'real_launch_fixture.py';fixture.write_text(REAL_LAUNCH)
    return run,[sys.executable,str(fixture),str(spec_path),str(run),behavior]


@pytest.mark.parametrize('schedule',['SS','SL','LS','LL'])
def test_real_launch_default_agent_schedule_and_durable_decisions_1_9(tmp_path,monkeypatch,schedule):
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    run,command=full_launch_fixture(tmp_path,schedule)
    receipt=guard(run,command,deadlines(load=2,call=1,episode=5,outer=8,cleanup_grace=3))
    assert receipt['status']=='episode_complete', (receipt,(run/'worker.out').read_text())
    result=receipt['outcome']
    assert result['schedule']==schedule and result['physical_calls']==10
    assert 'model_id' not in result and set(result['model_pins'])=={'S','L'}
    events=[json.loads(x) for x in (run/'episode'/'agent'/'events.jsonl').read_text().splitlines()]
    decisions=[e for e in events if e['event']=='routing_decision']
    assert [e['logical_call'] for e in decisions]==[1,9]
    assert [e['model_action'] for e in decisions]==list(schedule)
    ready=next(json.loads(line) for line in (run/'lifecycle.jsonl').read_text().splitlines()
               if json.loads(line)['event']=='model_ready')['monotonic']
    assert decisions[0]['episode_deadline_monotonic']==decisions[1]['episode_deadline_monotonic']==ready+2700
    assert 0<decisions[1]['remaining_episode_wall_seconds']<decisions[0]['remaining_episode_wall_seconds']<=2700
    assert decisions[0]['workspace_fingerprint']['sha256']!=decisions[1]['workspace_fingerprint']['sha256']
    assert [e['workspace_fingerprint']['bytes'] for e in decisions]==[
        len(b'inert workspace seed'),len(b'inert workspace seed')+8*len(b'|inert observation')]
    for decision in decisions:
        assert decision['randomized_logger'] is False
        assert sum(decision['probability_vector'].values())==1.0
        assert set(decision['both_action_reservations'])=={'S','L'}
        assert decision['both_action_reservations']['S']==decision['both_action_reservations']['L']
        assert decision['both_action_reservations']['S']['input_ids']==[11,12,13]
        assert decision['remaining_logical_calls_including_current']==25-decision['logical_call']
        assert decision['workspace_fingerprint']['method']=='sha256_raw_workspace_image'
        assert decision['workspace_fingerprint']['semantic_content_identity'] is False
        assert decision['workspace_fingerprint']['hash_elapsed_seconds']>=0
        assert decision['remaining_episode_wall_seconds']==decision['episode_deadline_monotonic']-decision['measured_at_monotonic']
    requests=[e for e in events if e['event']=='request']
    responses=[e for e in events if e['event']=='response']
    assert [e['physical_calls'] for e in requests]==list(range(1,11))
    assert [e['physical_calls'] for e in responses]==list(range(1,11))
    assert [e['model_action'] for e in responses]==[schedule[0]]*8+[schedule[1]]*2
    counts={'S':0,'L':0}
    for event in responses:
        counts[event['model_action']]+=1
        assert event['per_model_physical_calls']==counts[event['model_action']]
    assert (run/'episode'/'patch.supervisor.json').is_file()
    assert receipt['cleanup_verified'] and receipt['submission_eligible']
    assert (run/'episode'/'patch.diff').read_text()=='authored inert patch\n'


def test_real_launch_workspace_receipt_failure_at_decision9_prevents_ninth_generation(tmp_path,monkeypatch):
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    run,command=full_launch_fixture(tmp_path,'SL','state_unavailable9')
    receipt=guard(run,command,deadlines(load=2,call=1,episode=5,outer=8,cleanup_grace=3))
    assert receipt['status']=='infrastructure_unknown' and not receipt['submission_eligible']
    assert receipt['worker_reaped'] and receipt['cleanup_verified']
    assert receipt['assigned_slot_retained'] and receipt['operational_resolution']==0
    events=[json.loads(line) for line in (run/'episode'/'agent'/'events.jsonl').read_text().splitlines()]
    assert [e['physical_calls'] for e in events if e['event']=='request']==list(range(1,9))
    assert [e['physical_calls'] for e in events if e['event']=='response']==list(range(1,9))
    assert [e['logical_call'] for e in events if e['event']=='routing_decision']==[1]
    assert not (run/'episode'/'patch.diff').exists()


def test_owned_raw_workspace_hash_is_exact_and_overhead_is_measured(tmp_path):
    path=tmp_path/'workspace.img';data=b'authored image bytes'*1200;path.write_bytes(data)
    deadline=time.monotonic()+2700
    state=worker.measure_workspace_decision_state(path,episode_deadline=deadline)
    assert state['workspace_fingerprint']['sha256']==worker.digest_file(path)
    assert state['workspace_fingerprint']['bytes']==len(data)
    assert state['workspace_fingerprint']['hash_elapsed_seconds']>=0
    assert 0<state['remaining_episode_wall_seconds']<2700
    assert state['remaining_episode_wall_seconds']==deadline-state['measured_at_monotonic']
    assert state['workspace_fingerprint']['semantic_content_identity'] is False


@pytest.mark.parametrize('kind',['symlink','fifo','empty','over_cap'])
def test_workspace_hash_rejects_unbounded_or_nonregular_input(tmp_path,kind):
    path=tmp_path/'workspace.img'
    if kind=='symlink':
        target=tmp_path/'target';target.write_bytes(b'owned');path.symlink_to(target)
    elif kind=='fifo':os.mkfifo(path)
    elif kind=='empty':path.write_bytes(b'')
    else:
        with path.open('wb') as file:file.truncate(8*1024**3+1)
    with pytest.raises((OSError,ValueError)):
        worker.measure_workspace_decision_state(path,episode_deadline=time.monotonic()+2700)


def test_workspace_mutation_during_hash_is_rejected(tmp_path,monkeypatch):
    path=tmp_path/'workspace.img';path.write_bytes(b'authored bytes')
    read=worker.os.read;mutated=False
    def mutate(fd,size):
        nonlocal mutated
        data=read(fd,size)
        if data and not mutated:
            mutated=True
            with path.open('ab') as image:image.write(b'changed')
        return data
    monkeypatch.setattr(worker.os,'read',mutate)
    with pytest.raises(ValueError,match='changed'):
        worker.measure_workspace_decision_state(path,episode_deadline=time.monotonic()+2700)


def test_workspace_path_replacement_during_hash_is_rejected(tmp_path,monkeypatch):
    path=tmp_path/'workspace.img';path.write_bytes(b'authored bytes')
    replacement=tmp_path/'replacement.img';replacement.write_bytes(b'authored bytes')
    read=worker.os.read;replaced=False
    def replace(fd,size):
        nonlocal replaced
        data=read(fd,size)
        if data and not replaced:
            replaced=True
            replacement.replace(path)
        return data
    monkeypatch.setattr(worker.os,'read',replace)
    with pytest.raises(ValueError,match='changed'):
        worker.measure_workspace_decision_state(path,episode_deadline=time.monotonic()+2700)


def test_deadline_consumed_by_workspace_hash_produces_time_exceeded_without_submission(tmp_path):
    path=tmp_path/'workspace.img';path.write_bytes(b'authored bytes')
    code='''
import json,sys,types
from pathlib import Path
from experiments.lead_req030.seaborn_runner_qualification import load_pinned_default_agent
load_pinned_default_agent()
from experiments.lead_req030 import req030ai_episode_worker as w
from minisweagent.exceptions import TimeExceeded
clock=iter([1.0,1.1,2.1])
w.time=types.SimpleNamespace(monotonic=lambda:next(clock))
try:w.measure_workspace_decision_state(Path(sys.argv[1]),episode_deadline=2.0)
except TimeExceeded as exc:print(json.dumps(exc.messages[-1]))
else:raise AssertionError('expired hash was accepted')
'''
    proc=subprocess.run([sys.executable,'-c',code,str(path)],cwd=worker.ROOT,capture_output=True,text=True,timeout=10)
    assert proc.returncode==0,proc.stderr
    result=json.loads(proc.stdout)
    assert result['extra']=={'exit_status':'TimeExceeded','submission':''}


def test_harvest_deadline_waits_for_real_supervisor_owner_eof_cleanup(tmp_path,monkeypatch):
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    run,command=full_launch_fixture(tmp_path,'SL','harvest_stall')
    receipt=guard(run,command,deadlines(load=2,call=1,episode=1.5,outer=5,cleanup_grace=6))
    assert receipt['reason']=='episode_deadline', (receipt,(run/'worker.out').read_text())
    assert receipt['status']=='operational_time_limit' and receipt['cleanup_verified']
    sup=json.loads((run/'episode'/'patch.supervisor.json').read_bytes())
    assert sup['reason']=='owner_eof' and sup['error'] is None
    assert_dead(sup['pid'])
    assert not (run/'episode'/'patch.diff').exists()
    assert receipt['operational_resolution']==0 and receipt['assigned_slot_retained']


@pytest.mark.parametrize('mutation',[{'error':'unknown'}, {'elapsed':float('nan')},{'pid':True},
                                    {'extra':'unexpected'},{'returncode':None}])
def test_harvest_receipt_strict_schema_rejects_ambiguous_cleanup(tmp_path,mutation):
    episode=tmp_path/'episode';episode.mkdir()
    (episode/'harvest.sh').write_text('authored marker')
    record={'reason':'exited','pid':123,'returncode':0,'retained_bytes':0,'elapsed':.1,'error':None}|mutation
    (episode/'patch.supervisor.json').write_bytes(worker.canonical(record))
    with pytest.raises(ValueError):worker.tool_receipts_clean(tmp_path,[])


def test_harvest_missing_receipt_is_not_verified_cleanup(tmp_path):
    episode=tmp_path/'episode';episode.mkdir();(episode/'harvest.sh').write_text('authored marker')
    assert not worker.tool_receipts_clean(tmp_path,[])


def test_final_worker_stderr_is_retained(tmp_path,monkeypatch):
    _,run,command=prepare(tmp_path)
    path=Path(command[1]);path.write_text(path.read_text()+"\nprint('FINAL_DIAGNOSTIC',file=sys.stderr,flush=True)\n")
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    result=guard(run,command)
    assert result['status']=='episode_complete'
    assert (run/'worker.out').read_text().endswith('FINAL_DIAGNOSTIC\n')


def test_unreapable_worker_receipt_requires_batch_abort(tmp_path,monkeypatch):
    _,run,command=prepare(tmp_path)
    monkeypatch.setenv('PYTHONPATH',str(worker.ROOT))
    real=worker._terminate_reap
    def forced_unknown(process,limits):
        reaped,killed,error=real(process,limits)
        assert reaped
        return False,killed,'authored_cleanup_failure_fixture'
    monkeypatch.setattr(worker,'_terminate_reap',forced_unknown)
    result=guard(run,command)
    assert result['abort_batch'] and result['status']=='infrastructure_unknown'
    assert result['assigned_slot_retained'] and result['operational_resolution']==0
    assert result['algorithmic_correctness']=='unknown'
    assert not result['submission_eligible']
