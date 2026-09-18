"""Runner for the code-routing study.

  python run.py --servers start|stop      llama-server for both models (frozen flags)
  python run.py --stage tests             environment construction: frozen visible tests, once per task
  python run.py --stage pilot             pilot tasks only (disjoint from train/confirm)
  python run.py --stage log               sequentially randomized log (frozen design), resumable
  python run.py --stage live              fresh executions of the frozen target policies on confirm tasks
  add --mock to dry-run any stage without a model (writes under work/, never under results/)

Every routing decision (state, full propensity, draw, action) is appended and fsync'ed to
decisions.jsonl BEFORE the model is invoked (protocol section 6). Completed runs are never
overwritten; re-running resumes the missing episodes only.

GPU courtesy guard: refuses to start while ANOTHER llama-server on this host is generating
(a sibling pre-registered experiment measures latency), unless --allow-contention (recorded).
The same check runs before EVERY episode, so if the sibling (re)starts mid-run this runner
stops launching new episodes until it is idle again (`yielded_seconds_before_start` per episode).
Episodes already in flight finish, so a restart can still see up to one episode of overlap.
"""
from __future__ import annotations
import argparse, json, os, signal, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests

from common import RESULTS, ROOT, code_sha256, git_head, load_config, load_tasks, now_iso, resolve, sha256_bytes
from agent import LlamaServerModel, MockModel, extract_code, restore_first_failure_prefix, run_episode, tests_prompt
import policies as P

LLAMA_BINS = [os.environ.get('LLAMA_SERVER', ''), str(ROOT / 'work' / 'llama.cpp' / 'build' / 'bin' / 'llama-server')]
PIDFILE = ROOT / 'work' / 'code_routing_servers.json'
P_ARMS = ('small', 'large')


def foreign_busy_servers(own_ports: set) -> list:
    busy = []
    try:
        out = subprocess.run(['/usr/sbin/lsof', '-nP', '-iTCP', '-sTCP:LISTEN'], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return busy
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


def servers(action: str, cfg: dict):
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    if action == 'stop':
        if PIDFILE.exists():
            for s in json.loads(PIDFILE.read_text()):
                try:
                    os.kill(s['pid'], signal.SIGTERM); print('stopped', s['alias'], s['pid'])
                except ProcessLookupError:
                    pass
            PIDFILE.unlink()
        return
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
    """sha256 of every weight file (slow once; cached under work/)."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--servers', choices=['start', 'stop'])
    ap.add_argument('--stage', choices=['tests', 'pilot', 'log', 'live', 'branch'])
    ap.add_argument('--mock', action='store_true')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--pilot-runs', type=int, default=4)
    ap.add_argument('--allow-contention', action='store_true')
    a = ap.parse_args()
    cfg = load_config()
    own = {m['port'] for m in cfg['models'].values()}
    if not a.mock and a.servers != 'stop':
        busy = foreign_busy_servers(own)
        if busy and not a.allow_contention:
            raise SystemExit("REFUSING: another llama-server is generating on port(s) %s; running now would contaminate that "
                             "experiment's latency outcomes. Retry later or pass --allow-contention (it is recorded)." % busy)
    if a.servers:
        return servers(a.servers, cfg)
    if not a.stage:
        ap.error('--stage or --servers required')

    tasks = {t['uid']: t for t in load_tasks(cfg)}
    base = (ROOT / 'work' / 'code_routing_mock') if a.mock else RESULTS
    base.mkdir(parents=True, exist_ok=True)
    if a.mock:
        models = dict(small=MockModel('small', tasks, 0.55), large=MockModel('large', tasks, 0.75))
        design = __import__('design').build(cfg, list(tasks.values()))
    else:
        models = {r: LlamaServerModel(r, m['alias'], m['port'], cfg) for r, m in cfg['models'].items()}
        for r, m in models.items():
            if m.alias not in m.served_ids():
                raise SystemExit('server for %s does not serve alias %s' % (r, m.alias))
        design = None
        if a.stage in ('tests', 'pilot') and not (RESULTS / 'design.json').exists():
            # before the freeze: pilot task ids depend only on design_seed and n_pilot_tasks, which the pilot may not change
            design = __import__('design').build(cfg, list(tasks.values())) if a.stage == 'pilot' else None
        else:
            raw = (RESULTS / 'design.json').read_bytes()
            if sha256_bytes(raw) != (RESULTS / 'design.sha256').read_text().strip():
                raise SystemExit('design.json does not match design.sha256')
            design = json.loads(raw)
            if design['config_sha256'] != cfg['_config_sha256']:
                raise SystemExit('config.json changed since the design was frozen')
    stamp = dict(config_sha256=cfg['_config_sha256'], code_sha256=code_sha256(), git_head=git_head(), mock=bool(a.mock),
                 contention_allowed=bool(a.allow_contention))

    # ------------------------------------------------------------- stage: frozen visible tests
    vt_path = base / 'visible_tests.json'
    if a.stage == 'tests':
        if vt_path.exists():
            raise SystemExit('%s exists; visible tests are part of the frozen environment' % vt_path)
        w = cfg['visible_tests']; writer = models[w['writer']]; out = {}
        def one(uid):
            kw = dict(task_uid=uid, kind='tests') if a.mock else {}
            r = writer.chat(tests_prompt(tasks[uid]), w['seed'], temperature=w['temperature'], max_tokens=w['max_tokens'], **kw)
            return uid, dict(tests=extract_code(r['text']), completion_tokens=r['completion_tokens'], finish=r['finish'])
        with ThreadPoolExecutor(cfg['workers']) as ex:
            for uid, rec in ex.map(one, sorted(tasks)[: a.limit]):
                out[uid] = rec
        vt_path.write_text(json.dumps(dict(writer=writer.alias, settings=w, created_utc=now_iso(), **stamp, tests=out), indent=0))
        print('visible tests for %d tasks -> %s (sha256 %s)' % (len(out), vt_path, sha256_bytes(vt_path.read_bytes())))
        return
    vt_raw = vt_path.read_bytes(); stamp['visible_tests_sha256'] = sha256_bytes(vt_raw)
    vtests = {u: r['tests'] for u, r in json.loads(vt_raw)['tests'].items()}

    # ------------------------------------------------------------- episodes for this stage
    if a.stage == 'pilot':
        rng = np.random.default_rng(cfg['design_seed'] + 1)
        eps = [dict(episode_id='pilot:%s#%d' % (u, r), task_uid=u, run=r, split='pilot', policy='randomized_log',
                    u=rng.random(cfg['horizon']).tolist(), seed=int(rng.integers(1, 2**31 - 1)), run_order=i * a.pilot_runs + r)
               for i, u in enumerate(design['pilot_tasks']) for r in range(a.pilot_runs)]
    elif a.stage == 'branch':
        # prefix population: CONFIRM log episodes whose first validation failed; equal-probability sample without replacement
        parents = sorted((json.loads(l) for l in (base / 'log' / 'episodes.jsonl').read_text().splitlines() if l.strip()), key=lambda e: e['episode_id'])
        parents = [e for e in parents if not e.get('error') and e['split'] == 'confirm' and e['n_decisions'] >= 2]
        ba = design['branch_audit']; rng = np.random.default_rng(ba['seed'])
        pick = sorted(rng.choice(len(parents), size=min(ba['n_prefixes'], len(parents)), replace=False).tolist())
        resumes, eps = {}, []
        for i in pick:
            par = parents[i]
            for arm in (0, 1):
                for c in range(ba['continuations_per_arm']):
                    eid = 'branch:%s:%s#%d' % (par['episode_id'], P_ARMS[arm], c)
                    eps.append(dict(episode_id=eid, task_uid=par['task_uid'], run=c, split='confirm', policy='branch_stay_' + P_ARMS[arm],
                                    forced_arm=arm, seed=int(rng.integers(1, 2**31 - 1)), run_order=len(eps),
                                    sampling_probability=len(pick) / len(parents)))
                    resumes[eid] = (par, arm)
    else:
        eps = sorted(design['%s_episodes' % a.stage], key=lambda e: e['run_order'])
    learned = None
    if a.stage == 'live':
        lp = base / 'learned_policy.json'
        if not lp.exists():
            raise SystemExit('freeze %s (analysis.py --learn) before live execution' % lp)
        learned = P.table_policy({tuple(k): v for k, v in json.loads(lp.read_text())['table']})
        stamp['learned_policy_sha256'] = sha256_bytes(lp.read_bytes())
    out_dir = base / a.stage; out_dir.mkdir(exist_ok=True)
    ep_path, dec_path = out_dir / 'episodes.jsonl', out_dir / 'decisions.jsonl'
    done = {json.loads(l)['episode_id'] for l in ep_path.read_text().splitlines() if l.strip()} if ep_path.exists() else set()
    todo = [e for e in eps if e['episode_id'] not in done and e['task_uid'] in vtests][: a.limit]
    if not a.mock:
        stamp['gguf'] = gguf_digests(cfg)
    with open(out_dir / 'run_manifest.jsonl', 'a') as mf:
        mf.write(json.dumps(dict(started_utc=now_iso(), argv=sys.argv[1:], n_todo=len(todo), n_done_before=len(done),
                                 design_sha256=(RESULTS / 'design.sha256').read_text().strip() if (not a.mock and (RESULTS / 'design.sha256').exists()) else None, **stamp)) + '\n')
    lock = threading.Lock(); dec_f = open(dec_path, 'a')

    def on_decision(eid, dec):
        with lock:
            dec_f.write(json.dumps(dict(episode_id=eid, logged_utc=now_iso(), **{k: dec[k] for k in ('t', 'state', 'a', 'action', 'p_large', 'b_obs', 'source', 'transcript_sha256')})) + '\n')
            dec_f.flush(); os.fsync(dec_f.fileno())

    def chooser(e):
        if 'forced_arm' in e:       # branch audit: the forked model is used at t=1 and kept at t=2 ("stay with the forked model")
            return lambda state: (e['forced_arm'], float(e['forced_arm']), 'branch_forced')
        pol = None if e['policy'] == 'randomized_log' else (learned if e['policy'] == 'learned' else P.PRESPECIFIED[e['policy']])
        def choose(state):
            pl = cfg['p_large'] if pol is None else float(pol(state))
            return int(e['u'][state['t']] < pl), pl, ('design_u' if pol is None else 'policy:' + e['policy'])
        return choose

    ep_stamp = {k: v for k, v in stamp.items() if k != 'gguf'}
    t0 = time.time(); k = 0
    with ThreadPoolExecutor(cfg['workers']) as ex, open(ep_path, 'a') as f:
        def resume_of(e):
            if a.stage != 'branch':
                return None
            par, arm = resumes[e['episode_id']]
            return dict(restore_first_failure_prefix(tasks[e['task_uid']], vtests[e['task_uid']], par, cfg), parent_episode_id=par['episode_id'], arm=P_ARMS[arm])
        def guarded(e):
            # yield to a sibling experiment that (re)starts mid-run: no NEW episode begins while a foreign llama-server generates
            waited = 0
            while not a.mock and not a.allow_contention and foreign_busy_servers(own):
                time.sleep(30); waited += 30
            rec = run_episode(tasks[e['task_uid']], vtests[e['task_uid']], e, chooser(e), models, cfg, ep_stamp, on_decision, resume_of(e))
            rec['yielded_seconds_before_start'] = waited
            return rec
        futs = [ex.submit(guarded, e) for e in todo]
        for fu in as_completed(futs):
            rec = fu.result()
            with lock:
                f.write(json.dumps(rec) + '\n'); f.flush(); k += 1
                if k % 50 == 0 or k == len(todo):
                    el = time.time() - t0
                    print('%d/%d episodes  %.2fs/ep  eta %.0f min' % (k, len(todo), el / k, (len(todo) - k) * el / k / 60), flush=True)
    print('done ->', ep_path)


if __name__ == '__main__':
    main()
