"""DTR-REQ-011 (lead a0e8379, docs/theory_feedback_20260924_req010_decision.md): ONE fixed-backend DEVELOPMENT
competence pair on astropy__astropy-14598, Qwen2.5-Coder-14B first and 7B second, under the committed manifest
configs/v2_req011_competence_pair_20260924.json (its declared rules are the specification of this runner).
Descriptive single-task feasibility only: not a paired causal comparison, not a population rate, not CONFIRM.

A thin runner over validated code, which it imports read-only and never edits:
  * serving: pilot_runner.Servers (pre-launch GGUF hash, foreign-process refusal, port check, health poll, owned stop);
    only the ownership holder label is rewritten. The frozen generation preflight is replaced by GET-only checks;
  * episodes: req011_entry.py in the pinned mini-swe-agent venv -> cue_episode.run_episode, arm 'baseline';
  * admission and supervision: req010_sentinel probes, scrub_env, docker_env, wait_wall, kill_group, sanitize;
  * grading: req011_grade.py in the pinned evaluator venv -> grade_identity.grade_flow, after the server is stopped;
  * containment beyond this process: a server watchdog (this file, --watchdog), started before the first load, stops
    the recorded llama-server if this process dies (even by SIGKILL) or the pair deadline passes; every child runs in
    its own process group, killed as a whole; cleanup cut short by a first signal is retried once (later ones are
    ignored).
Usage: work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req011_pair.py [--admission-only]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (Path(__file__).resolve().parent, ROOT / 'experiments/v2_adapter'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import pilot_runner as PR  # noqa: E402  frozen yaml-v1 runner (Servers, listener_pid, sha_file, constants)
import req010_sentinel as S  # noqa: E402  REQ-010 probes and supervision helpers
import workspace_capture as WC  # noqa: E402
import cue_admission as A  # noqa: E402
import cue_transport as CT  # noqa: E402
import grade_identity as GI  # noqa: E402

REQUEST = 'DTR-REQ-011'
MANIFEST_REL = 'configs/v2_req011_competence_pair_20260924.json'
REQ010_SUMMARY_REL = 'results/v2_adapter/req010_sentinel_20260924/sentinel_summary.json'
HOLDER = 'DTR-AgentEvals worker (DTR-REQ-011 competence pair)'
GiB = 1 << 30
CAPS = dict(pair_wall_s=7200, episode_wall_s=1800, episode_load_allowance_s=600, child_cleanup_grace_s=120,
            child_wait_slack_s=30, server_cleanup_reserve_s=90, grading_floor_s=900, evaluator_attempt_max_s=1800,
            evaluator_min_start_budget_s=600, evaluator_max_attempts=2, evaluator_end_reserve_s=300,
            grader_wait_slack_s=120, max_logical_requests=48, max_physical_requests=96, per_episode_logical=24,
            per_episode_physical=48, host_reserve_bytes=GiB)
MEMORY = dict(admission_min_free_pct=30, post_load_min_free_pct=10, kv_gib=dict(large=3.0, small=0.88), vm_gib=16,
              margin_gib=2)
DISK = dict(vm_min_gib=S.MIN_VM_GB, host_min_gib=S.MIN_HOST_GB, work_free_min_above_reserve_gib=6)
SERVING = dict(llama_cpp_commit='4fea119de30f6a923992780f6fd5ccb0bee5d47d',
               llama_server=PR.LLAMA_SERVER.relative_to(PR.ROOT).as_posix(),
               flags=['-ngl', '99', '-np', '1', '-c', '16384'], host='127.0.0.1', build_info_contains='4fea119',
               conversion_record=PR.CONV.relative_to(PR.ROOT).as_posix(),
               conversion_record_sha256='7e165c220b2d4f045375a98e3edc35ccc5a0133221bfd8bff18c397cbab61c1f',
               non_task_generation_probes=0)
EVALUATOR = dict(commit=S.EVALUATOR_COMMIT, python=S.VENV_PY)
RUNTIME = dict(episode_python=PR.MSWEA_PY.relative_to(PR.ROOT).as_posix(), grader_python=S.VENV_PY,
               orchestrator='experiments/v2_agent/req011_pair.py', entry='experiments/v2_agent/req011_entry.py',
               grader='experiments/v2_agent/req011_grade.py')
OUTPUTS = dict(raw='work/runs/req011_competence_20260924', published='results/v2_agent/req011_competence_20260924',
               pause_file='work/REQ011_PAUSE', private_receipts=A.PRIVATE_RECEIPTS_REL)
TEXT_KEYS = ('declared_rules', 'interpretations', 'inherited_labels', 'semantics_differences', 'scope')
SOURCES = tuple('experiments/v2_agent/' + n for n in (
    'pilot_episode.py', 'pilot_runner.py', 'pilot_cohort.py', 'workspace_capture.py', 'cue_episode.py',
    'cue_transport.py', 'cue_terminal.py', 'cue_admission.py', 'cue_cohort.py', 'cue_detector.py', 'exit_capture.py',
    'request_receipt.py', 'grade_submission.py', 'grade_identity.py', 'req011_pair.py', 'req011_entry.py',
    'req011_grade.py')) + tuple('experiments/v2_adapter/' + n for n in (
        'grading_conformance.py', 'qualify_instances.py', 'req010_sentinel.py')) + (
    MANIFEST_REL, S.LOCK, SERVING['conversion_record'], REQ010_SUMMARY_REL)
SANDBOX_ENV_KEYS = frozenset(('PAGER', 'MANPAGER', 'LESS', 'PIP_PROGRESS_BAR', 'TQDM_DISABLE'))
SANDBOX_KEYS = frozenset(('env', 'image', 'cwd', 'executable', 'timeout', 'run_args'))
OWN_SCRIPTS = ('req011_pair.py', 'req011_entry.py', 'req011_grade.py')
MSWEA_GLOBAL_ENV = Path.home() / 'Library/Application Support/mini-swe-agent/.env'
WATCHDOG = dict(poll_s=5, grace_s=S.KILL_GRACE_SECONDS, ready_timeout_s=60)
AGENT_EXITS = ('Submitted', 'LimitsExceeded', 'RepeatedFormatError', 'FormatError')   # mini-swe-agent 04d809c
TIME_EXITS = ('TimeExceeded', 'EpisodeDeadline')


class Gate(RuntimeError):
    """A predeclared gate failure: it stops the pair (remaining assignments not started); never a substitution."""


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def write_raw(path, obj):
    """Raw (unsanitized) write-once JSON under the git-ignored work/ tree; returns its sha256."""
    text = json.dumps(obj, indent=1, default=str) + '\n'
    with open(path, 'x') as fh:
        fh.write(text)
    return S.sha_bytes(text.encode())


# ------------------------------------------------------------------ manifest binding
def assignment_row(order, backend, conv):
    be, q = conv['backends'][backend], conv['backends'][backend]['q4_k_m']
    return dict(order=order, assignment_id='req011-%d-%s' % (order, backend), backend=backend, arm='baseline',
                model=be['repository'], model_commit=be['source_commit'], port=PR.PORTS[backend],
                alias=PR.ALIAS[backend], gguf=q['file'], gguf_sha256=q['sha256'], gguf_bytes=q['bytes'])


def expected_manifest(conv, req010):
    """The manifest's machine-checked sections, from the bound code, pilot_runner, the conversion record and the
    REQ-010 summary (the instance/env/base image IDs it recorded after qualification)."""
    return dict(request=REQUEST, lead_commit='a0e8379', source_commit='10be146', instance_id=S.TARGET,
                images={k: dict(key=v['key'], id=v['digest']) for k, v in req010['images_after'].items()},
                assignments=[assignment_row(1, 'large', conv), assignment_row(2, 'small', conv)],
                settings=dict(PR.FROZEN_SETTINGS, context_per_slot=16384, configuration_binding='yaml-v1',
                              workspace_binding='wc2', template_platform_binding='cp2',
                              mini_swe_agent=PR.HARNESS_PIN, default_yaml_sha256=PR.DEFAULT_YAML_PIN),
                serving=SERVING, evaluator=EVALUATOR, caps=CAPS, memory_rule=MEMORY, disk_rule=DISK, watchdog=WATCHDOG,
                runtime=RUNTIME, outputs=OUTPUTS)


def manifest_problems(manifest, conv, req010):
    expected = expected_manifest(conv, req010)
    problems = ['manifest %s differs from the bound value' % k for k in expected if manifest.get(k) != expected[k]]
    problems += ['manifest %s is missing' % k for k in TEXT_KEYS if not manifest.get(k)]
    if req010.get('status') != 'QUALIFIED' or req010.get('target') != S.TARGET:
        problems.append('the REQ-010 summary does not record %s as QUALIFIED' % S.TARGET)
    return problems


# ------------------------------------------------------------------ admission probes (each returns (ok, detail))
def probe_manifest(root):
    raw = (root / MANIFEST_REL).read_bytes()
    conv_path = root / SERVING['conversion_record']
    problems = manifest_problems(json.loads(raw), json.loads(conv_path.read_bytes()),
                                 json.loads((root / REQ010_SUMMARY_REL).read_bytes()))
    if S.sha_file(conv_path) != SERVING['conversion_record_sha256']:
        problems.append('conversion record sha256 differs from the bound value')
    return not problems, OrderedDict(manifest=MANIFEST_REL, manifest_sha256=S.sha_bytes(raw), problems=problems)


def probe_sources(root, run=S.sh, base=S.probe_sources, compute_binding=None):
    ok, d = base(root)
    srcs = OrderedDict()
    for s in SOURCES:
        srcs[s] = OrderedDict(sha256=S.sha_file(root / s),
                              tracked=run(['git', '-C', str(root), 'ls-files', '--error-unmatch', s])[0] == 0,
                              unchanged_from_head=run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--', s])[0] == 0)
    binding, problems = (compute_binding or (lambda r: A.compute_binding(A.Layout(r))))(root)
    d.update(req011_sources=srcs, cue_binding_problems=problems, cue_binding_sha256=binding.get('binding_sha256'),
             cue_runtime={k: binding['runtime'].get(k) for k in ('sdk_traced_files', 'mini_swe_agent_sources')})
    return ok and not problems and all(v['tracked'] and v['unchanged_from_head'] for v in srcs.values()), d


def probe_images(root, pins, run=S.sh):
    ok, d = S.probe_images(root, run=run)
    d['pinned'] = pins
    d['equal_to_pins'] = {k: d['local_images'][k]['key'] == pins[k]['key'] and d['local_images'][k]['digest'] ==
                          pins[k]['id'] for k in ('base', 'env', 'instance')}
    return ok and all(d['equal_to_pins'].values()), d


def probe_conflicts(root, run=S.sh):
    ok, d = S.probe_conflicts(root, run=run)
    rec = load_json(root / 'work/code_routing_servers.json')
    d['server_record'] = None if rec is None else OrderedDict(
        holder=rec.get('holder'), release_confirmed=rec.get('release_confirmed'), servers=rec.get('servers'))
    d['req011_pause_file_present'] = (root / OUTPUTS['pause_file']).exists()
    _, rows = S.process_table(run)
    mine = S.ancestors(rows, os.getpid()) | {os.getpid()}
    d['other_req011_processes'] = [pid for pid, _, argv in rows if pid not in mine
                                   and any(Path(x).name in OWN_SCRIPTS for x in argv[:3])]
    return (ok and rec is not None and rec.get('release_confirmed') is True and rec.get('servers') == []
            and not d['req011_pause_file_present'] and not d['other_req011_processes']), d


def sandbox_problems(environment):
    """The agent container config (PE.build_effective_config 'environment') must carry no host credentials."""
    problems = []
    if environment.get('forward_env', []) != []:
        problems.append('forward_env is not empty')
    if not set(environment.get('env', {})) <= SANDBOX_ENV_KEYS:
        problems.append('container env keys %s exceed the allowed set' % sorted(set(environment.get('env', {}))))
    if environment.get('run_args') != ['--rm', '--platform', 'linux/amd64']:
        problems.append('run_args %r are not exactly --rm --platform linux/amd64' % (environment.get('run_args'),))
    if set(environment) - SANDBOX_KEYS:
        problems.append('unexpected environment keys %s' % sorted(set(environment) - SANDBOX_KEYS))
    return problems


def probe_isolation(root, image_id, assignments):
    import yaml
    import pilot_episode as PE          # sets MSWEA_* as the frozen driver does; the entry sets them again
    cfg_path = PE.MSWEA / 'src/minisweagent/config/default.yaml'
    problems = [] if PE.sha(cfg_path.read_bytes()) == PE.DEFAULT_YAML_SHA else ['default.yaml differs from the pin']
    cfg = yaml.safe_load(cfg_path.read_text())
    for a in assignments:
        problems += sandbox_problems(PE.build_effective_config(cfg, alias=a['alias'], port=a['port'],
                                                               image_id=image_id)['environment'])
    _, removed = S.scrub_env(dict(os.environ))
    d = OrderedDict(sandbox_problems=problems, child_env_credential_like_variables_removed=removed,
                    proxies=sorted(k for k in urllib.request.getproxies() if k != 'no'),
                    litellm_or_handler_env=sorted(k for k in os.environ if k.startswith('LITELLM_')
                                                  or k == 'EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER'),
                    mini_swe_agent_global_env_present=MSWEA_GLOBAL_ENV.exists(),
                    networking='agent containers use the docker default bridge network; recorded, not restricted')
    return not (problems or d['proxies'] or d['litellm_or_handler_env'] or d['mini_swe_agent_global_env_present']), d


def probe_disk(root, run=S.sh):
    ok, d = S.probe_disk(root, run=run)
    d['work_free_space_refusal'] = A.free_space_check(root / 'work', host_reserve_bytes=CAPS['host_reserve_bytes'])
    return ok and d['work_free_space_refusal'] is None, d


def probe_models(root, assignments):
    conv = json.loads((root / SERVING['conversion_record']).read_text())
    models = OrderedDict((a['backend'], OrderedDict(file=a['gguf'], sha256=PR.sha_file(root / a['gguf']),
                                                    expected=a['gguf_sha256'])) for a in assignments)
    tools = OrderedDict((n, OrderedDict(sha256=S.sha_file(root / t['path']), expected=t['sha256']))
                        for n, t in sorted(conv['llama_cpp']['tools'].items())
                        if n == 'llama-server' or n.endswith('.dylib'))
    ok = len(tools) == 11 and all(v['sha256'] == v['expected'] for v in list(models.values()) + list(tools.values()))
    return ok, OrderedDict(models=models, llama_cpp_tools=tools)


def memory_free_pct(run=S.sh):
    rc, out, _ = run(['memory_pressure'], timeout=30)
    m = re.search(r'System-wide memory free percentage:\s*(\d+)%', out or '')
    return int(m.group(1)) if rc == 0 and m else None


def probe_memory(root, assignments, run=S.sh):
    free = memory_free_pct(run)
    rc, out, _ = run(['sysctl', '-n', 'hw.memsize'])
    memsize = int(out.strip()) if rc == 0 and out.strip().isdigit() else None
    projection = OrderedDict((a['backend'], a['gguf_bytes'] + int((MEMORY['kv_gib'][a['backend']] + MEMORY['vm_gib'])
                                                                  * GiB)) for a in assignments)
    limit = None if memsize is None else memsize - MEMORY['margin_gib'] * GiB
    d = OrderedDict(memory_free_pct=free, hw_memsize=memsize, projection_bytes=projection, projection_limit_bytes=limit,
                    swap=run(['sysctl', '-n', 'vm.swapusage'])[1].strip(), rule=MEMORY)
    return (free is not None and free >= MEMORY['admission_min_free_pct'] and limit is not None
            and all(v <= limit for v in projection.values())), d


def admission_probes(manifest):
    pins, queue = manifest['images'], manifest['assignments']
    return OrderedDict(manifest=probe_manifest, sources=probe_sources, runtime=S.probe_runtime,
                       images=lambda root: probe_images(root, pins), conflicts=probe_conflicts,
                       isolation=lambda root: probe_isolation(root, pins['instance']['id'], queue),
                       disk=probe_disk, models=lambda root: probe_models(root, queue),
                       memory=lambda root: probe_memory(root, queue))


# ------------------------------------------------------------------ serving
class Servers(PR.Servers):
    """pilot_runner.Servers unchanged; the ownership record it writes is re-labelled for DTR-REQ-011."""

    def _record(self):
        super()._record()
        rec = json.loads(PR.SERVERS.read_text())
        rec['holder'] = HOLDER
        tmp = PR.SERVERS.with_suffix('.tmp')
        tmp.write_text(json.dumps(rec, indent=1) + '\n')
        os.replace(tmp, PR.SERVERS)


def served_problems(props, models, listener, pid, *, gguf, alias):
    problems = []
    if props.get('model_path') != gguf:
        problems.append('/props model_path %r is not the hashed file' % props.get('model_path'))
    if props.get('model_alias') != alias:
        problems.append('/props model_alias %r' % props.get('model_alias'))
    if SERVING['build_info_contains'] not in str(props.get('build_info')):
        problems.append('/props build_info %r' % props.get('build_info'))
    if props.get('total_slots') != 1 or (props.get('default_generation_settings') or {}).get('n_ctx') != 16384:
        problems.append('/props slots/context differ from 1 x 16384')
    if alias not in [m.get('id') for m in models.get('data') or [] if isinstance(m, dict)]:
        problems.append('/v1/models does not list the alias')
    if listener != pid:
        problems.append('port listener %r is not the server PID %r' % (listener, pid))
    return problems


def listener_pid(port, run=S.sh):
    """pilot_runner.listener_pid with a subprocess timeout (None: no listener or unknown; a list: several)."""
    rc, out, _ = run(['lsof', '-nP', '-iTCP:%d' % port, '-sTCP:LISTEN', '-t'], timeout=30)
    pids = [int(x) for x in out.split() if x.isdigit()] if rc in (0, 1) else []
    return pids[0] if len(pids) == 1 else (None if not pids else pids)


def check_served(servers, a, root=ROOT, get=None, run=S.sh):
    """GET-only identity checks after load (no generation request); every host probe has a timeout."""
    if get is None:
        import requests
        get = lambda url: requests.get(url, timeout=10).json()  # noqa: E731
    base = 'http://%s:%d' % (SERVING['host'], a['port'])
    props, models = get(base + '/props'), get(base + '/v1/models')
    pid = servers.live['pid']
    problems = served_problems(props, models, listener_pid(a['port'], run), pid, gguf=str(root / a['gguf']),
                               alias=a['alias'])
    free = memory_free_pct(run)
    if free is None or free < MEMORY['post_load_min_free_pct']:
        problems.append('post-load memory free %r%% is below %d%%' % (free, MEMORY['post_load_min_free_pct']))
    checks = OrderedDict((k, props.get(k)) for k in ('model_path', 'model_alias', 'model_ftype', 'build_info',
                                                     'total_slots'))
    checks.update(n_ctx=(props.get('default_generation_settings') or {}).get('n_ctx'),
                  chat_template_sha256=S.sha_bytes(str(props.get('chat_template', '')).encode()),
                  v1_models_ids=[m.get('id') for m in models.get('data') or [] if isinstance(m, dict)],
                  server_pid=pid, memory_free_pct=free,
                  swap=run(['sysctl', '-n', 'vm.swapusage'], timeout=30)[1].strip(),
                  rss_kb=(lambda o: int(o) if o.isdigit() else None)(
                      run(['ps', '-o', 'rss=', '-p', str(pid)], timeout=30)[1].strip()))
    return checks, problems


def make_serve(servers, ctx):
    def serve(a):
        wd = ctx.get('watchdog')
        if not ctx.get('watchdog_ready') or wd is None or wd.poll() is not None:
            raise Gate('the server watchdog is not running: no server is started without it')
        try:
            load = servers.serve(a['backend'])
            checks, problems = check_served(servers, a, ctx['root'])
        except Exception as e:  # noqa: BLE001  a serving failure is a predeclared gate, never a substitution
            ctx['served'][a['backend']] = OrderedDict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
            raise Gate('serving %s failed (%s)' % (a['backend'], type(e).__name__))
        live = servers.live
        ctx['served'][a['backend']] = OrderedDict(load=load, checks=checks, problems=problems)
        ctx['served_arg'] = dict(model_file=live['model_file'], model_sha256=live['model_sha256'],
                                 server_pid=live['pid'], server_started_utc=live['started_utc'],
                                 llama_cpp=SERVING['llama_cpp_commit'], model_path=checks['model_path'],
                                 build_info=checks['build_info'])
        if problems:
            raise Gate('served identity/memory check failed for %s: %s' % (a['backend'], '; '.join(problems)))
    return serve


def stop_server(servers, ctx):
    try:
        servers.stop()
    except Exception as e:  # noqa: BLE001  recorded; grading needs no server; the watchdog stays armed
        ctx['summary'].setdefault('server_stop_errors', []).append('%s: %s' % (type(e).__name__, str(e)[:300]))
    ctx['summary']['server_events'] = servers.events


# ------------------------------------------------------------------ server watchdog (a separate process)
def live_args(pid, run=S.sh):
    rc, out, _ = run(['ps', '-ww', '-o', 'args=', '-p', str(pid)], timeout=10)
    return out.strip() if rc == 0 and out.strip() else None


def is_recorded_server(server, root, run=S.sh):
    """The live process at the recorded PID runs exactly the recorded llama-server command line (model path, alias,
    port; the ownership record stores it with the repository prefix removed)."""
    cmd = server.get('cmd') if isinstance(server.get('cmd'), str) else ''
    args = live_args(server['pid'], run) if type(server.get('pid')) is int else None
    return args is not None and args.replace(str(root) + '/', '') == cmd and '--port %s' % server.get('port') in cmd


def stop_recorded_servers(cfg, reason, run=S.sh, clock=time.time, sleep=time.sleep):
    """Stop (SIGTERM, grace, SIGKILL) each server of the ownership record, only if the record is held by DTR-REQ-011
    and the live process is exactly the recorded command; nothing else is ever signalled. After the parent died, a
    confirmed stop also releases the record."""
    rec = load_json(cfg['servers_record'])
    out = OrderedDict(request=REQUEST, reason=reason, utc=S.utc(clock()), watchdog_pid=os.getpid(),
                      record_holder=(rec or {}).get('holder'), servers=[], record_released=False)
    if not rec or rec.get('holder') != cfg['holder']:
        out['action'] = 'none: the ownership record is not held by %s' % REQUEST
        return out
    for s in rec.get('servers') or []:
        row = OrderedDict(pid=s.get('pid'), port=s.get('port'), matched=is_recorded_server(s, cfg['root'], run),
                          signals=[])
        for sig, wait in ((signal.SIGTERM, cfg['grace_s']), (signal.SIGKILL, 10)) if row['matched'] else ():
            if not is_recorded_server(s, cfg['root'], run):
                break
            try:
                os.kill(s['pid'], sig)
            except ProcessLookupError:
                break
            row['signals'].append(signal.Signals(sig).name)
            end = clock() + wait
            while clock() < end and is_recorded_server(s, cfg['root'], run):
                sleep(0.25)
        row['recorded_command_still_running'] = is_recorded_server(s, cfg['root'], run)
        out['servers'].append(row)
    out['action'] = 'stopped' if any(r['signals'] for r in out['servers']) else 'none: no live recorded server'
    if reason == 'parent process gone' and out['servers'] and all(
            r['matched'] and not r['recorded_command_still_running'] for r in out['servers']):
        rec.update(servers=[], release_confirmed=not rec.get('unconfirmed_episode_pids')
                   and not rec.get('unconfirmed_container_runs'))
        rec.setdefault('events', []).append(dict(event='stopped_by_watchdog', reason=reason, utc=out['utc'],
                                                 pids=[r['pid'] for r in out['servers']]))
        tmp = Path(cfg['servers_record']).with_suffix('.watchdog.tmp')
        tmp.write_text(json.dumps(rec, indent=1) + '\n')
        os.replace(tmp, cfg['servers_record'])
        out['record_released'] = rec['release_confirmed']
    return out


def watchdog(cfg_path, clock=time.time, sleep=time.sleep, getppid=os.getppid, run=S.sh):
    """Runs in its own session: when the launching parent is gone (re-parented) or the pair deadline passed, stop the
    recorded server and exit. It holds no model, sends no request and signals nothing but the recorded server."""
    cfg = json.loads(Path(cfg_path).read_text())
    out = Path(cfg['out'])
    write_raw(out / 'watchdog_ready.json', dict(request=REQUEST, watchdog_pid=os.getpid(), parent_pid=cfg['parent_pid'],
                                                utc=S.utc(clock())))
    while True:
        reason = ('parent process gone' if getppid() != cfg['parent_pid'] else
                  'pair deadline passed' if clock() >= cfg['deadline'] else None)
        if reason:
            break
        sleep(cfg['poll_s'])
    write_raw(out / 'watchdog_action.json', stop_recorded_servers(cfg, reason, run, clock, sleep))
    return 0


def spawn_watchdog(raw, deadline, env, *, servers_record=PR.SERVERS, root=PR.ROOT, python=sys.executable,
                   popen=subprocess.Popen, clock=time.time, **overrides):
    """Start the watchdog in its own session and wait (wall clock) for its readiness record; returns (proc, ready)."""
    w = dict(WATCHDOG, **overrides)
    cfg_path = Path(raw) / 'watchdog_config.json'
    write_raw(cfg_path, dict(request=REQUEST, parent_pid=os.getpid(), deadline=deadline, holder=HOLDER, out=str(raw),
                             servers_record=str(servers_record), root=str(root), poll_s=w['poll_s'],
                             grace_s=w['grace_s']))
    with open(Path(raw) / 'watchdog_stdout.txt', 'x') as log:
        p = popen([str(python), str(Path(__file__).resolve()), '--watchdog', str(cfg_path)], cwd=str(ROOT), env=env,
                  start_new_session=True, stdout=log, stderr=subprocess.STDOUT)
    end = clock() + w['ready_timeout_s']
    while clock() < end and p.poll() is None:
        ready = load_json(Path(raw) / 'watchdog_ready.json')
        if ready and ready.get('watchdog_pid') == p.pid and ready.get('parent_pid') == os.getpid():
            return p, True
        time.sleep(0.2)
    return p, False


def release_watchdog(p, servers):
    """Terminate the watchdog only once no server of ours is live; otherwise it stays armed past this process."""
    if p is None:
        return OrderedDict(started=False)
    if p.poll() is None and servers.live is None:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=10)
    return OrderedDict(started=True, pid=p.pid, returncode=p.poll(), left_armed=p.poll() is None)


# ------------------------------------------------------------------ ledger, schedule, accounting
class Ledger:
    """Append-only JSONL, one fsync'd line per event. A start is written before dispatch, an end after the child
    exits. A start without an end is 'interrupted'; an assignment with any record is never dispatched again."""

    def __init__(self, path, clock=time.time):
        self.path, self.clock = Path(path), clock

    def events(self):
        return [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()] if self.path.exists() else []

    def _append(self, event):
        with open(self.path, 'a') as fh:
            fh.write(json.dumps(dict(event, request=REQUEST, utc=S.utc(self.clock())), sort_keys=True) + '\n')
            fh.flush()
            os.fsync(fh.fileno())

    def start(self, order, **fields):
        if any(e.get('order') == order for e in self.events()):
            raise Gate('assignment %d already has a ledger record: never re-dispatched' % order)
        self._append(dict(fields, event='start', order=order))

    def end(self, order, state, **fields):
        self._append(dict(fields, event='end', order=order, state=state))

    def states(self):
        out = {}
        for e in self.events():
            out[e['order']] = dict(run_id=e.get('run_id'), state='interrupted' if e['event'] == 'start' else e['state'])
        return out


def fits(now, pair_deadline, load, caps=CAPS):
    """An episode starts only if its load, full wall, child cleanup grace, the parent's wait slack and the server
    reserve end before the grading floor (time-based, never outcome-based)."""
    return (now + load + caps['episode_wall_s'] + caps['child_cleanup_grace_s'] + caps['child_wait_slack_s']
            + caps['server_cleanup_reserve_s'] <= pair_deadline - caps['grading_floor_s'])


def request_limit(counted_before, caps=CAPS):
    return max(0, min(caps['per_episode_physical'], caps['max_physical_requests'] - counted_before))


def account(episode, caps=CAPS):
    """cue_admission.account_requests over the episode's reported physical_requests (unknown/invalid reserve 48)."""
    value = episode.get('physical_requests') if isinstance(episode, dict) else None
    reported, reported_raw, counted, accounting = A.account_requests(value, 0, caps['per_episode_physical'])
    return OrderedDict(reported=reported, reported_raw=reported_raw, counted=counted, accounting=accounting)


def run_episodes(queue, pair_deadline, serve, run_one, records, *, clock=time.time, pause=None, caps=CAPS):
    """Episodes in manifest order, each row appended to `records` before it runs. serve(a) raises Gate;
    run_one(a, counted_before, row) fills the row in place and returns a gate reason or None. A gate or the time rule
    stops the pair; an episode's outcome never does. Returns the stop reason (None when all were dispatched)."""
    counted, stop = 0, None
    for a in queue:
        rec = OrderedDict((k, a[k]) for k in ('order', 'assignment_id', 'backend', 'alias', 'port'))
        records.append(rec)
        if stop is None and pause is not None and Path(pause).exists():
            stop = 'paused (%s present)' % Path(pause).name
        if stop is None and not fits(clock(), pair_deadline, caps['episode_load_allowance_s'], caps):
            stop = 'pair cap'
        if stop is None:
            try:
                serve(a)
            except Gate as e:
                stop = 'gate: %s' % e
        if stop is None and not fits(clock(), pair_deadline, 0, caps):
            stop = 'pair cap (after load)'
        if stop is not None:
            rec.update(state='not_started: ' + stop, request_accounting=OrderedDict(counted=0, accounting='not_started'))
            continue
        gate = run_one(a, counted, rec)
        counted += rec['request_accounting']['counted']
        if gate:
            stop = 'gate: %s' % gate
    return stop


# ------------------------------------------------------------------ one episode (parent side)
def remove_containers(refs, run=S.sh, env=None, deadline=None, clock=time.time):
    """docker rm -f of exactly these container IDs/names, only while still listed; then a relist. With a deadline each
    docker call's timeout shrinks with the time left (never below 5 s)."""
    refs = [r for r in refs if r]

    def limit(default):
        return default if deadline is None else max(5, min(default, (deadline - clock()) / 3))

    def listed():
        rc, out, _ = run(['docker', 'ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.Names}}'], env=env,
                         timeout=limit(30))
        return [r for r in refs if r in out.split()] if rc == 0 else None
    found = listed() if refs else []
    rm_rc = run(['docker', 'rm', '-f'] + found, env=env, timeout=limit(60))[0] if found else None
    remaining = listed() if found else found
    return OrderedDict(refs=refs, found=found, rm_rc=rm_rc, remaining=remaining, complete=remaining == [])


def settle(p, run_dir, run_id, ctx):
    """Kill the child's whole process group if anything of it is left; remove only the recorded container; record (never
    remove) any other mini-swe-agent container still listed."""
    out = OrderedDict(child_returncode=None, process_group_gone=True)
    if p is not None:
        if p.poll() is None or S.group_members(p.pid) != []:
            out['process_group_gone'] = S.kill_group(p.pid, reap=p.poll)
        out['child_returncode'] = p.poll()
    own = load_json(run_dir / 'container_ownership.json') or {}
    cid = own.get('container_id') if own.get('run_id') == run_id else None
    out['owned_container'] = cid
    out['container_removal'] = remove_containers([cid] if cid else [], run=ctx['run'], env=ctx['env'],
                                                 deadline=ctx['pair_deadline'], clock=ctx['clock'])
    rc, listing, _ = ctx['run'](['docker', 'ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.Names}}'], env=ctx['env'],
                                timeout=max(5, min(30, (ctx['pair_deadline'] - ctx['clock']()) / 3)))
    out['minisweagent_containers_listed_after'] = None if rc != 0 else [
        line.split()[1] for line in listing.splitlines() if len(line.split()) > 1
        and line.split()[1].startswith('minisweagent-')]
    return out


def make_episode_runner(ctx, caps=CAPS):
    backstops = ctx.setdefault('backstops', OrderedDict())

    def run(a, counted_before, rec):
        rec.update(counted_before=counted_before, request_limit=request_limit(counted_before, caps))
        try:
            if a['order'] in ctx['ledger'].states():
                raise Gate('assignment %d already has a ledger record: never re-dispatched' % a['order'])
            run_id, run_dir = WC.new_run_dir(ctx['raw'], S.TARGET, a['backend'], 'req011')
            control = ctx['raw'] / 'control' / run_id
            control.mkdir(parents=True, exist_ok=False)
            now = ctx['clock']()
            ns = dict(instance=S.TARGET, backend=a['backend'], arm='baseline', position=a['order'], port=a['port'],
                      alias=a['alias'], run_dir=str(run_dir), run_id=run_id, expected_image=ctx['image_id'],
                      served=json.dumps(ctx['served_arg'], sort_keys=True),
                      episode_deadline=now + caps['episode_wall_s'],
                      block_deadline=ctx['pair_deadline'] - caps['grading_floor_s'], counted_before=counted_before,
                      request_limit=rec['request_limit'], host_reserve_bytes=caps['host_reserve_bytes'])
            WC.write_once(control / 'entry.json', json.dumps(dict(
                request=REQUEST, namespace=ns, binding_sha256=ctx['manifest_sha256'], assignment_id=a['assignment_id'],
                model_sha256=a['gguf_sha256'], admitted_sources=ctx['sources'], runtime=ctx['runtime']), indent=1) + '\n')
            ctx['ledger'].start(a['order'], run_id=run_id, assignment_id=a['assignment_id'])
        except (OSError, ValueError, Gate) as e:
            rec.update(state='not_started: gate: record not written',
                       request_accounting=OrderedDict(counted=0, accounting='not_started'))
            return 'a record could not be written durably before dispatch: %s' % str(e)[:200]
        rec.update(run_id=run_id, started_utc=S.utc(now), episode_deadline_utc=S.utc(ns['episode_deadline']),
                   state='interrupted')
        p, spawned, key = None, {}, 'settle episode %d' % a['order']
        backstops[key] = lambda: rec.update(settle(spawned.get('p'), run_dir, run_id, ctx), settle_backstop=True)
        try:
            with open(control / 'child_stdout.txt', 'x') as log:
                p = spawned['p'] = ctx['popen']([str(ctx['python']), str(ctx['entry']), str(control / 'entry.json')],
                                                cwd=str(ctx['root']), env=ctx['env'], start_new_session=True,
                                                stdout=log, stderr=subprocess.STDOUT)
                try:
                    S.wait_wall(p, ns['episode_deadline'] + caps['child_cleanup_grace_s'] + caps['child_wait_slack_s'],
                                clock=ctx['clock'])
                    rec['state'] = 'completed'
                except subprocess.TimeoutExpired:
                    rec['state'] = 'killed'
        finally:
            rec.update(settle(p, run_dir, run_id, ctx))
            backstops.pop(key, None)                 # a first signal inside settle leaves it for run_pair's retry
            if rec['state'] == 'completed' and not (run_dir / 'episode.json').exists():
                rec['state'] = 'exited_without_episode_record'
            rec['ended_utc'] = S.utc(ctx['clock']())
            ctx['ledger'].end(a['order'], state=rec['state'], run_id=run_id)
        rec['request_accounting'] = account(load_json(run_dir / 'episode.json'), caps)
        if (control / 'entry_refused.json').exists():
            return 'the entry refused admission of the running code'
        if not rec['process_group_gone']:
            return 'episode process-group termination unconfirmed'
        if not rec['container_removal']['complete']:
            return 'episode-owned container removal unconfirmed'
        return None
    return run


# ------------------------------------------------------------------ grading (parent side)
def evaluator_run_ids(run_dir, caps=CAPS):
    try:
        root = GI.evaluator_run_id(load_json(run_dir / 'episode.json') or {}, (run_dir / 'submission.diff').read_text())
    except (GI.IntegrityRefusal, OSError, ValueError):
        return []
    return ['%s-a%d' % (root, n) for n in range(1, caps['evaluator_max_attempts'] + 1)]


def evaluator_containers(run_dir, caps=CAPS):
    """Exactly the stock evaluator containers this run's grading can create (no other container name ever)."""
    return ['sweb.eval.%s.%s' % (S.TARGET, rid) for rid in evaluator_run_ids(run_dir, caps)]


GRADE_FIELDS = ('classification', 'grade_valid', 'evaluated', 'strict_outcome', 'operational_resolved',
                'upstream_resolved', 'reason')


def make_grader(ctx, caps=CAPS):
    """The grader is a session/process-group leader and its stock evaluator runs inside that group, so one group kill
    (at the pair cap, on an operator signal, or after a normal exit if anything is left) reaches all of it."""
    backstops = ctx.setdefault('backstops', OrderedDict())

    def contain(p, run_dir, evaluable):
        gone = S.kill_group(p.pid, reap=p.poll) if p.poll() is None or S.group_members(p.pid) != [] else True
        return gone, remove_containers(evaluator_containers(run_dir, caps) if evaluable else [], run=ctx['run'],
                                       env=ctx['env'], deadline=ctx['pair_deadline'], clock=ctx['clock'])

    def grade(rec):
        run_dir = ctx['raw'] / rec['run_id']
        if not (run_dir / 'episode.json').exists() or not (run_dir / 'submission.diff').exists():
            return OrderedDict(status='no grade: no episode record (%s)' % rec.get('state'))
        evaluable = ((load_json(run_dir / 'episode.json') or {}).get('exit_status') == 'Submitted'
                     and bool((run_dir / 'submission.diff').read_bytes().strip()))
        if evaluable and ctx['clock']() >= ctx['pair_deadline'] - caps['evaluator_end_reserve_s']:
            return OrderedDict(status='ungraded: pair cap (grading not started)', evaluable=True)
        control = ctx['raw'] / 'control' / rec['run_id']
        gpath = control / 'grade_control.json'
        WC.write_once(gpath, json.dumps(dict(
            request=REQUEST, run_dir=str(run_dir), work=str(ctx['raw'] / 'grading'), pair_deadline=ctx['pair_deadline'],
            image_pin=ctx['image_id'], admitted_sources=ctx['sources'], caps=caps), indent=1) + '\n')
        killed, key = False, 'grader %s' % rec['run_id']
        with open(control / 'grader_stdout.txt', 'x') as log:
            p = ctx['popen']([str(ctx['grader_python']), str(ctx['grader']), str(gpath)], cwd=str(ctx['root']),
                             env=ctx['env'], start_new_session=True, stdout=log, stderr=subprocess.STDOUT)
        backstops[key] = lambda: contain(p, run_dir, evaluable)
        try:
            S.wait_wall(p, ctx['pair_deadline'] - caps['evaluator_end_reserve_s'] + caps['grader_wait_slack_s'],
                        clock=ctx['clock'])
        except subprocess.TimeoutExpired:
            killed = True
        finally:
            gone, cleanup = contain(p, run_dir, evaluable)
            backstops.pop(key, None)
        result, grade_rec = load_json(control / 'grade_result.json'), load_json(run_dir / 'grade.json')
        if killed:
            status = 'ungraded: pair cap (grader killed at the pair cap)'
        else:
            status = (result or {}).get('status') or (
                'graded: %s (grader result record missing)' % grade_rec.get('classification') if grade_rec else
                'ungraded: grader exited without a result (returncode %s)' % p.returncode)
        out = OrderedDict(status=status, evaluable=evaluable, grader_killed=killed, grader_returncode=p.returncode,
                          grader_group_gone=gone, evaluator_container_cleanup=cleanup)
        if grade_rec and not killed:
            out.update((k, grade_rec.get(k)) for k in GRADE_FIELDS)
        elif grade_rec:                                    # a kill at the cap is never turned into a grade
            out['grade_record_written_before_the_kill'] = OrderedDict((k, grade_rec.get(k)) for k in GRADE_FIELDS)
        if result:
            out['grader'] = OrderedDict((k, result.get(k)) for k in ('status', 'reason', 'attempts', 'image_before',
                                                                     'image_after', 'image_after_equals_pin'))
        return out
    return grade


# ------------------------------------------------------------------ the real pair
def run_pair(ctx):
    root, raw, manifest = ctx['root'], ctx['raw'], ctx['manifest']
    clean, removed = S.scrub_env(dict(os.environ))
    os.environ.clear()
    os.environ.update(clean)                      # the llama-server child (Servers.serve) inherits this environment
    ctx['summary']['environment_variables_removed'] = removed
    ctx.update(env=S.scrub_env(S.docker_env())[0], run=S.sh, popen=subprocess.Popen,
               python=root / RUNTIME['episode_python'], entry=root / RUNTIME['entry'],
               grader_python=root / RUNTIME['grader_python'], grader=root / RUNTIME['grader'],
               image_id=manifest['images']['instance']['id'], served=OrderedDict())
    ctx['summary']['serving'] = ctx['served']
    try:
        awake = subprocess.Popen(['caffeinate', '-i', '-s', '-w', str(os.getpid())])
    except OSError:
        awake = None
    block = dict(block=1, block_start_utc=S.utc(ctx['start']), block_hard_end_utc=S.utc(ctx['pair_deadline']),
                 hard_deadline_epoch=ctx['pair_deadline'])
    servers = Servers(json.loads((root / SERVING['conversion_record']).read_text()), block, raw)
    backstops = ctx.setdefault('backstops', OrderedDict())
    try:
        ctx['watchdog'], ctx['watchdog_ready'] = spawn_watchdog(raw, ctx['pair_deadline'], dict(os.environ))
        try:
            stop = run_episodes(manifest['assignments'], ctx['pair_deadline'], make_serve(servers, ctx),
                                make_episode_runner(ctx), ctx['records'], clock=ctx['clock'],
                                pause=root / OUTPUTS['pause_file'])
        finally:
            stop_server(servers, ctx)
            ctx['summary']['watchdog'] = release_watchdog(ctx.get('watchdog'), servers)   # only once none is live
        grade, blocked = make_grader(ctx), None
        for rec in ctx['records']:
            if not rec.get('run_id'):
                rec['grade'] = OrderedDict(status='no grade: assignment not started')
            elif blocked:
                rec['grade'] = OrderedDict(status='ungraded: %s' % blocked)
            else:
                rec['grade'] = OrderedDict(status='ungraded: grading did not complete (interrupted or error)')
                rec['grade'] = grade(rec)
                if rec['grade'].get('grader_group_gone') is False:
                    blocked = 'an earlier grader process group was not confirmed gone (no concurrent evaluator)'
        return stop
    finally:                  # once a first signal has arrived later ones are ignored, so these retries run to the end
        for name, backstop in list(backstops.items()):
            try:
                backstop()
                ctx['summary'].setdefault('backstops_run', []).append(name)
            except Exception as e:  # noqa: BLE001  recorded
                ctx['summary'].setdefault('backstops_run', []).append('%s: %s: %s' % (name, type(e).__name__, e))
        if servers.live is not None:
            stop_server(servers, ctx)
        ctx['summary']['watchdog'] = release_watchdog(ctx.get('watchdog'), servers)
        if awake is not None:
            awake.terminate()


# ------------------------------------------------------------------ summary and publication
def token_totals(receipts_dir):
    """Server-reported usage summed over the public outcome receipts; unknown usage is counted, never 0."""
    sums, known, unknown = dict(prompt_tokens=0, completion_tokens=0), 0, 0
    for path in sorted(Path(receipts_dir).glob('*.outcome.json')):
        usage = (load_json(path) or {}).get('server_reported_usage') or {}
        if usage.get('usage_known'):
            known += 1
            for k in sums:
                sums[k] += usage[k]
        else:
            unknown += 1
    return OrderedDict(prompt_tokens=sums['prompt_tokens'] if known else None,
                       completion_tokens=sums['completion_tokens'] if known else None,
                       outcomes_with_known_usage=known, outcomes_with_unknown_usage=unknown)


def call9_facts(run_dir, control_dir):
    """Observable pre-action resources when call 9 was about to be sent (call9_history.json is written just before)."""
    hist = load_json(run_dir / 'call9_history.json')
    if not isinstance(hist, dict) or not isinstance(hist.get('captured_at'), (int, float)):
        return None
    ns = (load_json(control_dir / 'entry.json') or {}).get('namespace') or {}
    path, starts = run_dir / 'attempts.jsonl', []
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get('event') == 'start' and isinstance(row.get('t_start'), (int, float)):
            starts.append(row)
    t, before = hist['captured_at'], [r for r in starts if isinstance(r.get('call'), int) and r['call'] < 9]
    limit, deadline = ns.get('request_limit'), ns.get('episode_deadline')
    return OrderedDict(
        captured_utc=S.utc(t), message_count=len(hist.get('messages') or []), logical_calls_before=8,
        physical_attempts_before=len(before),
        request_budget_remaining=limit - len(before) if type(limit) is int else None,
        seconds_since_first_request=round(t - min(r['t_start'] for r in starts), 1) if starts else None,
        seconds_to_episode_deadline=round(deadline - t, 1) if isinstance(deadline, (int, float)) else None,
        source='call9_history.json captured_at and messages; attempts.jsonl start events; control entry.json')


def outcome_source(state, exit_status, eligible):
    """Descriptive: separates infrastructure/supervision non-submissions from agent-ended ones (never a grade)."""
    if eligible:
        return 'eligible_submission'
    if state != 'completed' or exit_status is None:
        return 'infrastructure_or_supervision'
    return 'agent' if exit_status in AGENT_EXITS else 'time_limit' if exit_status in TIME_EXITS else \
        'infrastructure_or_supervision'


def episode_facts(run_dir, run_id, root=ROOT, control_dir=None):
    ep, diag = load_json(run_dir / 'episode.json'), load_json(run_dir / 'exit_diagnostic.json')
    sub = run_dir / 'submission.diff'
    nonempty = bool(sub.read_bytes().strip()) if sub.exists() else None
    get = (lambda k: ep.get(k)) if ep else (lambda k: None)
    completeness = CT.read_only_completeness(root / OUTPUTS['private_receipts'] / run_id, run_dir / A.RECEIPTS_SUBDIR,
                                             cohort=A.COHORT, run_id=run_id)
    return OrderedDict(
        episode_record_present=ep is not None, exit_status=get('exit_status'), error=get('error'),
        logical_calls=get('logical_calls'), n_model_calls=get('n_model_calls'),
        physical_requests=get('physical_requests'), wall_seconds=get('wall_seconds'),
        server_reported_tokens=token_totals(run_dir / A.RECEIPTS_SUBDIR),
        submission_present=sub.exists(), submission_nonempty=nonempty, submission_sha256=get('submission_sha256'),
        eligible=get('exit_status') == 'Submitted' and nonempty is True,
        call9_reached=(run_dir / 'call9_history.json').exists(),
        call9_pre_action=call9_facts(run_dir, control_dir) if control_dir is not None else None,
        exit_diagnostic=None if diag is None else OrderedDict(
            status=diag.get('status'), changes_observed=diag.get('changes_observed'),
            sections=OrderedDict((k, (v or {}).get('state')) for k, v in (diag.get('sections') or {}).items()),
            failures=diag.get('failures')),
        terminal_phase=get('terminal_phase'), receipt_integrity=get('receipt_integrity'),
        storage_integrity=get('storage_integrity'), container_cleanup=get('container_cleanup'),
        receipts_completeness={k: v for k, v in completeness.items() if k not in ('note', 'attempt_keys')})


def publish(raw, pub, run_ids):
    """Sanitized copies (repository path -> '.', home -> '~'), raw and published sha256; *.log names get .txt."""
    manifest = OrderedDict()

    def put(src, rel):
        name = rel + ('.txt' if rel.endswith('.log') else '')
        data = src.read_bytes()
        clean = S.sanitize(data.decode('utf-8', 'replace')).encode()
        (pub / name).parent.mkdir(parents=True, exist_ok=True)
        with open(pub / name, 'xb') as fh:
            fh.write(clean)
        manifest[name] = OrderedDict(raw_sha256=S.sha_bytes(data), published_sha256=S.sha_bytes(clean),
                                     sanitized=clean != data)

    def tree(base, prefix):
        for p in sorted(base.rglob('*')) if base.is_dir() else []:
            if p.is_file() and not p.is_symlink():
                put(p, prefix + p.relative_to(base).as_posix())
    for name in ('admission.json', 'ledger.jsonl', 'pair_summary.json', 'watchdog_config.json', 'watchdog_ready.json',
                 'watchdog_stdout.txt', 'watchdog_action.json'):
        if (raw / name).exists():
            put(raw / name, name)
    for p in sorted(raw.glob('server_*.log')):
        put(p, p.name)
    for run_id in run_ids:
        tree(raw / run_id, run_id + '/')
        tree(raw / 'control' / run_id, run_id + '/control/')
    tree(raw / 'grading', 'grading/')
    S.write_json_x(pub / 'publication_manifest.json', manifest)
    hits = S.username_hits(pub)
    if hits:
        S.write_json_x(pub / 'USERNAME_FOUND.json', OrderedDict(files=hits, action='do not publish until redacted'))
    return manifest, hits


def finish(ctx, summary, manifest):
    """Complete every assignment's row (from the ledger when the run was cut short), write and publish."""
    root, raw, records, states = ctx['root'], ctx['raw'], ctx['records'], ctx['ledger'].states()
    seen = {r['order'] for r in records}
    records += [OrderedDict((k, a[k]) for k in ('order', 'assignment_id', 'backend', 'alias', 'port'))
                for a in manifest.get('assignments', []) if a['order'] not in seen]
    rows = []
    for r in sorted(records, key=lambda r: r['order']):
        row, st = OrderedDict(r), states.get(r['order'])
        if 'state' not in row or (st and st['state'] == 'interrupted'):
            row.update(run_id=(st or {}).get('run_id'), state=st['state'] if st else 'not_started: pair %s' % (
                (summary.get('status') or 'blocked').lower()))
        if 'request_accounting' not in row:
            row['request_accounting'] = account(load_json(raw / row['run_id'] / 'episode.json')) if row.get(
                'run_id') else OrderedDict(counted=0, accounting='not_started')
        if row.get('run_id') and (raw / row['run_id']).is_dir():
            try:                                            # one unreadable record never costs the summary
                row.update(episode_facts(raw / row['run_id'], row['run_id'], root, raw / 'control' / row['run_id']))
            except Exception as e:  # noqa: BLE001
                row['episode_facts_error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
        row['outcome_source'] = outcome_source(row.get('state'), row.get('exit_status'), row.get('eligible') is True)
        row.setdefault('grade', OrderedDict(status='no grade: %s' % (
            'assignment not started' if not row.get('run_id') else 'grading not reached (%s)' % summary.get('status'))))
        rows.append(row)
    ints = lambda k: sum(x[k] for x in rows if type(x.get(k)) is int)  # noqa: E731
    end = ctx['clock']()
    logical, physical = ints('logical_calls'), ints('physical_requests')
    counted = sum(x['request_accounting']['counted'] for x in rows)
    summary.update(
        finished_utc=S.utc(end), wall_seconds=round(end - ctx['start'], 1), pair_cap_s=CAPS['pair_wall_s'],
        within_cap=end - ctx['start'] <= CAPS['pair_wall_s'], assignments=rows,
        requests=OrderedDict(logical_reported_total=logical, physical_reported_total=physical,
                             physical_counted_total=counted, max_logical=CAPS['max_logical_requests'],
                             max_physical=CAPS['max_physical_requests'],
                             within_caps=logical <= CAPS['max_logical_requests']
                             and counted <= CAPS['max_physical_requests'], non_task_generation_requests=0),
        denominator='both assignments, whatever their state',
        outcome_sources=OrderedDict((k, sum(x['outcome_source'] == k for x in rows)) for k in (
            'eligible_submission', 'agent', 'time_limit', 'infrastructure_or_supervision')),
        outcome_source_rule='agent = %s; time_limit = %s; anything else (killed, interrupted, not started, no episode '
                            'record, InfrastructureStop, StartPreflightRefused, transport errors) = '
                            'infrastructure_or_supervision, which is not evidence about competence'
                            % (list(AGENT_EXITS), list(TIME_EXITS)),
        interpretations=manifest.get('interpretations'), inherited_labels=manifest.get('inherited_labels'),
        semantics_differences=manifest.get('semantics_differences'), scope=manifest.get('scope'),
        published=OUTPUTS['published'])
    write_raw(raw / 'pair_summary.json', summary)
    publish(raw, ctx['pub'], [r['run_id'] for r in rows if r.get('run_id') and (raw / r['run_id']).is_dir()])
    return summary


def main(argv=None, root=ROOT, probes=None, runner=None, clock=time.time):
    ap = argparse.ArgumentParser(description='DTR-REQ-011 fixed-backend DEVELOPMENT competence pair (single shot)')
    ap.add_argument('--admission-only', action='store_true', help='print the admission record; start nothing')
    ap.add_argument('--watchdog', metavar='CONFIG', help=argparse.SUPPRESS)   # internal: started by run_pair
    args = ap.parse_args(argv)
    if args.watchdog:
        return watchdog(args.watchdog)
    raw, pub = root / OUTPUTS['raw'], root / OUTPUTS['published']
    if not args.admission_only and (raw.exists() or pub.exists()):
        print('DTR-REQ-011 is single-shot: %s or %s already exists; no automatic resume or re-dispatch'
              % (OUTPUTS['raw'], OUTPUTS['published']), file=sys.stderr)
        return 3
    start = clock()
    manifest_bytes = (root / MANIFEST_REL).read_bytes()
    manifest = json.loads(manifest_bytes)
    adm = S.admission(root, probes if probes is not None else admission_probes(manifest))
    adm.update(request=REQUEST, manifest_file=MANIFEST_REL, manifest_sha256=S.sha_bytes(manifest_bytes),
               started_utc=S.utc(start), mode='admission-only' if args.admission_only else 'launch')
    if args.admission_only:
        print(json.dumps(S.sanitize(adm), indent=1, default=str))
        return 0 if adm['admitted'] else 1
    raw.mkdir(parents=True, exist_ok=False)
    pub.mkdir(parents=True, exist_ok=False)
    summary = OrderedDict(request=REQUEST, manifest=MANIFEST_REL, manifest_sha256=adm['manifest_sha256'],
                          admission_sha256=write_raw(raw / 'admission.json', adm), started_utc=S.utc(start),
                          pair_deadline_utc=S.utc(start + CAPS['pair_wall_s']), status=None, stop_reason=None,
                          interrupted_or_error=None)
    sources = ((adm.get('sources') or {}).get('detail') or {})
    ctx = dict(root=root, raw=raw, pub=pub, start=start, pair_deadline=start + CAPS['pair_wall_s'], clock=clock,
               manifest=manifest, manifest_sha256=adm['manifest_sha256'], summary=summary, records=[],
               ledger=Ledger(raw / 'ledger.jsonl', clock),
               sources={k: v['sha256'] for k, v in (sources.get('req011_sources') or {}).items()},
               runtime=sources.get('cue_runtime'))
    if not adm['admitted']:
        summary.update(status='BLOCKED', executed=False, failed_admission_checks=[
            k for k, v in adm.items() if isinstance(v, dict) and v.get('ok') is False])
        finish(ctx, summary, manifest)
        print(json.dumps(S.sanitize({k: summary[k] for k in ('status', 'failed_admission_checks')})))
        return 2
    old = {sig: signal.signal(sig, S.raise_interrupted) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        summary['stop_reason'] = (runner or run_pair)(ctx)
        summary['status'] = 'STOPPED' if summary['stop_reason'] else 'COMPLETED'
    except S.Interrupted as e:
        summary.update(status='INTERRUPTED', interrupted_or_error=str(e))
    except Exception as e:  # noqa: BLE001  recorded; the summary is still written
        summary.update(status='ERROR', interrupted_or_error='%s: %s' % (type(e).__name__, str(e)[:500]))
    finally:
        for sig in old:
            signal.signal(sig, signal.SIG_IGN)       # later signals never cut the records short
        try:
            finish(ctx, summary, manifest)
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
    print(json.dumps(S.sanitize({k: summary.get(k) for k in ('status', 'stop_reason', 'wall_seconds', 'within_cap')})))
    return 0


if __name__ == '__main__':
    sys.exit(main())
