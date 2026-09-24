"""DTR-REQ-013 (lead 702e58a, docs/theory_feedback_20260924_req012_decision.md): ONE Qwen2.5-Coder-14B DEVELOPMENT
discriminator episode on astropy__astropy-14598 under the unchanged configuration yaml-v1-repair1. It runs only after the
no-model step 1 and only if every gate passes, including the literal swap rule (>= 4 GiB unused at admission). The
committed manifest configs/v2_req013_14b_discriminator_20260924.json is the specification: its declared rules govern
this runner. The probe is not a success rate, not a paired comparison and not CONFIRM evidence.

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req013_pair.py --admission-only   (read-only)
    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req013_pair.py                    (the probe)

A thin layer over the committed REQ-012 runner (req012_pair.py, and through it req011_pair.py). Both are imported
read-only and never edited. It reuses their admission probes, the REQ-012 gate check, repair1 isolation, the queue,
episode supervision, grading and publication. Restated here are only the parts REQ-012 hard-codes: the manifest, the
14B assignment, the ownership holder, the watchdog launcher, the entry (req013_entry.py) and the run sequence. New
parts are the swap gate, the precondition and the step-1 check. The precondition is the passing REQ-012 gate record
plus a deterministic proof that the 14B repair1 configuration equals the 7B one apart from the model name and the port.
The live gate is not re-run.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (Path(__file__).resolve().parent, ROOT / 'experiments/v2_adapter'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req012_pair as P12  # noqa: E402  the committed REQ-012 runner, imported read-only

P11, R, PR, S, A = P12.P11, P12.R, P12.PR, P12.S, P12.A
GiB = P11.GiB
REQUEST = 'DTR-REQ-013'
MANIFEST_REL = 'configs/v2_req013_14b_discriminator_20260924.json'
LEAD_DECISION = 'docs/theory_feedback_20260924_req012_decision.md'
HOLDER = 'DTR-AgentEvals worker (DTR-REQ-013 14B discriminator)'
CAPS = dict(P12.CAPS)                                # identical to REQ-012 (the 14B load time needs no more; manifest)
RUNTIME = dict(P12.RUNTIME, orchestrator='experiments/v2_agent/req013_pair.py',
               entry='experiments/v2_agent/req013_entry.py')
OUTPUTS = dict(raw='work/runs/req013_14b_discriminator_20260924',
               published='results/v2_agent/req013_14b_discriminator_20260924', pause_file='work/REQ013_PAUSE',
               private_receipts=A.PRIVATE_RECEIPTS_REL)
NEW_SOURCES = ('experiments/v2_agent/req013_pair.py', 'experiments/v2_agent/req013_entry.py',
               'experiments/v2_agent/req013_reconcile.py', 'experiments/tools/req013_watchdog_check.py', MANIFEST_REL,
               'tests/test_req013_discriminator.py')
SOURCES = P12.SOURCES + NEW_SOURCES
OWN_SCRIPTS = ('req013_pair.py', 'req013_entry.py')
REQ012_GATE = P12.OUTPUTS['published'] + '/gate.json'
REQ012_SUMMARY = P12.OUTPUTS['published'] + '/probe/pair_summary.json'
PRIOR_RESULTS = OrderedDict(list(P12.PRIOR_RESULTS.items()) + [
    (REQ012_GATE, 'de29636aed8ef690b312b504b12fd8707874afed8dbec4d76e58c49264f807ab'),
    (REQ012_SUMMARY, '2d13b8c099555b1028de5099aebd94e88141dfd8a9a0d67f604c5996d6f0df76')])
STEP1 = OrderedDict(
    reconciliation=OUTPUTS['published'] + '/reconciliation.json',
    watchdog_host_check=OUTPUTS['published'] + '/watchdog_host_check.json',
    rule="both records present, tracked and unchanged from HEAD; the reconciliation says verified true and the "
         "watchdog host check says passed true",
    when="before the probe namespace (a refusal consumes nothing) and again as the admission probe 'step1'")
DIFF_ALLOWED = ('model.model_name', 'model.model_kwargs.api_base')
PRECONDITION = OrderedDict(
    req012_gate_record=REQ012_GATE, req012_gate_raw_record=P12.OUTPUTS['raw'] + '/gate/gate.json',
    req012_manifest=P12.MANIFEST_REL,
    req012_manifest_sha256='45afa0694a6965ecdd4dc0e7bcae04d0a379c7d0a2e14994a579521bfdc24cac',
    req012_entry='experiments/v2_agent/req012_entry.py',
    req012_entry_sha256='4daa8293156e6c8f9ed1e78bffd5ff497495e1b35e46cec1edb272aab6f21754',
    rule="req012_pair.probe_gate passes: the REQ-012 gate passed and was not interrupted, for the REQ-012 manifest "
         "sha256 and the current digest of every REQ-012 source, and its raw copy agrees. The gate record's repair1 "
         "section and prompt bytes equal this manifest's and the REQ-012 manifest's, and its configuration is "
         "yaml-v1-repair1. Its container environment ran the pinned instance image with run_args --rm --platform "
         "linux/amd64 --network none and observed NetworkMode none. Its image pins equal this manifest's, all three "
         "equal to the local images. The REQ-012 manifest and req012_entry.py have the sha256 bound here (the latter is "
         "the entry_source_sha256 of the REQ-012 probe's repair_record.json). The configuration proof passes. The "
         "live gate is not re-run",
    configuration_proof=OrderedDict(
        allowed_differences=list(DIFF_ALLOWED),
        rule="The pinned default.yaml (sha256 checked) goes through pilot_episode.build_effective_config for the "
             "REQ-012 7B assignment and for this manifest's 14B assignment (same image pin), then through "
             "req012_entry.repair_config. The two results are compared leaf by leaf. They must differ exactly at "
             "model.model_name ('openai/' + alias) and model.model_kwargs.api_base (the port) and nowhere else. The "
             "agent section (repair1 instance template, whose sha256 must equal "
             "prompt_bytes.instance_template_repair1_sha256), the environment (run_args with --network none) and every "
             "other model field are then identical. The backend, GGUF and model sha256 are assignment fields outside "
             "the configuration. The agent class, stall rule and fingerprint rule are req012_entry code, used unchanged "
             "by req013_entry.py"),
    when="before the probe namespace (a refusal consumes nothing) and again as the admission probe 'gate'")
SWAP = OrderedDict(
    command=['sysctl', '-n', 'vm.swapusage'], min_free_bytes=4 * GiB, min_free_gib=4,
    parse="exactly one 'free = <number><unit>' field, unit K, M or G read as KiB, MiB or GiB (sysctl prints M); "
          "a nonzero return code, no such field or more than one fails closed",
    rule="unused swap >= 4 GiB at admission (the literal lead rule), in addition to memory_rule",
    note="On macOS 'free' counts only unused space inside the swap files already allocated. The pager adds swap files "
         "on demand and does not shrink them promptly, so this can stay below 4 GiB while physical memory is ample",
    on_failure="status BLOCKED_FOR_CAPACITY; nothing is started and nothing is substituted; no job is killed or "
               "interrupted to create capacity",
    when="read-only before the probe namespace (a refusal there consumes nothing: exit 4), then again as the admission "
         "probe 'swap' (a failure there consumes the namespace like any failed admission)")
SWAP_FREE = re.compile(r'\bfree = ([0-9]+(?:\.[0-9]+)?)([KMG])\b')
UNITS = dict(K=1 << 10, M=1 << 20, G=1 << 30)


# ------------------------------------------------------------------ manifest binding
def expected_manifest(conv, req010):
    """The machine-checked sections, from the bound code (REQ-012 values via req012_pair, repair1 via req012_entry)."""
    m12 = P12.expected_manifest(conv, req010)
    return dict(request=REQUEST, lead_commit='702e58a', lead_decision=LEAD_DECISION, source_commit='8bcca8a',
                instance_id=S.TARGET, images=m12['images'],
                assignments=[dict(P11.assignment_row(1, 'large', conv), assignment_id='req013-1-large')],
                settings=m12['settings'], repair1=m12['repair1'], serving=P11.SERVING, evaluator=P11.EVALUATOR,
                caps=CAPS, memory_rule=P11.MEMORY, disk_rule=P11.DISK, swap_rule=SWAP, watchdog=P11.WATCHDOG,
                precondition=PRECONDITION, step1=STEP1, runtime=RUNTIME, outputs=OUTPUTS, prior_results=PRIOR_RESULTS)


SAME_AS_REQ012 = ('images', 'settings', 'repair1', 'prompt_bytes', 'serving', 'evaluator', 'caps', 'memory_rule',
                  'disk_rule', 'watchdog')


def manifest_problems(manifest, conv, req010, m11, m12, template=None):
    expected = expected_manifest(conv, req010)
    problems = ['manifest %s differs from the bound value' % k for k in expected if manifest.get(k) != expected[k]]
    problems += ['manifest %s is missing' % k for k in P11.TEXT_KEYS + ('prompt_bytes',) if not manifest.get(k)]
    problems += ['manifest %s differs from the REQ-012 manifest' % k for k in SAME_AS_REQ012
                 if manifest.get(k) != m12.get(k)]
    strip = lambda rows: [dict(a, assignment_id=None) for a in rows or []]  # noqa: E731
    if strip(manifest.get('assignments')) != strip([a for a in m11.get('assignments') or []
                                                     if a.get('backend') == 'large']):
        problems.append('the assignment is not the REQ-011 manifest 14B row (apart from its assignment_id)')
    if req010.get('status') != 'QUALIFIED' or req010.get('target') != S.TARGET:
        problems.append('the REQ-010 summary does not record %s as QUALIFIED' % S.TARGET)
    if template is not None and manifest.get('prompt_bytes') != R.prompt_bytes(template):
        problems.append('manifest prompt_bytes differ from the pinned default.yaml')
    return problems


def load(root, rel):
    return json.loads((root / rel).read_bytes())


def probe_manifest(root, template=None):
    raw = (root / MANIFEST_REL).read_bytes()
    template = R.frozen_template() if template is None else template
    problems = manifest_problems(json.loads(raw), load(root, P11.SERVING['conversion_record']),
                                 load(root, P11.REQ010_SUMMARY_REL), load(root, P11.MANIFEST_REL),
                                 load(root, P12.MANIFEST_REL), template)
    if S.sha_file(root / P11.SERVING['conversion_record']) != P11.SERVING['conversion_record_sha256']:
        problems.append('conversion record sha256 differs from the bound value')
    return not problems, OrderedDict(manifest=MANIFEST_REL, manifest_sha256=S.sha_bytes(raw), problems=problems,
                                     prompt_bytes=R.prompt_bytes(template))


# ------------------------------------------------------------------ the configuration proof and the precondition
MISSING = object()


def leaves(obj, path=()):
    """{dotted path: value} for every leaf of a JSON-like tree (an empty dict or any non-dict is a leaf)."""
    if isinstance(obj, dict) and obj:
        out = OrderedDict()
        for k, v in obj.items():
            out.update(leaves(v, path + (str(k),)))
        return out
    return OrderedDict([('.'.join(path), obj)])


def pinned_config():
    import yaml
    raw = (R.PE.MSWEA / 'src/minisweagent/config/default.yaml').read_bytes()
    if R.PE.sha(raw) != R.PE.DEFAULT_YAML_SHA:
        raise ValueError('default.yaml differs from the pin')
    return yaml.safe_load(raw.decode())


def config_proof(cfg, a12, a13, image_id, template_sha256, build=None):
    """(problems, record): the repair1 configs of the two assignments differ exactly at DIFF_ALLOWED."""
    build = build or R.PE.build_effective_config
    c12, c13 = (json.loads(json.dumps(R.repair_config(build(cfg, alias=a['alias'], port=a['port'], image_id=image_id))))
                for a in (a12, a13))
    l12, l13 = leaves(c12), leaves(c13)
    differing = sorted(k for k in set(l12) | set(l13) if l12.get(k, MISSING) != l13.get(k, MISSING))
    observed = OrderedDict((k, [l12.get(k), l13.get(k)]) for k in differing)
    expected = OrderedDict([('model.model_kwargs.api_base', ['http://127.0.0.1:%d/v1' % a['port'] for a in (a12, a13)]),
                            ('model.model_name', ['openai/' + a['alias'] for a in (a12, a13)])])
    problems = [] if dict(observed) == dict(expected) else [
        'the repair1 configurations differ at %s, not exactly at %s with the assignment values' % (
            differing, sorted(DIFF_ALLOWED))]
    tmpl_sha = R.sha(c13['agent'].get('instance_template') or '')
    if tmpl_sha != template_sha256:
        problems.append('the 14B instance template is not the repair1 template of the manifest prompt bytes')
    if c13['environment'].get('run_args') != R.RUN_ARGS:
        problems.append('the 14B run_args are not %s' % ' '.join(R.RUN_ARGS))
    return problems, OrderedDict(
        assignments=[a['assignment_id'] for a in (a12, a13)], leaves_compared=len(set(l12) | set(l13)),
        differences=observed, allowed_differences=list(DIFF_ALLOWED), instance_template_sha256=tmpl_sha,
        run_args=c13['environment'].get('run_args'), agent_class=R.AGENT_CLASS, stall_rule_sha256=R.sha(R.STALL_RULE),
        volatile_patterns=[p.pattern for p, _ in R.VOLATILE])


def probe_precondition(root, load_cfg=None, build=None):
    """Read-only: the passing REQ-012 gate for these bytes, and the configuration proof. The live gate is not re-run."""
    ok12, d = P12.probe_gate(root)
    gate = P11.load_json(root / REQ012_GATE) or {}
    m13, m12 = load(root, MANIFEST_REL), load(root, P12.MANIFEST_REL)
    container = (gate.get('container') or {}).get('detail') or {}
    env, images = container.get('environment') or {}, (gate.get('images') or {}).get('detail') or {}
    pin = m13['images']['instance']['id']
    checks = OrderedDict(
        req012_gate=ok12,
        req012_manifest_sha256=S.sha_file(root / P12.MANIFEST_REL) == PRECONDITION['req012_manifest_sha256'],
        req012_entry_sha256=S.sha_file(root / PRECONDITION['req012_entry']) == PRECONDITION['req012_entry_sha256'],
        repair1=gate.get('repair1') == m13.get('repair1') == m12.get('repair1') == R.repair1_record(),
        prompt_bytes=gate.get('prompt_bytes') == m13.get('prompt_bytes') == m12.get('prompt_bytes') is not None,
        configuration=gate.get('configuration') == R.CONFIGURATION,
        image=(env.get('image') == pin == m12['images']['instance']['id'] and images.get('pinned') == m13['images']
               and images.get('equal_to_pins') == dict(base=True, env=True, instance=True)),
        network=(env.get('run_args') == R.RUN_ARGS
                 and (container.get('network') or {}).get('network_mode') == 'none'))
    try:
        problems, proof = config_proof((load_cfg or pinned_config)(), m12['assignments'][0], m13['assignments'][0],
                                       pin, (m13.get('prompt_bytes') or {}).get('instance_template_repair1_sha256'),
                                       build)
    except Exception as e:  # noqa: BLE001  a proof that cannot run fails closed
        problems, proof = ['the configuration proof could not run: %s: %s' % (type(e).__name__, str(e)[:200])], None
    checks['configuration_proof'] = not problems
    d.update(checks=checks, configuration_proof=proof, configuration_proof_problems=problems)
    return all(checks.values()), d


def probe_step1(root, run=S.sh):
    rows = P12.source_rows(root, (STEP1['reconciliation'], STEP1['watchdog_host_check']), run)
    rec, wd = (P11.load_json(root / STEP1[k]) or {} for k in ('reconciliation', 'watchdog_host_check'))
    d = OrderedDict(records=rows, reconciliation_verified=rec.get('verified') is True,
                    watchdog_host_check_passed=wd.get('passed') is True)
    return (all(v['tracked'] and v['unchanged_from_head'] for v in rows.values()) and d['reconciliation_verified']
            and d['watchdog_host_check_passed']), d


def preconditions(root):
    g_ok, g = probe_precondition(root)
    s_ok, s = probe_step1(root)
    return g_ok and s_ok, OrderedDict(gate=g, step1=s)


# ------------------------------------------------------------------ the swap gate
def swap_free_bytes(text):
    hits = SWAP_FREE.findall(text or '')
    return int(float(hits[0][0]) * UNITS[hits[0][1]]) if len(hits) == 1 else None


def probe_swap(root, run=S.sh):
    rc, out, _ = run(list(SWAP['command']), timeout=30)
    free = swap_free_bytes(out) if rc == 0 else None
    d = OrderedDict(command=SWAP['command'], returncode=rc, output=(out or '').strip()[:200], free_bytes=free,
                    free_gib=None if free is None else round(free / GiB, 3), min_free_bytes=SWAP['min_free_bytes'],
                    rule=SWAP['rule'], note=SWAP['note'])
    return free is not None and free >= SWAP['min_free_bytes'], d


# ------------------------------------------------------------------ admission (REQ-012 probes + REQ-013 parts)
def probe_sources(root, run=S.sh, base=S.probe_sources, compute_binding=None):
    ok, d = P12.probe_sources(root, run, base, compute_binding)
    d['req013_sources'] = P12.source_rows(root, NEW_SOURCES, run)
    return ok and all(v['tracked'] and v['unchanged_from_head'] for v in d['req013_sources'].values()), d


def other_req013_processes(run=S.sh):
    _, rows = S.process_table(run)
    mine = S.ancestors(rows, os.getpid()) | {os.getpid()}
    return [pid for pid, _, argv in rows if pid not in mine and any(Path(x).name in OWN_SCRIPTS for x in argv[:3])]


def probe_conflicts(root, run=S.sh):
    ok, d = P12.probe_conflicts(root, run)
    d['req013_pause_file_present'] = (root / OUTPUTS['pause_file']).exists()
    d['other_req013_processes'] = other_req013_processes(run)
    return ok and not d['req013_pause_file_present'] and not d['other_req013_processes'], d


def admission_probes(manifest):
    pins, queue = manifest['images'], manifest['assignments']
    return OrderedDict(manifest=probe_manifest, sources=probe_sources, runtime=S.probe_runtime,
                       images=lambda root: P11.probe_images(root, pins), conflicts=probe_conflicts,
                       isolation=lambda root: P12.probe_isolation(root, pins['instance']['id'], queue),
                       disk=P11.probe_disk, models=lambda root: P11.probe_models(root, queue),
                       memory=lambda root: P11.probe_memory(root, queue), swap=probe_swap, gate=probe_precondition,
                       step1=probe_step1)


# ------------------------------------------------------------------ serving and watchdog (REQ-013 labels)
class Servers(P11.Servers):
    """pilot_runner.Servers through the REQ-011 subclass; the ownership record is re-labelled for DTR-REQ-013."""

    def _record(self):
        super()._record()
        rec = json.loads(PR.SERVERS.read_text())
        rec['holder'] = HOLDER
        tmp = PR.SERVERS.with_suffix('.tmp')
        tmp.write_text(json.dumps(rec, indent=1) + '\n')
        os.replace(tmp, PR.SERVERS)


def spawn_watchdog(raw, deadline, env, *, servers_record=PR.SERVERS, root=PR.ROOT, python=sys.executable,
                   popen=subprocess.Popen, clock=time.time, **overrides):
    """req012_pair.spawn_watchdog with this runner's holder and script; the loop is req011_pair.watchdog, unchanged."""
    w = dict(P11.WATCHDOG, **overrides)
    cfg_path = Path(raw) / 'watchdog_config.json'
    P11.write_raw(cfg_path, dict(request=REQUEST, parent_pid=os.getpid(), deadline=deadline, holder=HOLDER,
                                 out=str(raw), servers_record=str(servers_record), root=str(root), poll_s=w['poll_s'],
                                 grace_s=w['grace_s']))
    with open(Path(raw) / 'watchdog_stdout.txt', 'x') as log:
        p = popen([str(python), str(Path(__file__).resolve()), '--watchdog', str(cfg_path)], cwd=str(ROOT), env=env,
                  start_new_session=True, stdout=log, stderr=subprocess.STDOUT)
    end = clock() + w['ready_timeout_s']
    while clock() < end and p.poll() is None:
        ready = P11.load_json(Path(raw) / 'watchdog_ready.json')
        if ready and ready.get('watchdog_pid') == p.pid and ready.get('parent_pid') == os.getpid():
            return p, True
        time.sleep(0.2)
    return p, False


# ------------------------------------------------------------------ the probe
def run_probe(ctx):
    """req012_pair.run_probe with the REQ-013 holder, watchdog, entry and PAUSE file: scrubbed environment, watchdog
    before the load, the episode, server stop, then grading; every cleanup cut short by a first signal is retried."""
    root, raw, manifest = ctx['root'], ctx['raw'], ctx['manifest']
    clean, removed = S.scrub_env(dict(os.environ))
    os.environ.clear()
    os.environ.update(clean)                      # the llama.cpp server child (Servers.serve) inherits this environment
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
    servers = Servers(json.loads((root / P11.SERVING['conversion_record']).read_text()), block, raw)
    backstops = ctx.setdefault('backstops', OrderedDict())
    try:
        ctx['watchdog'], ctx['watchdog_ready'] = spawn_watchdog(raw, ctx['pair_deadline'], dict(os.environ))
        try:
            stop = P11.run_episodes(manifest['assignments'], ctx['pair_deadline'], P11.make_serve(servers, ctx),
                                    P11.make_episode_runner(ctx, CAPS), ctx['records'], clock=ctx['clock'],
                                    pause=root / OUTPUTS['pause_file'], caps=CAPS)
        finally:
            P11.stop_server(servers, ctx)
            ctx['summary']['watchdog'] = P11.release_watchdog(ctx.get('watchdog'), servers)
        grade = P11.make_grader(ctx, CAPS)
        for rec in ctx['records']:
            if not rec.get('run_id'):
                rec['grade'] = OrderedDict(status='no grade: assignment not started')
            else:
                rec['grade'] = OrderedDict(status='ungraded: grading did not complete (interrupted or error)')
                rec['grade'] = grade(rec)
        return stop
    finally:
        for name, backstop in list(backstops.items()):
            try:
                backstop()
                ctx['summary'].setdefault('backstops_run', []).append(name)
            except Exception as e:  # noqa: BLE001  recorded
                ctx['summary'].setdefault('backstops_run', []).append('%s: %s: %s' % (name, type(e).__name__, e))
        if servers.live is not None:
            P11.stop_server(servers, ctx)
        ctx['summary']['watchdog'] = P11.release_watchdog(ctx.get('watchdog'), servers)
        if awake is not None:
            awake.terminate()


@contextlib.contextmanager
def rebound(module, **values):
    """Rebind module globals for the duration of one call (single-threaded), then restore them."""
    old = {k: getattr(module, k) for k in values}
    for k, v in values.items():
        setattr(module, k, v)
    try:
        yield module
    finally:
        for k, v in old.items():
            setattr(module, k, v)


def finish(ctx, summary, manifest):
    """req012_pair.finish (row completion, summary, req011_pair.publish) with REQ-013's outputs and prior results."""
    with rebound(P12, OUTPUTS=OUTPUTS, PRIOR_RESULTS=PRIOR_RESULTS):
        return P12.finish(ctx, summary, manifest)


def step1_facts(root):
    rec = P11.load_json(root / STEP1['reconciliation']) or {}
    out = OrderedDict((k, OrderedDict(record=STEP1[k], sha256=S.sha_file(root / STEP1[k])
                                      if (root / STEP1[k]).is_file() else None))
                      for k in ('reconciliation', 'watchdog_host_check'))
    out['req012_probe'] = rec.get('statement')
    return out


def main(argv=None, root=ROOT, probes=None, runner=None, clock=time.time, precondition=None, swap=None):
    ap = argparse.ArgumentParser(description='DTR-REQ-013 single 14B DEVELOPMENT discriminator (after step 1)')
    ap.add_argument('--admission-only', action='store_true', help='print the admission record; start nothing')
    ap.add_argument('--watchdog', metavar='CONFIG', help=argparse.SUPPRESS)   # internal: started by run_probe
    args = ap.parse_args(argv)
    if args.watchdog:
        return P11.watchdog(args.watchdog)
    raw, pub = root / OUTPUTS['raw'] / 'probe', root / OUTPUTS['published'] / 'probe'
    if not args.admission_only:
        if raw.exists() or pub.exists():
            print('DTR-REQ-013 probe is single-shot: %s/probe or %s/probe already exists; no automatic resume or '
                  're-dispatch' % (OUTPUTS['raw'], OUTPUTS['published']), file=sys.stderr)
            return 3
        ok, detail = (precondition or preconditions)(root)
        if not ok:
            print('DTR-REQ-013 probe refused before its namespace (nothing consumed): the REQ-012 gate, the '
                  'configuration proof or step 1 did not pass: %s' % json.dumps(S.sanitize(detail), default=str),
                  file=sys.stderr)
            return 3
        ok, detail = (swap or probe_swap)(root)
        if not ok:
            print(json.dumps(S.sanitize(OrderedDict(status='BLOCKED_FOR_CAPACITY', started=False, namespace_created=False,
                                                    swap=detail))))
            return 4
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
    summary = OrderedDict(request=REQUEST, kind='single-episode DEVELOPMENT 14B discriminator summary (the file name '
                                                'pair_summary.json is that of the reused req011_pair publication)',
                          manifest=MANIFEST_REL, manifest_sha256=adm['manifest_sha256'],
                          admission_sha256=P11.write_raw(raw / 'admission.json', adm), configuration=R.CONFIGURATION,
                          started_utc=S.utc(start), probe_deadline_utc=S.utc(start + CAPS['pair_wall_s']), status=None,
                          stop_reason=None, interrupted_or_error=None, step1=step1_facts(root))
    sources = (adm.get('sources') or {}).get('detail') or {}
    ctx = dict(root=root, raw=raw, pub=pub, start=start, pair_deadline=start + CAPS['pair_wall_s'], clock=clock,
               manifest=manifest, manifest_sha256=adm['manifest_sha256'], summary=summary, records=[],
               ledger=P11.Ledger(raw / 'ledger.jsonl', clock),
               sources={k: v['sha256'] for key in ('req011_sources', 'req012_sources', 'req013_sources')
                        for k, v in (sources.get(key) or {}).items()},
               runtime=sources.get('cue_runtime'))
    if not adm['admitted']:
        failed = [k for k, v in adm.items() if isinstance(v, dict) and v.get('ok') is False]
        summary.update(status='BLOCKED_FOR_CAPACITY' if 'swap' in failed else 'BLOCKED', executed=False,
                       failed_admission_checks=failed)
        finish(ctx, summary, manifest)
        print(json.dumps(S.sanitize({k: summary[k] for k in ('status', 'failed_admission_checks')})))
        return 2
    old = {sig: signal.signal(sig, S.raise_interrupted) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        summary['stop_reason'] = (runner or run_probe)(ctx)
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
