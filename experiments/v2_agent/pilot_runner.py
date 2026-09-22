"""DTR-REQ-002 fixed-backend DEVELOPMENT pilot runner: one bounded shared-host block (lead 23b0ddc: PROCEED; option A
served files; REQ-004 slot under the owner's authorization, ICLR explicitly deferred).

Declared before launch (no outcome exists yet):
  * queue = the frozen frame's 8 tasks in position order, each task's two backends in its frozen backend_order
    (16 episodes); nothing is replaced, reordered or stopped on outcomes
  * restart: an episode with a terminal episode.json is skipped (hash recorded); an interrupted run directory is
    retained and requires explicit ledger reconciliation before any execution; a run directory naming another task/backend conflicts
    BEFORE any execution; the whole queue is validated first
  * block: actual start S, hard end S+7200 s. An episode starts only if its full wall allowance (1,800 s + 300 s
    kill margin + 300 s model-switch allowance when the backend changes) ends before S+7200, so the block ends by
    resource/time, never by results; unstarted IDs are preserved for a later block
  * serial serving: at most ONE llama-server (own build, llama.cpp 4fea119) at a time, 127.0.0.1:8291 (7B) or :8293
    (14B), -ngl 99 -np 1 -c 16384; the served file's SHA-256 must equal the option-A conversion record; before every
    start the host must have no llama-server/mlx/ollama process that this runner did not start; a server is stopped
    only if the port's listener PID equals the PID this runner recorded (ownership by PORT + record)
  * per-model preflight on first load in the block: load time, RSS, swap, /props (n_ctx, slots), /apply-template,
    one fixed non-task probe (512 generated tokens, T=0) and one long-prompt probe (~12k tokens) for throughput;
    fit failures are recorded, never substituted
  * grading is NOT done in the block (CPU-only, after release) by grade_submission.py
  work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/pilot_runner.py --cohort yaml-v1 --block 1 [--dry-run]
"""
from __future__ import annotations
import argparse, hashlib, json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace_capture as WC  # noqa: E402
import pilot_cohort as PC  # noqa: E402

FRAME = ROOT / 'results/v2_agent/pilot_frame_20260922.json'
CONV = ROOT / 'results/v2_agent/coder_conversion_20260922.json'
OUT = ROOT / 'results/v2_agent/pilot_20260922'
SERVERS = ROOT / 'work/code_routing_servers.json'
LLAMA_SERVER = ROOT / 'work/upstream/llama.cpp-4fea119/build/bin/llama-server'
MSWEA_PY = ROOT / 'work/venvs/minisweagent_04d809c/bin/python'
EPISODE = Path(__file__).resolve().parent / 'pilot_episode.py'
PORTS = dict(small=8291, large=8293)
ALIAS = dict(small='qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m', large='qwen2.5-coder-14b-instruct-aedcc2d-q4_k_m')
BLOCK_CAP, EPISODE_WALL, KILL_MARGIN, SWITCH_ALLOWANCE = 7200, 1800, 300, 300
CHILD_CLEANUP_GRACE, SERVER_CLEANUP_RESERVE = 120, 90
MAX_PHYSICAL_TOTAL = 768
FOREIGN = ('llama-server', 'mlx_lm', 'ollama')
HARNESS_PIN = '04d809ceab9df28f9adaed044884180159172930'
DEFAULT_YAML_PIN = '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f'
FROZEN_SETTINGS = dict(step_limit=24, cost_limit=0.0, wall_time_limit_seconds=1800, temperature=0.0, max_tokens=1536,
                       command_timeout_s=60, physical_attempts_per_call_max=2, request_timeout_s=900)


class Conflict(RuntimeError):
    pass


class DeadlineReached(TimeoutError):
    pass


def remaining(deadline, limit=None):
    left = deadline - time.time()
    if left <= 0:
        raise DeadlineReached('absolute work deadline reached; releasing the shared host')
    return left if limit is None else min(left, limit)


def request_count(rec):
    count = rec.get('physical_requests')
    if count is None:
        return 48                         # unknown consumption retains the full episode reservation
    if type(count) is not int or not 0 <= count <= 48:
        raise Conflict('invalid physical_requests %r; reconcile the ledger before execution' % count)
    return count


def sha_file(p, bs=1 << 24):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(bs), b''):
            h.update(b)
    return h.hexdigest()


def utc(t=None):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


def episode_queue(frame):
    q = []
    for t in sorted(frame['pilot']['tasks'], key=lambda t: t['position']):
        for k, be in enumerate(t['backend_order']):
            q.append(dict(position=t['position'], order=k + 1, instance_id=t['instance_id'], backend=be, image=t['instance_image']))
    return q


def episode_state(out, item, expected_models=None, expected_binding=None, expected_episode_source=None):
    """completed (terminal episode.json) | incomplete (run dir(s) without one) | new; conflicts raise."""
    prefix = '%s__%s__' % (item['instance_id'], item['backend'])
    dirs = sorted(d for d in Path(out).glob(prefix + '*') if d.is_dir()) if Path(out).exists() else []
    done, partial = None, []
    for d in dirs:
        e = d / 'episode.json'
        if not e.exists():
            partial.append(d.name)
            continue
        raw = e.read_bytes()
        try:
            rec = json.loads(raw)
        except ValueError:
            raise Conflict('unparsable %s' % e)
        if rec.get('instance_id') != item['instance_id'] or rec.get('backend') != item['backend'] or rec.get('run_id') != d.name:
            raise Conflict('%s names %s/%s/%s' % (e, rec.get('instance_id'), rec.get('backend'), rec.get('run_id')))
        if not rec.get('exit_status'):
            raise Conflict('%s has no exit_status' % e)
        if expected_models is not None and (rec.get('pins', {}).get('image_id') != item['image'] or
                rec.get('served', {}).get('model_sha256') != expected_models[item['backend']]):
            raise Conflict('%s has missing/conflicting frozen image or served-model identity; reconcile before reuse' % e)
        if expected_models is not None and (
                rec.get('pins', {}).get('mini_swe_agent') != HARNESS_PIN or
                rec.get('pins', {}).get('default_yaml_sha256') != DEFAULT_YAML_PIN or
                rec.get('workspace_binding') != 'wc2' or rec.get('template_platform_binding') != 'cp2' or
                any(rec.get('settings', {}).get(k) != v for k, v in FROZEN_SETTINGS.items())):
            raise Conflict('%s has missing/conflicting frozen harness/settings/binding identity; reconcile before reuse' % e)
        if expected_binding is not None:
            try:
                PC.validate_effective_receipt(d, rec, expected_binding, expected_episode_source)
            except ValueError as exc:
                raise Conflict('%s: %s' % (e, exc)) from exc
        if done is not None:
            raise Conflict('two terminal episodes for %s/%s: %s and %s' % (item['instance_id'], item['backend'], done[0], d.name))
        done = (d.name, hashlib.sha256(raw).hexdigest(), rec)
    if done:
        request_count(done[2])
        return 'completed', done, partial
    return ('incomplete' if partial else 'new'), None, partial


def plan_start(now, block_start, switching, cap=BLOCK_CAP, wall=EPISODE_WALL, margin=KILL_MARGIN, switch=SWITCH_ALLOWANCE):
    """True iff the episode's full allowance ends before the hard block end (time-based, never outcome-based)."""
    return now + wall + margin + (switch if switching else 0) <= block_start + cap


def run_block(queue, out, serve, run_episode, status, clock=time.time, block_start=None, pause=None, physical_so_far=0,
              expected_models=None, expected_binding=None, expected_episode_source=None):
    """serve(backend) makes that backend the ONE live server (stopping the other); run_episode(item) returns the
    terminal record. Every task state is validated before any execution."""
    block_start = clock() if block_start is None else block_start
    states = [(it, episode_state(out, it, expected_models, expected_binding, expected_episode_source)) for it in queue]
    incomplete = [dict(instance_id=it['instance_id'], backend=it['backend'], run_dirs=state[2])
                  for it, state in states if state[2]]
    if incomplete:
        raise Conflict('interrupted run directories need explicit ledger reconciliation; no automatic episode rerun: %s' % incomplete)
    if type(physical_so_far) is not int or physical_so_far < 0:
        raise Conflict('invalid prior request accounting')
    physical = physical_so_far + sum(request_count(done[2]) for _, (state, done, _) in states if state == 'completed')
    if physical > MAX_PHYSICAL_TOTAL:
        raise Conflict('whole-cohort request accounting exceeds the declared ceiling or is invalid')
    status.update(block_start_utc=utc(block_start), block_hard_end_utc=utc(block_start + BLOCK_CAP), skipped_completed=[],
                  retained_incomplete=[], ran=[], unstarted=[], stopped=None)
    current = None
    for i, (it, (state, done, partial)) in enumerate(states):
        key = dict(position=it['position'], order=it['order'], instance_id=it['instance_id'], backend=it['backend'])
        if state == 'completed':
            status['skipped_completed'].append(dict(key, run_id=done[0], episode_sha256=done[1]))
            continue
        reason = None
        if pause is not None and Path(pause).exists():
            reason = 'paused (shared-host coordination)'
        elif not plan_start(clock(), block_start, it['backend'] != current):
            reason = 'block time cap: full episode allowance would pass S+%d s' % BLOCK_CAP
        elif physical + 48 > MAX_PHYSICAL_TOTAL:
            reason = 'all-episode physical request ceiling %d' % MAX_PHYSICAL_TOTAL
        if reason:
            status['stopped'] = reason
            status['unstarted'] = [dict(position=x['position'], order=x['order'], instance_id=x['instance_id'], backend=x['backend'])
                                   for x, (s, _, _) in states[i:] if s != 'completed']
            break
        if partial:
            status['retained_incomplete'].append(dict(key, run_dirs=partial))
        if it['backend'] != current:
            serve(it['backend'])
            current = it['backend']
        if not plan_start(clock(), block_start, False):
            status['stopped'] = 'block time cap after setup: full episode plus cleanup reserve no longer fits'
            status['unstarted'] = [dict(position=x['position'], order=x['order'], instance_id=x['instance_id'], backend=x['backend'])
                                   for x, (s, _, _) in states[i:] if s != 'completed']
            break
        rec = run_episode(it)
        physical += request_count(rec)
        status['ran'].append(dict(key, run_id=rec.get('run_id'), exit_status=rec.get('exit_status'), wall_seconds=rec.get('wall_seconds'),
                                  physical_requests=rec.get('physical_requests')))
    status['physical_requests_total'] = physical
    status['block_end_utc'] = utc(clock())
    return status


# ---------------------------------------------------------------- host / server side (not used by the unit tests)

def host_processes():
    p = subprocess.run(['ps', '-axo', 'pid=,comm=,args='], capture_output=True, text=True)
    rows = []
    for line in p.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) >= 2 and any(f in (parts[1] + ' ' + (parts[2] if len(parts) > 2 else '')) for f in FOREIGN):
            rows.append(dict(pid=int(parts[0]), comm=Path(parts[1]).name))
    return [r for r in rows if r['comm'] != 'grep']


def listener_pid(port):
    p = subprocess.run(['lsof', '-nP', '-iTCP:%d' % port, '-sTCP:LISTEN', '-t'], capture_output=True, text=True)
    pids = [int(x) for x in p.stdout.split()]
    return pids[0] if len(pids) == 1 else (None if not pids else pids)


def swap_used():
    return subprocess.run(['sysctl', '-n', 'vm.swapusage'], capture_output=True, text=True).stdout.strip()


def rss_kb(pid):
    out = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) if out else None


class Servers:
    """Serial single-server manager with a published ownership record."""

    def __init__(self, conv, block, log_dir):
        self.conv, self.block, self.log_dir = conv, block, Path(log_dir)
        self.live = None            # dict(backend, pid, port, proc)
        self.events = []
        self.unconfirmed_episode_pids = []
        self.unconfirmed_container_runs = []
        self.hard_deadline = block['hard_deadline_epoch']
        self.work_deadline = self.hard_deadline - KILL_MARGIN

    def _record(self):
        rec = dict(holder='DTR-AgentEvals worker (REQ-002 pilot)', block=self.block, block_start_utc=self.block['block_start_utc'],
                   block_hard_end_utc=self.block['block_hard_end_utc'],
                   servers=[] if not self.live else [dict(role=self.live['backend'], pid=self.live['pid'], port=self.live['port'],
                                                          alias=ALIAS[self.live['backend']], model_file=self.live['model_file'],
                                                          model_sha256=self.live['model_sha256'], started_utc=self.live['started_utc'],
                                                          cmd=self.live['cmd'])],
                   unconfirmed_episode_pids=self.unconfirmed_episode_pids, unconfirmed_container_runs=self.unconfirmed_container_runs,
                   release_confirmed=self.live is None and not self.unconfirmed_episode_pids and not self.unconfirmed_container_runs,
                   events=self.events)
        tmp = SERVERS.with_suffix('.tmp')
        tmp.write_text(json.dumps(rec, indent=1) + '\n')
        os.replace(tmp, SERVERS)

    def stop(self):
        if not self.live:
            return
        pid, port = self.live['pid'], self.live['port']
        if self.live['proc'].poll() is not None:
            self.live = None
            self._record()
            return
        lp = listener_pid(port)
        if lp not in (pid, None):
            raise Conflict('port %d listener is %r, not our recorded PID %d: refusing to signal' % (port, lp, pid))
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.live['proc'].wait(timeout=max(0, min(60, self.hard_deadline - time.time())))
        except subprocess.TimeoutExpired:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                self.live['proc'].wait(timeout=max(0, min(30, self.hard_deadline - time.time())))
            except subprocess.TimeoutExpired:
                pass                      # SIGKILL sent; never wait beyond the block hard end
        if self.live['proc'].poll() is None:
            self.events.append(dict(event='termination_unconfirmed', role=self.live['backend'], pid=pid, port=port, utc=utc()))
            self._record()                # retain ownership; a sent signal is not confirmation of exit
            raise Conflict('server PID %d termination remains unconfirmed; ownership retained' % pid)
        self.events.append(dict(event='stopped', role=self.live['backend'], pid=pid, port=port, utc=utc()))
        self.live = None
        self._record()

    def serve(self, backend):
        import requests
        remaining(self.work_deadline)
        self.stop()
        foreign = [p for p in host_processes()]
        if foreign:
            raise Conflict('non-DTR accelerator processes present, not starting: %s' % foreign)
        port = PORTS[backend]
        if listener_pid(port) is not None:
            raise Conflict('port %d already has a listener' % port)
        be = self.conv['backends'][backend]
        model = ROOT / be['q4_k_m']['file']
        cmd = [str(LLAMA_SERVER), '-m', str(model), '--alias', ALIAS[backend], '--host', '127.0.0.1', '--port', str(port),
               '-ngl', '99', '-np', '1', '-c', '16384']
        t0 = time.time()
        got = sha_file(model)
        remaining(self.work_deadline)
        if got != be['q4_k_m']['sha256']:
            raise Conflict('served file hash %s != conversion record %s' % (got, be['q4_k_m']['sha256']))
        swap0 = swap_used()
        log = open(self.log_dir / ('server_%s_%s.log' % (backend, utc().replace(':', ''))), 'x')
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.live = dict(backend=backend, pid=proc.pid, port=port, proc=proc, model_file=model.name, model_sha256=got,
                         started_utc=utc(t0), cmd=' '.join(c.replace(str(ROOT) + '/', '') for c in cmd))
        self._record()
        t1 = time.time()
        ok = False
        while time.time() - t1 < 600:
            remaining(self.work_deadline)
            if proc.poll() is not None:
                break
            try:
                if requests.get('http://127.0.0.1:%d/health' % port, timeout=remaining(self.work_deadline, 5)).status_code == 200:
                    ok = True
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        ev = dict(event='started' if ok else 'load_failed', role=backend, pid=proc.pid, port=port, hash_seconds=round(t1 - t0, 1),
                  load_seconds=round(time.time() - t1, 1), rss_kb=rss_kb(proc.pid), swap_before=swap0, swap_after=swap_used(), utc=utc())
        self.events.append(ev)
        self._record()
        if not ok:
            raise Conflict('server %s failed to load (exit %s): recorded as a fit/load failure' % (backend, proc.poll()))
        return ev


def preflight(backend, ev, out, deadline, block):
    """Measured non-task probes on the freshly loaded server; write-once per backend."""
    import requests
    p = Path(out) / ('preflight_%s_block%d.json' % (backend, block['block']))
    if p.exists():
        raise Conflict('preflight receipt already exists for this block: %s' % p)
    base = 'http://127.0.0.1:%d' % PORTS[backend]
    props = requests.get(base + '/props', timeout=remaining(deadline, 10)).json()
    tmpl = requests.post(base + '/apply-template', json=dict(messages=[dict(role='user', content='hello')]), timeout=remaining(deadline, 30)).json()
    probes = {}
    long_text = ' '.join('line %d: the quick brown fox jumps over the lazy dog.' % i for i in range(1000))   # ~12k tokens
    for name, content, n in (('short_gen', 'Write a Python function that returns the n-th Fibonacci number, with a docstring.', 512),
                             ('long_prompt', long_text + '\nHow many lines are above? Answer with one number.', 32)):
        t0 = time.time()
        r = requests.post(base + '/v1/chat/completions', json=dict(model=ALIAS[backend], messages=[dict(role='user', content=content)],
                                                                   temperature=0, max_tokens=n), timeout=remaining(deadline, 900))
        j = r.json()
        probes[name] = dict(http=r.status_code, wall_seconds=round(time.time() - t0, 2), usage=j.get('usage'), timings=j.get('timings'),
                            finish_reason=(j.get('choices') or [{}])[0].get('finish_reason'))
    pid = ev['pid']
    rec = dict(request='DTR-REQ-002', backend=backend, block=block['block'], alias=ALIAS[backend], utc=utc(), load=ev, rss_kb_after_probes=rss_kb(pid),
               swap_after_probes=swap_used(), n_ctx_per_slot=props.get('default_generation_settings', {}).get('n_ctx'),
               total_slots=props.get('total_slots'), model_file=Path(props.get('model_path') or '').name,
               chat_template_applies=bool(tmpl.get('prompt')), probes=probes,
               non_task_probe_requests=len(probes), probe_accounting='separate from the 768 episode-request ceiling',
               fits_declared_limits=props.get('default_generation_settings', {}).get('n_ctx') == 16384 and props.get('total_slots') == 1
               and all(v['http'] == 200 for v in probes.values()),
               note='non-task probes only; throughput is descriptive, not a native-performance claim')
    with open(p, 'x') as fh:
        fh.write(json.dumps(rec, indent=1) + '\n')
    return rec


def make_episode_runner(out, servers, verify_source=None):
    def run(item):
        if verify_source is not None:
            verify_source()
        if remaining(servers.work_deadline) < EPISODE_WALL:
            raise DeadlineReached('full episode allowance no longer fits after setup')
        run_id, run_dir = WC.new_run_dir(out, item['instance_id'], item['backend'], 'pilot-cp2-wc2-yaml-v1')
        live = servers.live
        served = dict(model_file=live['model_file'], model_sha256=live['model_sha256'], server_pid=live['pid'],
                      server_started_utc=live['started_utc'], llama_cpp='4fea119de30f6a923992780f6fd5ccb0bee5d47d')
        cmd = [str(MSWEA_PY), str(EPISODE), '--instance', item['instance_id'], '--backend', item['backend'], '--port', str(PORTS[item['backend']]),
               '--alias', ALIAS[item['backend']], '--run-dir', str(run_dir), '--run-id', run_id, '--expected-image', item['image'],
               '--served', json.dumps(served), '--episode-deadline', str(time.time() + EPISODE_WALL),
               '--block-deadline', str(servers.work_deadline)]
        log = open(run_dir / 'runner_stdout.txt', 'x')
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        servers.unconfirmed_episode_pids.append(proc.pid)
        servers.unconfirmed_container_runs.append(run_id)
        wall_timeout = False
        try:
            proc.wait(timeout=min(EPISODE_WALL, remaining(servers.work_deadline)))
        except (subprocess.TimeoutExpired, DeadlineReached):
            wall_timeout = True
            if proc.poll() is None:
                # Its absolute alarm has ended inference; do not interrupt cleanup with a duplicate alarm.
                grace = max(0, min(CHILD_CLEANUP_GRACE, servers.hard_deadline - time.time() - SERVER_CLEANUP_RESERVE))
                try:
                    proc.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=max(0, min(30, servers.hard_deadline - time.time() - SERVER_CLEANUP_RESERVE)))
                except subprocess.TimeoutExpired:
                    pass
        confirmed = proc.poll() is not None
        if confirmed:
            servers.unconfirmed_episode_pids.remove(proc.pid)
        WC.write_once(run_dir / 'runner_cleanup.json', json.dumps(dict(pid=proc.pid, wall_timeout=wall_timeout,
                       termination_confirmed=confirmed, utc=utc())) + '\n')
        if not confirmed:
            servers.events.append(dict(event='episode_termination_unconfirmed', pid=proc.pid, run_id=run_id, utc=utc()))
        ownership_path, cleanup_path = run_dir / 'container_ownership.json', run_dir / 'container_cleanup.json'
        def receipt(path):
            try:
                value = json.loads(path.read_text())
                return value if isinstance(value, dict) else {}
            except (OSError, ValueError):
                return {}
        ownership = receipt(ownership_path)
        owned_id = ownership.get('container_id') if ownership.get('run_id') == run_id else None
        container_cleanup = receipt(cleanup_path)
        if not (owned_id and container_cleanup.get('container_id') == owned_id and container_cleanup.get('confirmed') is True):
            from pilot_episode import cleanup_owned_container
            container_cleanup = cleanup_owned_container(owned_id, servers.hard_deadline - SERVER_CLEANUP_RESERVE)
            WC.write_once(run_dir / 'runner_container_cleanup.json', json.dumps(container_cleanup) + '\n')
        if container_cleanup.get('confirmed') is not True:
            servers.events.append(dict(event='container_termination_unconfirmed', run_id=run_id, container_id=owned_id, utc=utc()))
        else:
            servers.unconfirmed_container_runs.remove(run_id)
        e = run_dir / 'episode.json'
        if not e.exists():   # hard kill or crash: durable terminal record, empty submission (budget/infrastructure exit)
            submission = run_dir / 'submission.diff'
            if not submission.exists():
                WC.write_once(submission, '')
            rec = dict(kind='runner terminal record (episode process produced no episode.json)', instance_id=item['instance_id'],
                       backend=item['backend'], backend_alias=ALIAS[item['backend']], run_id=run_id, served=served,
                       pins=dict(image_id=item['image'], mini_swe_agent=HARNESS_PIN, default_yaml_sha256=DEFAULT_YAML_PIN),
                       settings=dict(FROZEN_SETTINGS), workspace_binding='wc2', template_platform_binding='cp2',
                       configuration_binding='yaml-v1', effective_config_status='unavailable; reconciliation required',
                       episode_source_sha256=sha_file(EPISODE),
                       contract_scope='declared invocation; child produced no observed episode record',
                       exit_status='EpisodeWallLimit' if wall_timeout else
                       ('RunnerHardKill' if proc.returncode in (-9, None) else 'EpisodeProcessError'),
                       returncode=proc.returncode, infrastructure_suspect=True, submission_sha256=sha_file(submission),
                       submission_bytes=submission.stat().st_size, submission_empty=not submission.read_text().strip(), physical_requests=None,
                       request_accounting='unknown terminal reserves 48; durable attempts retained for reconciliation',
                       container_cleanup=container_cleanup)
            WC.write_once(e, json.dumps(rec, indent=1) + '\n')
        if not confirmed:
            raise Conflict('episode PID %d termination unconfirmed; no subsequent episode permitted' % proc.pid)
        if container_cleanup.get('confirmed') is not True:
            raise Conflict('episode container cleanup unconfirmed; no subsequent episode permitted')
        return json.loads(e.read_text())
    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--block', type=int, required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--cohort', choices=tuple(PC.COHORTS), required=True)
    args = ap.parse_args()
    if not args.dry_run and args.cohort != 'yaml-v1':
        ap.error('legacy cohort is read-only; never execute the repaired driver in its namespace')
    out = PC.cohort_output(args.cohort)
    frame = json.loads(FRAME.read_text())
    queue = episode_queue(frame)
    if args.dry_run:
        for it in queue:
            print(it['position'], it['order'], it['instance_id'], it['backend'], episode_state(out, it)[0])
        return
    PC.validate_amendment(FRAME, CONV)
    from pilot_episode import CONFIGURATION_BINDING
    if CONFIGURATION_BINDING != args.cohort:
        raise Conflict('runner/episode configuration binding mismatch')
    conv = json.loads(CONV.read_text())
    out.mkdir(parents=True, exist_ok=True)
    source_binding = PC.freeze_source_binding(out)
    bpath = out / ('block_%d.json' % args.block)
    if bpath.exists():
        raise SystemExit('block %d already recorded' % args.block)
    status = dict(block=args.block, cohort=args.cohort, frame_sha256=sha_file(FRAME), conversion_record_sha256=sha_file(CONV),
                  amendment_sha256=sha_file(PC.AMENDMENT), runner_source_sha256=sha_file(Path(__file__)),
                  episode_source_sha256=sha_file(EPISODE))
    S = time.time()
    block = dict(block=args.block, block_start_utc=utc(S), block_hard_end_utc=utc(S + BLOCK_CAP), hard_deadline_epoch=S + BLOCK_CAP)
    servers = Servers(conv, block, out)
    done_pre = set()

    def serve(backend):
        PC.freeze_source_binding(out)
        ev = servers.serve(backend)
        if backend not in done_pre:
            receipt = preflight(backend, ev, out, servers.work_deadline, block)
            fits = receipt['fits_declared_limits']
            status.setdefault('preflight', {})[backend] = fits
            status['non_task_probe_requests'] = status.get('non_task_probe_requests', 0) + receipt['non_task_probe_requests']
            done_pre.add(backend)
            if not fits:
                raise Conflict('%s preflight does not fit the declared limits: recorded, no episode on this backend' % backend)
    def alarm(_signum, _frame):
        raise DeadlineReached('block work deadline reached; cleanup reserve begins')
    old_handler = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, remaining(servers.work_deadline))
    try:
        run_block(queue, out, serve, make_episode_runner(out, servers, lambda: PC.freeze_source_binding(out)), status, block_start=S, pause=out / 'PAUSE',
                  expected_models={be: conv['backends'][be]['q4_k_m']['sha256'] for be in PORTS}, expected_binding=args.cohort,
                  expected_episode_source=source_binding['sources']['pilot_episode.py'])
    except Exception as e:  # noqa: BLE001  recorded; the block still releases its own server
        status['stopped'] = 'error: %s: %s' % (type(e).__name__, str(e)[:500])
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            servers.stop()
        except Exception as e:
            status['cleanup_error'] = '%s: %s' % (type(e).__name__, str(e)[:500])
        finally:
            signal.signal(signal.SIGALRM, old_handler)
        status['server_events'] = servers.events
        status['unconfirmed_episode_pids'] = servers.unconfirmed_episode_pids
        status['unconfirmed_container_runs'] = servers.unconfirmed_container_runs
        status['released_utc'] = utc() if servers.live is None and not servers.unconfirmed_episode_pids and not servers.unconfirmed_container_runs else None
        with open(bpath, 'x') as fh:
            fh.write(json.dumps(status, indent=1) + '\n')
    print(json.dumps({k: status.get(k) for k in ('stopped', 'physical_requests_total', 'released_utc')}))


if __name__ == '__main__':
    main()
