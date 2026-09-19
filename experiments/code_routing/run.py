"""Runner for the code-routing study.

  python run.py --servers start|stop      llama-server for both models (frozen flags)
  python run.py --stage tests             environment construction: frozen visible tests, once per task
  python run.py --stage pilot             pilot tasks only (disjoint from train/confirm); runs BEFORE the design freeze
  python run.py --stage log               sequentially randomized log (frozen design), resumable
  python run.py --stage live              fresh executions of the frozen target policies on confirm tasks
  python run.py --stage branch            restored-prefix branch audit (plan frozen on first invocation)
  add --mock to dry-run any stage without a model (writes under work/, never under results/)

Integrity rules enforced here
  * every routing decision (state, propensity, draw, action) is appended and fsync'ed to decisions.jsonl BEFORE the model
    is invoked, tagged with the invocation id and attempt number;
  * an episode whose record carries `error` is NOT done: a plain re-run retries it with the SAME pre-drawn uniforms and
    seed, up to max_attempts_per_episode; analysis keeps the last successful attempt, else scores it intention-to-treat;
  * a stage refuses to start unless its upstream stage is complete, the task file matches the design's sha256, config /
    visible-test hashes match earlier invocations of the stage, and no other invocation holds the stage lock;
  * a torn final line (kill mid-append) is tolerated and reported, never silently parsed.
GPU courtesy: refuses to start, and yields before every episode, while ANOTHER llama-server on this host is generating
(a sibling project's local coding experiments use latency as an outcome), unless --allow-contention; then each episode
records whether foreign load was actually present when it began.
"""
from __future__ import annotations
import argparse, atexit, json, os, signal, subprocess, sys, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests

from common import RESULTS, ROOT, code_sha256, git_head, load_config, load_tasks, now_iso, resolve, sha256_bytes
from agent import (LlamaServerModel, MockModel, canonical_tests, certified_tests, extract_tests_text, restore_first_failure_prefix, run_episode,
                   tests_prompt)
import policies as P

LLAMA_BINS = [os.environ.get('LLAMA_SERVER', ''), str(ROOT / 'work' / 'llama.cpp' / 'build' / 'bin' / 'llama-server')]
PIDFILE = ROOT / 'work' / 'code_routing_servers.json'
P_ARMS = ('small', 'large')


def read_jsonl(path) -> tuple:
    """(records, n_torn). A final line that does not parse is a torn append; anything else unparsable is fatal."""
    if not path.exists():
        return [], 0
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    out = []
    for i, l in enumerate(lines):
        try:
            out.append(json.loads(l))
        except ValueError:
            if i == len(lines) - 1:
                return out, 1
            raise SystemExit('%s: unparsable line %d (not the last line) - refusing to guess' % (path, i + 1))
    return out, 0


def foreign_busy_servers(own_ports: set):
    """Ports of other llama-servers that are generating. None if the check itself failed (caller decides)."""
    busy = []
    try:
        out = subprocess.run(['/usr/sbin/lsof', '-nP', '-iTCP', '-sTCP:LISTEN'], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if not line.startswith('llama-ser'):
            continue
        try:
            port = int(line.split(':')[-1].split()[0])
        except ValueError:
            continue
        if port in own_ports:
            continue
        try:
            if any(s.get('is_processing') for s in requests.get('http://127.0.0.1:%d/slots' % port, timeout=5).json()):
                busy.append(port)
        except Exception:
            busy.append(port)
    return busy


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False


def servers(action: str, cfg: dict):
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    known = json.loads(PIDFILE.read_text()) if PIDFILE.exists() else []
    if action == 'stop':
        for s in known:
            if _alive(s['pid']):
                os.kill(s['pid'], signal.SIGTERM); print('stopped', s['alias'], s['pid'])
        if PIDFILE.exists():
            PIDFILE.unlink()
        return
    if any(_alive(s['pid']) for s in known):
        raise SystemExit('servers from %s are still running; stop them first' % PIDFILE)
    binp = next((b for b in LLAMA_BINS if b and os.path.exists(b)), None)
    if not binp:
        raise SystemExit('llama-server binary not found; set LLAMA_SERVER')
    started = []
    for role, m in cfg['models'].items():
        gg = resolve(m['gguf']); log = open(ROOT / 'work' / ('llama_%s.log' % role), 'ab')
        cmd = [binp, '-m', gg, '--alias', m['alias'], '--port', str(m['port'])] + cfg['llama_server_flags']
        p = subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)
        started.append(dict(role=role, alias=m['alias'], pid=p.pid, port=m['port'], cmd=cmd, gguf=gg, gguf_bytes=os.path.getsize(gg)))
    PIDFILE.write_text(json.dumps(started, indent=1))
    for s in started:
        for _ in range(240):
            try:
                if requests.get('http://127.0.0.1:%d/health' % s['port'], timeout=3).json().get('status') == 'ok':
                    print('ready', s['alias'], s['port']); break
            except Exception:
                pass
            time.sleep(1)
        else:
            raise SystemExit('server %s not healthy; see work/llama_%s.log' % (s['alias'], s['role']))


def gguf_digests(cfg: dict) -> dict:
    cache = ROOT / 'work' / 'gguf_sha256.json'
    known = json.loads(cache.read_text()) if cache.exists() else {}
    import glob, hashlib
    out = {}
    for role, m in cfg['models'].items():
        first = resolve(m['gguf'])
        for f in sorted(glob.glob(first.replace('-00001-of-', '-0000?-of-'))) or [first]:
            k = '%s|%d' % (f, os.path.getsize(f))
            if k not in known:
                h = hashlib.sha256()
                with open(f, 'rb') as fh:
                    for chunk in iter(lambda: fh.read(1 << 24), b''):
                        h.update(chunk)
                known[k] = h.hexdigest()
            out.setdefault(role, []).append(dict(file=os.path.basename(f), bytes=os.path.getsize(f), sha256=known[k]))
    cache.write_text(json.dumps(known, indent=1))
    return out


def server_facts(cfg: dict) -> dict:
    """What the servers ACTUALLY serve (alias, slots, per-slot context), for the manifest."""
    out = {}
    for role, m in cfg['models'].items():
        try:
            pr = requests.get('http://127.0.0.1:%d/props' % m['port'], timeout=10).json()
            out[role] = dict(total_slots=pr.get('total_slots'), n_ctx_per_slot=(pr.get('default_generation_settings') or {}).get('n_ctx'),
                             model_path=os.path.basename(str(pr.get('model_path', ''))), build=pr.get('build_info'))
        except Exception as e:
            out[role] = dict(error=repr(e)[:200])
    return out


def resolved_ids(path, max_attempts: int):
    """episode ids that are finished: a non-error record exists, or max_attempts error records exist (unresolved, ITT)."""
    recs, torn = read_jsonl(path)
    ok = {r['episode_id'] for r in recs if not r.get('error')}
    n_err = {}
    for r in recs:
        if r.get('error'):
            n_err[r['episode_id']] = n_err.get(r['episode_id'], 0) + 1
    exhausted = {e for e, k in n_err.items() if k >= max_attempts and e not in ok}
    return ok, exhausted, n_err, torn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--servers', choices=['start', 'stop'])
    ap.add_argument('--stage', choices=['tests', 'pilot', 'log', 'live', 'branch'])
    ap.add_argument('--mock', action='store_true')
    ap.add_argument('--limit', type=int, help='cap the number of episodes started by THIS invocation (never allowed for --stage tests)')
    ap.add_argument('--pilot-runs', type=int, default=4)
    ap.add_argument('--allow-contention', action='store_true')
    ap.add_argument('--allow-code-change', action='store_true', help='resume although code_sha256 differs from earlier invocations (recorded)')
    a = ap.parse_args()
    cfg = load_config()
    own = {m['port'] for m in cfg['models'].values()}
    if not a.mock and a.servers != 'stop':
        busy = foreign_busy_servers(own)
        if busy and not a.allow_contention:
            raise SystemExit("REFUSING: another llama-server is generating on port(s) %s; running now would disturb that "
                             "experiment's timing. Retry later or pass --allow-contention (it is recorded)." % busy)
    if a.servers:
        return servers(a.servers, cfg)
    if not a.stage:
        ap.error('--stage or --servers required')
    if a.stage == 'tests' and a.limit and not a.mock:
        raise SystemExit('--limit is not allowed for the tests stage: a partial visible_tests.json would silently drop tasks downstream')

    task_list = load_tasks(cfg); tasks = {t['uid']: t for t in task_list}
    base = (ROOT / 'work' / 'code_routing_mock') if a.mock else RESULTS
    base.mkdir(parents=True, exist_ok=True)
    import design as D
    if a.mock:
        models = dict(small=MockModel('small', tasks, 0.55), large=MockModel('large', tasks, 0.75))
        design = D.build(cfg, task_list)
    else:
        models = {r: LlamaServerModel(r, m['alias'], m['port'], cfg) for r, m in cfg['models'].items()}
        for r, m in models.items():
            if m.alias not in m.served_ids():
                raise SystemExit('server for %s does not serve alias %s' % (r, m.alias))
        if (RESULTS / 'design.json').exists():
            raw = (RESULTS / 'design.json').read_bytes()
            if sha256_bytes(raw) != (RESULTS / 'design.sha256').read_text().strip():
                raise SystemExit('design.json does not match design.sha256')
            design = json.loads(raw)
            if design['config_sha256'] != cfg['_config_sha256']:
                raise SystemExit('config.json changed since the design was frozen')
        elif a.stage in ('tests', 'pilot'):
            design = D.build(cfg, task_list)      # pilot task ids depend only on design_seed / n_pilot_tasks
        else:
            raise SystemExit('freeze the design (design.py) and push it before --stage %s' % a.stage)
    if design['tasks_sha256'] != task_list[0]['_tasks_sha256']:
        raise SystemExit('task file sha256 %s differs from the design (%s): prompts or hidden tests changed' % (task_list[0]['_tasks_sha256'], design['tasks_sha256']))
    invocation = uuid.uuid4().hex[:12]
    stamp = dict(config_sha256=cfg['_config_sha256'], code_sha256=code_sha256(), git_head=git_head(), mock=bool(a.mock),
                 contention_allowed=bool(a.allow_contention), tasks_sha256=task_list[0]['_tasks_sha256'], invocation=invocation)

    # ------------------------------------------------------------- stage: frozen visible tests
    vt_path = base / 'visible_tests.json'
    if a.stage == 'tests':
        if vt_path.exists():
            raise SystemExit('%s exists; visible tests are part of the frozen environment' % vt_path)
        w = cfg['visible_tests']; writer = models[w['writer']]; out = {}

        def one(uid):
            kw = dict(task_uid=uid, kind='tests') if a.mock else {}
            r = writer.chat(tests_prompt(tasks[uid]), w['seed'], temperature=w['temperature'], max_tokens=w['max_tokens'], **kw)
            return uid, dict(raw_reply=r['text'], tests=extract_tests_text(r['text']), completion_tokens=r['completion_tokens'], finish=r['finish'])
        with ThreadPoolExecutor(cfg['workers']) as ex:
            for uid, rec in ex.map(one, sorted(tasks)):      # any failed request aborts BEFORE anything is written
                out[uid] = rec
        if set(out) != set(tasks):
            raise SystemExit('visible tests incomplete: %d of %d' % (len(out), len(tasks)))

        def certify(uid):
            return uid, certified_tests(tasks[uid], canonical_tests(out[uid]['tests'], tasks[uid].get('entry_point')), cfg)
        with ThreadPoolExecutor(cfg['workers']) as ex:
            for uid, cert in ex.map(certify, sorted(tasks)):
                out[uid]['certified'] = cert
        vt_path.write_text(json.dumps(dict(writer=writer.alias, settings=w, created_utc=now_iso(), **stamp, tests=out), indent=0))
        nw = sum(r['certified']['n_written'] for r in out.values()); nk = sum(r['certified']['n_checks'] for r in out.values())
        print('visible tests for %d tasks -> %s (sha256 %s)' % (len(out), vt_path, sha256_bytes(vt_path.read_bytes())))
        print('checks written %d, certified by the reference %d (%.1f%%); tasks with zero certified checks: %d' % (
            nw, nk, 100.0 * nk / max(nw, 1), sum(r['certified']['n_checks'] == 0 for r in out.values())))
        return
    if not vt_path.exists():
        raise SystemExit('run --stage tests first')
    vt_raw = vt_path.read_bytes(); stamp['visible_tests_sha256'] = sha256_bytes(vt_raw)
    vt = json.loads(vt_raw)['tests']
    vtests = {u: r['certified'] for u, r in vt.items()}      # the frozen artifact is self-contained: no reference is consulted at run time

    out_dir = base / a.stage; out_dir.mkdir(exist_ok=True)
    ep_path, dec_path = out_dir / 'episodes.jsonl', out_dir / 'decisions.jsonl'

    # ------------------------------------------------------------- single-writer lock
    lock_path = out_dir / 'run.lock'
    if lock_path.exists():
        holder = json.loads(lock_path.read_text())
        if _alive(holder['pid']):
            raise SystemExit('stage %s is already being written by pid %s (invocation %s)' % (a.stage, holder['pid'], holder['invocation']))
        print('removing stale lock of dead pid', holder['pid'])
    lock_path.write_text(json.dumps(dict(pid=os.getpid(), invocation=invocation, started_utc=now_iso())))
    atexit.register(lambda: lock_path.exists() and lock_path.unlink())

    # ------------------------------------------------------------- upstream completeness + episodes for this stage
    def complete(stage_name, wanted_ids):
        ok, exhausted, _, _ = resolved_ids(base / stage_name / 'episodes.jsonl', cfg['max_attempts_per_episode'])
        return [e for e in wanted_ids if e not in ok and e not in exhausted]
    learned = None
    if a.stage == 'pilot':
        rng = np.random.default_rng(cfg['design_seed'] + 1)
        eps = [dict(episode_id='pilot:%s#%d' % (u, r), task_uid=u, run=r, split='pilot', policy='randomized_log',
                    u=rng.random(cfg['horizon']).tolist(), seed=int(rng.integers(1, 2**31 - 1)), run_order=i * a.pilot_runs + r)
               for i, u in enumerate(design['pilot_tasks']) for r in range(a.pilot_runs)]
    elif a.stage == 'branch':
        missing = complete('log', [e['episode_id'] for e in design['log_episodes'] if e['split'] == 'confirm'])
        if missing:
            raise SystemExit('branch audit needs the COMPLETE confirm log; %d episodes unresolved' % len(missing))
        plan_path = out_dir / 'branch_plan.json'
        if not plan_path.exists():      # the sample is drawn ONCE from the complete log and frozen
            recs, _ = read_jsonl(base / 'log' / 'episodes.jsonl')
            last = {}
            for r in recs:
                if not r.get('error'):
                    last[r['episode_id']] = r
            parents = sorted((r for r in last.values() if r['split'] == 'confirm' and r['n_decisions'] >= 2), key=lambda r: r['episode_id'])
            ba = design['branch_audit']; rng = np.random.default_rng(ba['seed'])
            pick = sorted(rng.choice(len(parents), size=min(ba['n_prefixes'], len(parents)), replace=False).tolist())
            plan = dict(created_utc=now_iso(), n_eligible_prefixes=len(parents), sampling_probability=len(pick) / max(len(parents), 1),
                        log_sha256=sha256_bytes((base / 'log' / 'episodes.jsonl').read_bytes()), episodes=[])
            for i in pick:
                for arm in (0, 1):
                    for c in range(ba['continuations_per_arm']):
                        plan['episodes'].append(dict(episode_id='branch:%s:%s#%d' % (parents[i]['episode_id'], P_ARMS[arm], c), parent_episode_id=parents[i]['episode_id'],
                                                     task_uid=parents[i]['task_uid'], run=c, split='confirm', policy='branch_stay_' + P_ARMS[arm], forced_arm=arm,
                                                     seed=int(rng.integers(1, 2**31 - 1)), run_order=len(plan['episodes'])))
            plan_path.write_text(json.dumps(plan, indent=0))
        plan = json.loads(plan_path.read_text()); eps = plan['episodes']
        recs, _ = read_jsonl(base / 'log' / 'episodes.jsonl')
        parent_of = {r['episode_id']: r for r in recs if not r.get('error')}
    else:
        if a.stage == 'live':
            missing = complete('log', [e['episode_id'] for e in design['log_episodes']])
            if missing:
                raise SystemExit('live stage needs the COMPLETE randomized log; %d episodes unresolved' % len(missing))
            lp = base / 'learned_policy.json'
            if not lp.exists():
                raise SystemExit('freeze %s (analysis.py --learn) and push it before live execution' % lp)
            learned = P.table_policy({tuple(k): v for k, v in json.loads(lp.read_text())['table']})
            stamp['learned_policy_sha256'] = sha256_bytes(lp.read_bytes())
        eps = sorted(design['%s_episodes' % a.stage], key=lambda e: e['run_order'])
    lacking = sorted({e['task_uid'] for e in eps} - set(vtests))
    if lacking:
        raise SystemExit('%d design tasks have no visible tests (e.g. %s); refusing to drop them silently' % (len(lacking), lacking[:3]))

    ok, exhausted, n_err, torn = resolved_ids(ep_path, cfg['max_attempts_per_episode'])
    todo = [e for e in eps if e['episode_id'] not in ok and e['episode_id'] not in exhausted][: a.limit]
    prev_inv, _ = read_jsonl(out_dir / 'run_manifest.jsonl')
    for key in ('config_sha256', 'visible_tests_sha256', 'tasks_sha256'):
        if any(m.get(key) not in (None, stamp.get(key)) for m in prev_inv):
            raise SystemExit('%s differs from an earlier invocation of stage %s; this stage cannot be resumed with changed inputs' % (key, a.stage))
    code_changed = any(m.get('code_sha256') != stamp['code_sha256'] for m in prev_inv)
    if code_changed and not a.allow_code_change:
        raise SystemExit('code_sha256 differs from an earlier invocation of stage %s; pass --allow-code-change to resume (it is recorded)' % a.stage)
    if not a.mock:
        stamp['gguf'] = gguf_digests(cfg); stamp['server_facts'] = server_facts(cfg)
    with open(out_dir / 'run_manifest.jsonl', 'a') as mf:
        mf.write(json.dumps(dict(started_utc=now_iso(), argv=sys.argv[1:], n_todo=len(todo), n_ok_before=len(ok), n_exhausted_before=len(exhausted),
                                 n_retries_in_todo=sum(1 for e in todo if e['episode_id'] in n_err), torn_lines_seen=torn, code_changed_since_first_invocation=code_changed,
                                 design_sha256=(RESULTS / 'design.sha256').read_text().strip() if (not a.mock and (RESULTS / 'design.sha256').exists()) else None, **stamp)) + '\n')
    if torn:      # never append after a torn line: terminate it so the next record starts on its own line
        with open(ep_path, 'a') as f:
            f.write('\n')
    lock = threading.Lock(); dec_f = open(dec_path, 'a')

    def on_decision(eid, attempt):
        def log_it(_eid, dec):
            with lock:
                dec_f.write(json.dumps(dict(episode_id=_eid, invocation=invocation, attempt=attempt, logged_utc=now_iso(),
                                            **{k: dec[k] for k in ('t', 'eligible', 'available_actions', 'state', 'a', 'action', 'p_large', 'b_obs', 'draw', 'source', 'penalty', 'transcript_sha256')})) + '\n')
                dec_f.flush(); os.fsync(dec_f.fileno())
        return log_it

    def chooser(e):
        if 'forced_arm' in e:       # branch audit: forked model at t=1, kept at t=2
            return lambda state: (e['forced_arm'], float(e['forced_arm']), 'branch_forced', None)
        pol = None if e['policy'] == 'randomized_log' else (learned if e['policy'] == 'learned' else P.PRESPECIFIED[e['policy']])

        def choose(state):
            pl = cfg['p_large'] if pol is None else float(pol(state))
            u = e['u'][state['t']]
            a_t = int(u < pl)
            if pol is None and state['t'] == 0 and 'a0_block' in e and a_t != e['a0_block']:
                raise RuntimeError('realised a_0 %d differs from the design block %d' % (a_t, e['a0_block']))
            return a_t, pl, ('design_u' if pol is None else 'policy:' + e['policy']), u
        return choose

    ep_stamp = {k: v for k, v in stamp.items() if k not in ('gguf', 'server_facts')}

    def guarded(e):
        attempt = n_err.get(e['episode_id'], 0) + 1
        try:
            waited, check_failed = 0, False
            while not a.mock and not a.allow_contention:
                b = foreign_busy_servers(own)
                if b is None:
                    check_failed = True; break            # cannot tell: proceed, but say so in the record
                if not b:
                    break
                time.sleep(30); waited += 30
            b = foreign_busy_servers(own) if (a.allow_contention and not a.mock) else []
            resume = None
            if a.stage == 'branch':
                par = parent_of[e['parent_episode_id']]
                resume = dict(restore_first_failure_prefix(tasks[e['task_uid']], vtests[e['task_uid']], par, cfg), parent_episode_id=par['episode_id'], arm=P_ARMS[e['forced_arm']])
            rec = run_episode(tasks[e['task_uid']], vtests[e['task_uid']], e, chooser(e), models, cfg, ep_stamp, on_decision(e['episode_id'], attempt), resume)
            rec.update(yielded_seconds_before_start=waited, contention_check_failed=check_failed or b is None, foreign_gpu_load_at_start=bool(b))
        except Exception as ex_:      # nothing may escape: an escaped exception would discard every queued result
            rec = dict(episode_id=e['episode_id'], task_uid=e['task_uid'], split=e.get('split'), run=e.get('run'), policy=e.get('policy'),
                       error='runner: ' + repr(ex_)[:400], decisions=[], **ep_stamp)
        rec['attempt'] = attempt
        return rec

    t0 = time.time(); k = 0; errs = 0
    with ThreadPoolExecutor(cfg['workers']) as ex, open(ep_path, 'a') as f:
        futs = [ex.submit(guarded, e) for e in todo]
        try:
            for fu in as_completed(futs):
                rec = fu.result()
                with lock:
                    f.write(json.dumps(rec) + '\n'); f.flush(); os.fsync(f.fileno()); k += 1; errs += bool(rec.get('error'))
                    if k % 50 == 0 or k == len(todo):
                        el = time.time() - t0
                        print('%d/%d episodes  %.2fs/ep  errors %d  eta %.0f min' % (k, len(todo), el / k, errs, (len(todo) - k) * el / k / 60), flush=True)
                    if errs >= 25 and errs > 0.5 * k:
                        raise SystemExit('more than half of %d episodes errored - a server is probably down; stopping instead of burning the design' % k)
        finally:
            for fu in futs:
                fu.cancel()      # queued work is dropped on abort; in-flight episodes still finish and are NOT lost on the next resume
    print('done ->', ep_path, '| errors this invocation:', errs)


if __name__ == '__main__':
    main()
