"""DTR-REQ-016 (lead 97656b5, docs/theory_feedback_20260925_req015_decision.md): ONE fixed-backend Qwen2.5-Coder-7B
DEVELOPMENT competence screen on the REQ-015-qualified MiniWoB book-flight task, seeds 200-207 in order, one episode
each, through the restricted adapter (req016_adapter). No router, no 14B, no extra seeds, no rescue.

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_browser/req016_screen.py --admission-only   (read-only)
    work/venvs/minisweagent_04d809c/bin/python experiments/v2_browser/req016_screen.py                    (single shot)

This supervising parent reuses the committed REQ-011 serving code (pilot_runner.Servers through req011_pair, the
served-identity check and the separate server watchdog) and runs the episodes in a child process in the pinned REQ-015
BrowserGym venv (req016_episodes.py). It samples physical memory and host disk every <= 5 s while the child runs:
below the versioned thresholds, an unavailable measurement, or a sampling gap over 10 s stops only the owned child and
server (capacity interruption: not an outcome, never a zero). The committed manifest
configs/v2_req016_7b_browser_screen_20260925.json is the specification.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (Path(__file__).resolve().parent, ROOT / 'experiments/v2_agent', ROOT / 'experiments/v2_adapter'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req011_pair as P11  # noqa: E402  committed REQ-011 runner, imported read-only
import req016_adapter as AD  # noqa: E402
PR, S = P11.PR, P11.S
GiB = 2 ** 30

REQUEST = 'DTR-REQ-016'
MANIFEST_REL = 'configs/v2_req016_7b_browser_screen_20260925.json'
HOLDER = 'DTR-AgentEvals worker (DTR-REQ-016 7B browser screen)'
OWN_SCRIPTS = ('req016_screen.py', 'req016_episodes.py')
SERIES = 'resource_samples.jsonl'
SWAP_FIELD = re.compile(r'\b(total|used|free) = ([0-9]+(?:\.[0-9]+)?)([KMG])\b')
UNITS = dict(K=2 ** 10, M=2 ** 20, G=2 ** 30)


class Gate(RuntimeError):
    pass


@contextlib.contextmanager
def rebound(module, **values):
    old = {k: getattr(module, k) for k in values}
    for k, v in values.items():
        setattr(module, k, v)
    try:
        yield module
    finally:
        for k, v in old.items():
            setattr(module, k, v)


def load_manifest(root=ROOT):
    raw = (root / MANIFEST_REL).read_bytes()
    return raw, json.loads(raw), S.sha_bytes(raw)


def prompt_sha256():
    return S.sha_bytes((AD.SYSTEM_PROMPT + '\n\x00\n' + AD.USER_TEMPLATE).encode())


# ------------------------------------------------------------------ capacity (versioned rule req016-capacity-v1)
def capped(run, seconds):
    return lambda cmd, env=None, timeout=60: run(cmd, env=env, timeout=min(timeout, seconds))


def swap_gib(run=S.sh, timeout=1):
    rc, out, _ = run(['sysctl', '-n', 'vm.swapusage'], timeout=timeout)
    hits = SWAP_FIELD.findall(out or '') if rc == 0 else []
    if sorted(h[0] for h in hits) != ['free', 'total', 'used']:
        return OrderedDict(swap_total_gib=None, swap_used_gib=None, swap_free_gib=None)
    return OrderedDict(('swap_%s_gib' % n, round(float(v) * UNITS[u] / GiB, 3)) for n, v, u in hits)


def measure(root, run=S.sh, usage=shutil.disk_usage, timeouts=None):
    """physical free % (memory_pressure) and host disk free GiB, each with its own timeout; swap recorded."""
    timeouts = timeouts or dict(physical_free_pct=3, swap=1)
    errors = OrderedDict()
    try:
        pct = P11.memory_free_pct(capped(run, timeouts['physical_free_pct']))
    except Exception as e:  # noqa: BLE001  recorded; unavailable fails closed
        pct, errors['physical_free_pct'] = None, '%s: %s' % (type(e).__name__, e)
    try:
        host = usage(str(root)).free / GiB
    except Exception as e:  # noqa: BLE001
        host, errors['host_disk_free_gib'] = None, '%s: %s' % (type(e).__name__, e)
    out = OrderedDict(physical_free_pct=pct, host_disk_free_gib=host)
    out.update(swap_gib(run, timeouts['swap']))
    out['measurement_errors'] = errors
    return out


def capacity_problems(sample, thresholds):
    problems = []
    for key, low in thresholds.items():
        v = sample.get(key)
        if type(v) not in (int, float):
            problems.append('%s unavailable (fails closed)' % key)
        elif v < low:
            problems.append('%s %s is below %s' % (key, round(v, 3), low))
    return problems


def append_line(path, obj):
    with open(path, 'a') as fh:
        fh.write(json.dumps(obj, default=str) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def make_sampler(path, measure_fn, thresholds, clock=time.time):
    def sample(phase):
        t = clock()
        s = OrderedDict(phase=phase, t=t, utc=S.utc(t))
        s.update(measure_fn())
        s['sample_seconds'] = round(clock() - t, 3)
        s['problems'] = capacity_problems(s, thresholds[phase])
        append_line(path, s)
        return s
    return sample


def take_sample(sampler, phase):
    try:
        s = sampler(phase)
        return s, list(s['problems'])
    except Exception as e:  # noqa: BLE001  a sample that cannot be taken or recorded fails closed
        return None, ['the %s sample could not be taken or recorded: %s: %s' % (phase, type(e).__name__, str(e)[:200])]


def supervise(child, sampler, stop, clock=time.time, wait=None, interval=5.0, max_gap=10.0, deadline=None,
              health=None):
    """Wait for the child while sampling every `interval` s (start to start). A failing or unavailable sample, a gap
    over `max_gap` s between sample starts, or the deadline, stops the owned work through `stop(reason, detail)`
    unless the child has already exited. Returns an OrderedDict describing the end of supervision."""
    wait = wait or (lambda seconds: child.wait(timeout=seconds))
    last = None
    n = 0
    max_seen = 0.0
    while True:
        if child.poll() is not None:
            return OrderedDict(ended='child_exited', samples=n, max_gap_s=round(max_seen, 3))
        problem = health() if health else None
        if problem:
            stop('server_failure', OrderedDict(problem=problem))
            return OrderedDict(ended='server_failure', samples=n, max_gap_s=round(max_seen, 3), problem=problem)
        now = clock()
        if deadline is not None and now >= deadline:
            stop('batch_deadline', OrderedDict(utc=S.utc(now)))
            return OrderedDict(ended='batch_deadline', samples=n, max_gap_s=round(max_seen, 3))
        s, problems = take_sample(sampler, 'episode')
        n += 1
        if last is not None:
            gap = now - last
            max_seen = max(max_seen, gap)
            if gap > max_gap:
                problems.append('sampling gap %.1f s exceeds %s s (fails closed)' % (gap, max_gap))
        last = now
        if problems:
            if child.poll() is not None:
                return OrderedDict(ended='child_exited', samples=n, max_gap_s=round(max_seen, 3),
                                   breach_after_child_exit=OrderedDict(sample=s, problems=problems))
            stop('capacity_interruption', OrderedDict(sample=s, problems=problems))
            return OrderedDict(ended='capacity_interruption', samples=n, max_gap_s=round(max_seen, 3),
                               breach=OrderedDict(sample=s, problems=problems))
        try:
            wait(max(0.1, interval - (clock() - now)))
        except subprocess.TimeoutExpired:
            pass


# ------------------------------------------------------------------ admission
def assignment(manifest):
    return manifest['assignment']


def probe_manifest(root, manifest=None):
    _, m, _ = load_manifest(root) if manifest is None else (None, manifest, None)
    m11 = json.loads((root / m['model_source']['manifest']).read_text())
    row = next(a for a in m11['assignments'] if a['backend'] == 'small')
    a = assignment(m)
    problems = []
    for k in ('backend', 'port', 'alias', 'gguf', 'gguf_sha256', 'gguf_bytes', 'model', 'model_commit'):
        if a.get(k) != row.get(k):
            problems.append('assignment %s differs from the REQ-011 7B row' % k)
    if a.get('gguf_sha256') != m['lead_pins']['gguf_sha256']:
        problems.append('the GGUF sha256 differs from the lead-stated value')
    if P11.SERVING['llama_cpp_commit'] != m['lead_pins']['llama_cpp_commit']:
        problems.append('the llama.cpp pin differs from the lead-stated value')
    if m['seeds'] != list(range(200, 208)):
        problems.append('seeds are not 200-207 in order')
    st = m['settings']
    if (st['temperature'], st['max_tokens'], st['context']) != (0, 1536, 16384):
        problems.append('settings are not T=0, max_tokens 1536, context 16384')
    c = m['caps']
    if (c['logical_per_episode'], c['physical_per_episode'], c['batch_wall_s']) != (16, 32, 5400):
        problems.append('caps are not 16 logical / 32 physical per episode / 5400 s')
    if m['adapter']['prompt_sha256'] != prompt_sha256():
        problems.append('the frozen prompt sha256 differs from req016_adapter')
    if S.sha_file(root / m['model_source']['manifest']) != m['model_source']['manifest_sha256']:
        problems.append('model_source.manifest_sha256 differs from the REQ-011 manifest')
    if S.sha_file(root / m['browser']['req015_manifest']) != m['browser']['req015_manifest_sha256']:
        problems.append('browser.req015_manifest_sha256 differs from the REQ-015 manifest')
    for rel, want in m['adapter']['files'].items():
        if S.sha_file(root / rel) != want:
            problems.append('%s sha256 differs from the manifest' % rel)
    return not problems, OrderedDict(problems=problems, req011_row=row)


def source_rows(root, rels, run=S.sh):
    rows = OrderedDict()
    for s in rels:
        tracked = run(['git', '-C', str(root), 'ls-files', '--error-unmatch', s])[0] == 0
        rows[s] = OrderedDict(sha256=S.sha_file(root / s) if (root / s).is_file() else None, tracked=tracked,
                              unchanged_from_head=tracked and run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD',
                                                                   '--', s])[0] == 0)
    return rows


def probe_sources(root, manifest, run=S.sh):
    rows = source_rows(root, manifest['sources'], run)
    return all(r['tracked'] and r['unchanged_from_head'] for r in rows.values()), rows


def child_config(root, manifest, raw, deadline_epoch):
    a = assignment(manifest)
    return OrderedDict(request=REQUEST, seeds=manifest['seeds'], caps=manifest['caps'], settings=manifest['settings'],
                       alias=a['alias'], endpoint='http://%s:%d/v1/chat/completions' % (P11.SERVING['host'], a['port']),
                       deadline_epoch=deadline_epoch, out_dir=str(raw), task=manifest['task'], parent_pid=os.getpid(),
                       req015_manifest=manifest['browser']['req015_manifest'])


def child_env(root, manifest):
    env, removed = S.scrub_env(dict(os.environ))
    b = manifest['browser']
    env['MINIWOB_URL'] = (root / b['miniwob_html_dir']).as_uri() + '/'
    env['PLAYWRIGHT_BROWSERS_PATH'] = str(root / b['playwright_browsers_path'])
    return env, removed


def probe_browser(root, manifest, run=S.sh, scratch=None):
    """The child's --admission in the pinned BrowserGym venv (REQ-015 source/runtime pins and the action set)."""
    scratch = Path(scratch or (root / 'work/runs/req016_admission_scratch'))
    scratch.mkdir(parents=True, exist_ok=True)
    cfg = scratch / ('admission_%d.json' % os.getpid())
    cfg.write_text(json.dumps(child_config(root, manifest, scratch, 0)))
    env, _ = child_env(root, manifest)
    rc, out, err = run([str(root / manifest['browser']['python']), str(root / manifest['browser']['entry']),
                        '--admission', str(cfg)], env=env, timeout=120)
    cfg.unlink()
    try:
        d = json.loads(out)
    except ValueError:
        d = OrderedDict(rc=rc, stdout=out[-500:], stderr=err[-500:])
    return rc == 0 and bool(d.get('ok')), d


def probe_memory(root, manifest, run=S.sh):
    rule = manifest['capacity']
    free = P11.memory_free_pct(run)
    rc, out, _ = run(['sysctl', '-n', 'hw.memsize'])
    memsize = int(out.strip()) if rc == 0 and out.strip().isdigit() else None
    a = assignment(manifest)
    projection = a['gguf_bytes'] + int((rule['kv_gib'] + rule['vm_gib'] + rule['browser_gib']) * GiB)
    limit = None if memsize is None else memsize - rule['margin_gib'] * GiB
    d = OrderedDict(memory_free_pct=free, hw_memsize=memsize, projection_bytes=projection, projection_limit_bytes=limit,
                    swap=swap_gib(run, 5), rule=rule)
    return (free is not None and free >= rule['thresholds']['admission']['physical_free_pct'] and limit is not None
            and projection <= limit), d


def probe_disk(root, manifest, usage=shutil.disk_usage):
    host = usage(str(root)).free / GiB
    return host >= manifest['capacity']['thresholds']['admission']['host_disk_free_gib'], OrderedDict(
        host_disk_free_gib=host)


def own_processes(run=S.sh):
    _, rows = S.process_table(run)
    mine = S.ancestors(rows, os.getpid()) | {os.getpid()}
    return [pid for pid, _, argv in rows if pid not in mine and '--admission-only' not in argv
            and any(Path(x).name in OWN_SCRIPTS for x in argv[:3])]


def probe_conflicts(root, manifest, run=S.sh):
    ok, d = P11.probe_conflicts(root, run)
    d['other_req016_processes'] = own_processes(run)
    d['req016_pause_file_present'] = (root / manifest['outputs']['pause_file']).exists()
    return ok and not d['other_req016_processes'] and not d['req016_pause_file_present'], d


def admission_probes(manifest):
    return OrderedDict(manifest=lambda root: probe_manifest(root, manifest),
                       sources=lambda root: probe_sources(root, manifest),
                       browser=lambda root: probe_browser(root, manifest),
                       models=lambda root: P11.probe_models(root, [assignment(manifest)]),
                       conflicts=lambda root: probe_conflicts(root, manifest),
                       memory=lambda root: probe_memory(root, manifest),
                       disk=lambda root: probe_disk(root, manifest))


PIN_PROBES = ('manifest', 'sources', 'browser', 'models')


# ------------------------------------------------------------------ serving and watchdog (REQ-016 labels)
class Servers(P11.Servers):
    """pilot_runner.Servers through the REQ-011 subclass; the ownership record is re-labelled for DTR-REQ-016."""

    def _record(self):
        super()._record()
        rec = json.loads(PR.SERVERS.read_text())
        rec['holder'] = HOLDER
        tmp = PR.SERVERS.with_suffix('.tmp')
        tmp.write_text(json.dumps(rec, indent=1) + '\n')
        os.replace(tmp, PR.SERVERS)


def spawn_watchdog(raw, deadline, env, popen=subprocess.Popen):
    def launch(cmd, **options):
        return popen([cmd[0], str(Path(__file__).resolve())] + list(cmd[2:]), **options)
    with rebound(P11, REQUEST=REQUEST, HOLDER=HOLDER):
        return P11.spawn_watchdog(raw, deadline, env, popen=launch)


def runtime_processes(root, manifest, run=S.sh):
    prefixes = tuple(str(root / p) for p in manifest['browser']['exclusive_runtime_paths'])
    _, rows = S.process_table(run)
    return [pid for pid, _, argv in rows if argv and argv[0].startswith(prefixes)]


def sweep_browser_processes(root, manifest, run=S.sh, kill=os.kill, sleep=time.sleep, baseline=()):
    """Processes running from this request's exclusive browser runtime (the isolated Playwright browsers path or the
    pinned BrowserGym venv) that were not running before the child started (`baseline`), after the child ended:
    SIGTERM, then SIGKILL. Nothing else."""
    before = set(baseline)

    def owned():
        return [pid for pid in runtime_processes(root, manifest, run) if pid not in before]
    first = owned()
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in owned():
            try:
                kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
        for _ in range(25):
            if not owned():
                break
            sleep(0.2)
    return OrderedDict(baseline=sorted(before), found=first, remaining=owned())


# ------------------------------------------------------------------ the screen
def run_screen(ctx):
    root, raw, manifest = ctx['root'], ctx['raw'], ctx['manifest']
    summary = ctx['summary']
    a = assignment(manifest)
    caps, thresholds = manifest['caps'], manifest['capacity']['thresholds']
    sampler = make_sampler(raw / SERIES, lambda: measure(root), thresholds)
    servers = Servers(json.loads((root / P11.SERVING['conversion_record']).read_text()),
                      dict(block=1, block_start_utc=S.utc(ctx['start']), block_hard_end_utc=S.utc(ctx['deadline']),
                           hard_deadline_epoch=ctx['deadline']), raw)
    env, removed = child_env(root, manifest)
    summary['environment_variables_removed'] = removed
    wd, ready = spawn_watchdog(raw, ctx['deadline'], dict(os.environ))
    summary['watchdog'] = OrderedDict(pid=wd.pid, ready=ready)
    child = None
    try:
        if not ready:
            raise Gate('the server watchdog did not become ready: no server is started without it')
        try:
            load = servers.serve(a['backend'])
            checks, problems = P11.check_served(servers, a, root)
        except Exception as e:  # noqa: BLE001  a serving failure is a gate (BLOCKED), never a substitution
            summary['serving'] = OrderedDict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
            raise Gate('serving the 7B failed: %s' % type(e).__name__)
        summary['serving'] = OrderedDict(load=load, checks=checks, problems=problems)
        s, cap_problems = take_sample(sampler, 'post_load')
        summary['post_load_sample'] = s
        if problems or cap_problems:
            summary['status'] = 'BLOCKED'
            summary['blocked'] = OrderedDict(phase='post_load', served_problems=problems, capacity=cap_problems)
            return
        baseline = runtime_processes(root, manifest)
        summary['runtime_process_baseline'] = baseline
        cfg_path = raw / 'child_config.json'
        S.write_json_x(cfg_path, child_config(root, manifest, raw, ctx['deadline'] - caps['cleanup_reserve_s']))
        with open(raw / 'child_stdout.txt', 'x') as log:
            child = subprocess.Popen([str(root / manifest['browser']['python']), str(root / manifest['browser']['entry']),
                                      '--run', str(cfg_path)], cwd=str(root), env=env, stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
        summary['child'] = OrderedDict(pid=child.pid, started_utc=S.utc())
        stops = []

        def stop(reason, detail):
            stops.append(OrderedDict(reason=reason, utc=S.utc(), detail=detail))
            try:
                child.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
            if reason == 'capacity_interruption':
                P11.stop_server(servers, ctx)            # at once: nothing more is generated, memory is released
            try:
                child.wait(timeout=caps['child_stop_grace_s'])
            except subprocess.TimeoutExpired:
                S.kill_group(child.pid, grace=5)
        live = servers.live

        def health():
            return None if live['proc'].poll() is None else 'the owned server exited (code %s)' % live['proc'].poll()
        sup = supervise(child, sampler, stop, deadline=ctx['deadline'] - caps['cleanup_reserve_s'] + 60,
                        interval=manifest['capacity']['sample_interval_s'], max_gap=manifest['capacity']['max_gap_s'],
                        health=health)
        summary['supervision'] = sup
        summary['stops'] = stops
        if child.poll() is None:
            try:
                child.wait(timeout=caps['child_stop_grace_s'])
            except subprocess.TimeoutExpired:
                S.kill_group(child.pid, grace=5)
        summary['child']['returncode'] = child.poll()
        summary['status'] = screen_status(sup['ended'], child.poll(), load_batch(raw), len(manifest['seeds']))
    finally:
        if child is not None and child.poll() is None:
            S.kill_group(child.pid, grace=5)
        if servers.live is not None:
            P11.stop_server(servers, ctx)
        summary['server_events'] = servers.events
        try:
            summary['browser_process_sweep'] = sweep_browser_processes(root, manifest,
                                                                       baseline=summary.get('runtime_process_baseline', ()))
        except Exception as e:  # noqa: BLE001  recorded
            summary['browser_process_sweep'] = OrderedDict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
        summary['watchdog'].update(P11.release_watchdog(wd, servers))


def load_batch(raw):
    p = Path(raw) / 'batch_summary.json'
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except ValueError:                                   # truncated by a kill: the per-seed records are used instead
        return None


def screen_status(ended, returncode, batch, n_seeds):
    """COMPLETED only when the child exited 0 after recording every seed with no batch stop; otherwise the stop."""
    named = dict(capacity_interruption='CAPACITY_INTERRUPTION', batch_deadline='DEADLINE',
                 server_failure='SERVER_FAILURE')
    if ended in named:
        return named[ended]
    if returncode == 0 and batch and batch.get('stop') is None and len(batch.get('episodes') or []) == n_seeds:
        return 'COMPLETED'
    if batch and batch.get('stop'):
        return 'CHILD_STOPPED_' + str(batch['stop']).upper()
    return 'CHILD_FAILED'


UNRUN = ('stopped_by_supervisor', 'not_started', 'incomplete_record')


def episode_records(batch, raw):
    """Per-seed summaries: the batch summary, else the durable episodes.jsonl, else each episodes/seedN/episode.json."""
    found = OrderedDict((e.get('seed'), e) for e in (batch or {}).get('episodes', []))
    if raw is not None:
        lines = Path(raw) / 'episodes.jsonl'
        if lines.exists():
            for l in lines.read_text().splitlines():
                try:
                    e = json.loads(l)
                except ValueError:
                    continue
                found.setdefault(e.get('seed'), e)
        for p in sorted((Path(raw) / 'episodes').glob('seed*/episode.json')):
            try:
                e = json.loads(p.read_text())
            except ValueError:                           # truncated by a kill: that seed stays incomplete_record
                continue
            found.setdefault(e.get('seed'), e)
    return found


def score(batch, status, raw=None):
    """0-8/8 full successes (all eight seeds in the denominator) and the cause of every seed. Under any status other than
    COMPLETED, a seed stopped, not started or left without a summary carries the stop instead of an outcome: capacity
    rows are labelled capacity (not outcomes, never zeros), other rows 'not_run: <STATUS>'."""
    rows = []
    by_seed = episode_records(batch, raw)
    for seed in range(200, 208):
        e = by_seed.get(seed)
        if e is None:
            partial = raw is not None and (Path(raw) / 'episodes' / ('seed%d' % seed)).exists()
            e = OrderedDict(seed=seed, cause='incomplete_record' if partial else 'not_started', full_success=False)
        cause = e.get('cause') or 'unknown'
        if status == 'CAPACITY_INTERRUPTION' and cause in UNRUN:
            cause = 'capacity_interruption' if cause in ('stopped_by_supervisor', 'incomplete_record') else \
                'not_run_capacity'
        elif status != 'COMPLETED' and cause in UNRUN:
            cause = 'not_run: %s (%s)' % (status, cause)
        rows.append(OrderedDict(seed=seed, cause=cause, full_success=bool(e.get('full_success')),
                                **{k: e.get(k) for k in ('logical_calls', 'physical_attempts', 'executed_actions',
                                                         'invalid_replies', 'invalid_causes', 'action_errors',
                                                         'prompt_tokens', 'completion_tokens', 'usage_unknown_calls',
                                                         'wall_seconds', 'terminal', 'error')}))
    taxonomy = OrderedDict()
    for r in rows:
        taxonomy[r['cause']] = taxonomy.get(r['cause'], 0) + 1
    return OrderedDict(full_success=sum(r['full_success'] for r in rows), denominator=8, screen_status=status,
                       screen_complete=status == 'COMPLETED', taxonomy=taxonomy,
                       capacity_rows=[r['seed'] for r in rows if r['cause'] in ('capacity_interruption',
                                                                                'not_run_capacity')],
                       rows=rows)


def series_stats(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []
    phys = [r['physical_free_pct'] for r in rows if isinstance(r.get('physical_free_pct'), (int, float))]
    host = [r['host_disk_free_gib'] for r in rows if isinstance(r.get('host_disk_free_gib'), (int, float))]
    swap = [r['swap_used_gib'] for r in rows if isinstance(r.get('swap_used_gib'), (int, float))]
    ep = [r['t'] for r in rows if r.get('phase') == 'episode']
    gaps = [b - a for a, b in zip(ep, ep[1:])]
    return OrderedDict(samples=len(rows), episode_samples=len(ep), min_physical_free_pct=min(phys) if phys else None,
                       min_host_disk_free_gib=min(host) if host else None, peak_swap_used_gib=max(swap) if swap else None,
                       max_episode_gap_s=round(max(gaps), 3) if gaps else None,
                       samples_with_problems=sum(1 for r in rows if r.get('problems')))


def publish(raw, pub):
    pub.mkdir(parents=True, exist_ok=False)
    entries = OrderedDict()
    for f in sorted(raw.rglob('*')):
        if not f.is_file():
            continue
        rel = f.relative_to(raw)
        data = f.read_bytes()
        sanitized = False
        if f.suffix in ('.json', '.jsonl', '.md', '.txt', '.log'):
            text = S.sanitize(data.decode(errors='replace'))
            sanitized = text.encode() != data
            data = text.encode()
            if f.suffix == '.log':
                rel = rel.with_suffix('.log.txt')
        dst = pub / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        entries[str(rel)] = OrderedDict(raw_sha256=S.sha_file(f), published_sha256=S.sha_bytes(data), sanitized=sanitized)
    S.write_json_x(pub / 'publication_manifest.json', entries)
    return entries


def main(argv=None, root=ROOT, probes=None, runner=None, clock=time.time):
    ap = argparse.ArgumentParser(description='DTR-REQ-016 one 7B fixed-backend browser screen')
    ap.add_argument('--admission-only', action='store_true')
    ap.add_argument('--watchdog', metavar='CONFIG', help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.watchdog:
        with rebound(P11, REQUEST=REQUEST, HOLDER=HOLDER):
            return P11.watchdog(args.watchdog)
    manifest_bytes, manifest, msha = load_manifest(root)
    out = manifest['outputs']
    raw, pub = root / out['raw'], root / out['published']
    start = clock()
    adm = S.admission(root, probes if probes is not None else admission_probes(manifest))
    adm.update(request=REQUEST, status='DEVELOPMENT', manifest_file=MANIFEST_REL, manifest_sha256=msha,
               mode='admission-only' if args.admission_only else 'launch')
    if args.admission_only:
        print(json.dumps(S.sanitize(adm), indent=1, default=str))
        return 0 if adm['admitted'] else 1
    if raw.exists() or pub.exists():
        print('DTR-REQ-016 is single-shot: %s or %s exists' % (out['raw'], out['published']), file=sys.stderr)
        return 3
    pin_failed = [k for k in PIN_PROBES if not adm[k]['ok']]
    if pin_failed:
        print('DTR-REQ-016 refused before its namespace (nothing consumed): pin checks failed: %s' % pin_failed,
              file=sys.stderr)
        return 3
    raw.mkdir(parents=True)
    with open(raw / 'manifest.json', 'xb') as fh:
        fh.write(manifest_bytes)
    S.write_json_x(raw / 'admission.json', adm)
    deadline = start + manifest['caps']['batch_wall_s']
    summary = OrderedDict(request=REQUEST, status=None, kind=manifest['kind'], manifest=MANIFEST_REL,
                          manifest_sha256=msha, started_utc=S.utc(start), batch_deadline_utc=S.utc(deadline),
                          assignment=assignment(manifest), seeds=manifest['seeds'], caps=manifest['caps'])
    ctx = dict(root=root, raw=raw, manifest=manifest, start=start, deadline=deadline, summary=summary)
    old = {}
    try:
        return _finish_main(ctx, adm, runner, clock, old)
    finally:
        for sig, handler in old.items():                    # never leak ignored signals into this process
            signal.signal(sig, handler)


def _finish_main(ctx, adm, runner, clock, old):
    root, raw, manifest, start, summary = ctx['root'], ctx['raw'], ctx['manifest'], ctx['start'], ctx['summary']
    pub = root / manifest['outputs']['published']
    if not adm['admitted']:
        summary.update(status='BLOCKED', blocked=OrderedDict(phase='admission', failed=[
            k for k, v in adm.items() if isinstance(v, dict) and v.get('ok') is False]))
    else:
        append_line(raw / SERIES, OrderedDict(phase='admission', t=start, utc=S.utc(start),
                                              physical_free_pct=adm['memory']['detail'].get('memory_free_pct'),
                                              host_disk_free_gib=adm['disk']['detail'].get('host_disk_free_gib'),
                                              **adm['memory']['detail'].get('swap', {}), problems=[]))
        old.update({sig: signal.signal(sig, S.raise_interrupted) for sig in (signal.SIGINT, signal.SIGTERM,
                                                                              signal.SIGHUP)})
        try:
            (runner or run_screen)(ctx)
        except S.Interrupted as e:
            summary.update(status='INTERRUPTED', error=str(e))
        except Gate as e:
            summary.update(status='BLOCKED', error=str(e))
        except Exception as e:  # noqa: BLE001  recorded; the summary is still written
            summary.update(status='ERROR', error='%s: %s' % (type(e).__name__, str(e)[:500]))
        finally:
            for sig in old:
                signal.signal(sig, signal.SIG_IGN)          # later signals never cut the records short
    summary['score'] = score(load_batch(raw), summary['status'], raw)
    summary['resources'] = series_stats(raw / SERIES)
    summary['finished_utc'] = S.utc(clock())
    summary['wall_seconds'] = round(clock() - start, 2)
    summary['within_batch_cap'] = summary['wall_seconds'] <= manifest['caps']['batch_wall_s']
    art = sum(f.stat().st_size for f in raw.rglob('*') if f.is_file())
    summary['raw_artifact_bytes'] = art
    summary['within_artifact_cap'] = art <= manifest['caps']['artifact_gib'] * GiB
    S.write_json_x(raw / 'screen_summary.json', summary)
    publish(raw, pub)
    hits = S.username_hits(pub)
    print(json.dumps(S.sanitize(OrderedDict(status=summary['status'], full_success=summary['score']['full_success'],
                                            denominator=8, taxonomy=summary['score']['taxonomy'],
                                            wall_seconds=summary['wall_seconds'], username_hits=hits))))
    return 0 if not hits else 4


if __name__ == '__main__':
    sys.exit(main())
