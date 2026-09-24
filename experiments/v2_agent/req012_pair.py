"""DTR-REQ-012 (lead 40b4db2, docs/theory_feedback_20260924_req011_decision.md). This runs the no-model repair gate
first. Only if the gate passed does it run ONE Qwen2.5-Coder-7B DEVELOPMENT probe episode on astropy__astropy-14598,
under the versioned configuration yaml-v1-repair1 (req012_entry.py). The committed manifest
configs/v2_req012_repair_probe_20260924.json is the specification: its declared rules govern this runner. The probe is
a mechanism check. It is not a success rate, not a paired comparison and not CONFIRM evidence.

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req012_pair.py --admission-only   (read-only)
    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req012_pair.py --gate             (no model)
    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req012_pair.py                    (the probe)

This is a thin layer over the committed REQ-011 runner, req011_pair.py, which is imported read-only and never edited.
It reuses these REQ-011 parts:
  * the admission probes;
  * serving: the Servers subclass and the GET-only served-identity check;
  * the queue and schedule: run_episodes and fits;
  * episode supervision: make_episode_runner;
  * grading: make_grader, which runs req011_grade.py;
  * the watchdog loop, the episode facts and publication.
Only the parts REQ-011 hard-codes are restated here: the manifest, the caps (3600 s, one episode, 48 requests), the
entry, the ownership holder and the watchdog launcher. The gate and the probe summary are new.

The gate refuses before creating its single-shot namespace (nothing consumed) unless the manifest binds, every source is
tracked and unchanged from HEAD, no other REQ-012 process runs and the colima VM lists no minisweagent-* container. It
arms SIGINT/SIGTERM/SIGHUP like the probe: a first signal is recorded in gate.json (passed false) after the container is
stopped and removed. It may take a few minutes (fixtures, then emulated pip and pytest in the container): run it in the
background or under a timeout of at least 600 s.
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
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (Path(__file__).resolve().parent, ROOT / 'experiments/v2_adapter'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req011_pair as P11  # noqa: E402  the committed REQ-011 runner, imported read-only
import req012_entry as R  # noqa: E402  repair1 constants and pure functions (importing it installs no override)

PR, S, WC, A = P11.PR, P11.S, P11.WC, P11.A
REQUEST = 'DTR-REQ-012'
MANIFEST_REL = R.MANIFEST_REL
REQ011_SUMMARY = 'results/v2_agent/req011_competence_20260924/pair_summary.json'
HOLDER = 'DTR-AgentEvals worker (DTR-REQ-012 repair probe)'
CAPS = dict(P11.CAPS, pair_wall_s=3600, episode_load_allowance_s=300, grading_floor_s=900, max_logical_requests=24,
            max_physical_requests=48)       # grading floor 900 = evaluator_min_start_budget_s + evaluator_end_reserve_s
RUNTIME = dict(P11.RUNTIME, orchestrator='experiments/v2_agent/req012_pair.py', entry='experiments/v2_agent/req012_entry.py',
               fixtures_python='.venv/bin/python')
OUTPUTS = dict(raw='work/runs/req012_repair_probe_20260924', published='results/v2_agent/req012_repair_probe_20260924',
               pause_file='work/REQ012_PAUSE', private_receipts=A.PRIVATE_RECEIPTS_REL)
FIXTURES = 'tests/test_req012_repair.py'
NEW_SOURCES = ('experiments/v2_agent/req012_pair.py', 'experiments/v2_agent/req012_entry.py', MANIFEST_REL, FIXTURES,
               'tests/test_req011_pair.py', 'experiments/tools/req011_integration_harness.py',
               'experiments/tools/v2_cue_integration_harness.py')
SOURCES = P11.SOURCES + NEW_SOURCES
OWN_SCRIPTS = ('req012_pair.py', 'req012_entry.py')
PRIOR_RESULTS = OrderedDict((
    (REQ011_SUMMARY, 'a2cc62877b6a0b7b34a50688b5a7d114697b4c743199de918cbe0711c0382d31'),
    ('results/v2_agent/pilot_20260922_yaml_v1/report_yaml_v1_block1_final.json',
     'ef894706d393a73b6accc07a94cfbd1a4bba1c1b12b9a1c6e682c4744ec5fb17')))
OUTCOME_SOURCES = ('eligible_submission', 'agent', 'stall_guard', 'time_limit', 'infrastructure_or_supervision')
SCRATCH = 'req012_gate_scratch.txt'
ASTROPY_INIT = '/testbed/astropy/__init__.py'
IMAGE_HEAD = 'a4ae7a3808de3c53b0788875b6c97b20d5a12ee0'   # the SWE-bench setup commit (HEAD^ = the base commit)
IMAGE_HEAD_EVIDENCE = ('results/v2_adapter/req010_sentinel_20260924/astropy__astropy-14598/attempt-1-20260924T113537Z/'
                       'summary.json (repo_state_pre.head of the adapter_reference and adapter_no_change attempts on '
                       'the pinned instance image) and stock_test_output.txt (git '
                       "show: subject 'SWE-bench', pyproject.toml only); the image's setup_repo.sh ends with "
                       '`git commit --allow-empty -am SWE-bench` after pinning setuptools in pyproject.toml')
SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
GATE_COMMANDS = OrderedDict((
    ('G0', 'pwd'),
    ('G1', 'cd /testbed && git rev-parse HEAD HEAD^ && git log -1 --format=%s && git diff --name-only HEAD^ HEAD '
           '&& git status --porcelain'),
    ('G2', 'cd / && python -c "import astropy,sys; print(astropy.__file__); print(astropy.__version__)"'),
    ('G3', "pip list 2>/dev/null | grep -i '^astropy '"),
    ('G4', 'python -c "import socket; socket.create_connection((\'pypi.org\', 443), timeout=5)"'),
    ('G5', 'pip install --upgrade astropy'),
    ('G6', 'cd /testbed && python -m pytest astropy/io/fits/tests/test_header.py -q -x -k "card" -p no:cacheprovider'),
    ('G7', 'cd /testbed && echo req012 > %s && git status --porcelain' % SCRATCH)))
GATE_EXPECTATIONS = OrderedDict((
    ('G0', "rc 0 and the output is exactly '/testbed' (the working directory of every action)"),
    ('G1', "rc 0; the output is exactly four lines: HEAD = gate.image_head (SWE-bench's image setup commit), HEAD^ = "
           "the dataset base_commit, the HEAD subject 'SWE-bench' and 'pyproject.toml' (the only file HEAD changes); "
           'no status line (clean checkout)'),
    ('G2', "rc 0; the last two output lines are '%s' and a version containing '.dev'" % ASTROPY_INIT),
    ('G3', "rc 0; exactly one 'astropy ' line, whose last field is '/testbed' (editable location)"),
    ('G4', 'a nonzero integer rc (no egress)'),
    ('G5', "pip's integer rc and output are recorded, no particular rc is required (offline pip may keep the installed "
           "editable astropy and exit 0); the output has no 'Successfully installed' line; then the G2 command again "
           "(G5_then_G2): rc 0 and the same last two lines as G2; then the G3 command again (G5_then_G3): rc 0 and the "
           "same single 'astropy ' line as G3"),
    ('G6', 'rc 0 or 1 and a pytest summary line (the local tests ran offline)'),
    ('G7', "rc 0 and the line '?? %s' in the status (edits in /testbed are visible)" % SCRATCH)))
GATE = dict(
    commands=GATE_COMMANDS, expectations=GATE_EXPECTATIONS, command_timeout_s=R.PE.CMD_TIMEOUT,
    image_head=IMAGE_HEAD, image_head_evidence=IMAGE_HEAD_EVIDENCE,
    container='one repair1 agent container: the unmodified mini-swe-agent 04d809c DockerEnvironment with the repair1 '
              'environment config (pinned instance image ID, --rm --platform linux/amd64 --network none, cwd /testbed, '
              'the frozen container env), every command through its execute() with the frozen 60 s timeout; stopped '
              'and removed afterwards. It starts only if the VM lists no minisweagent-* container; if the start fails '
              'before the container ID is known, minisweagent-* containers listed afterwards (none were listed before) '
              'are removed by name and recorded',
    preflight='before the namespace is created (a refusal consumes nothing): the manifest check, every source tracked '
              'and unchanged from HEAD, no other REQ-012 process, and no minisweagent-* container listed',
    order='manifest, sources, fixtures, images, container; a check runs only while every earlier one passed (a skipped '
          'check fails), so the container is never started after a failed check',
    interruption='SIGINT, SIGTERM and SIGHUP raise S.Interrupted on the first signal (later ones are ignored); the '
                 'container is stopped and removed (the cleanup runs once more if the signal cut it short) and '
                 'gate.json records the signal with passed false',
    egress_evidence='the fixtures check no-egress at the configuration level only (the fake docker receives --network '
                    'none and reports NetworkMode none); the actual blocking is shown only by the live G4 and G5',
    fixtures=[RUNTIME['fixtures_python'], '-m', 'pytest', '-q', '-p', 'no:cacheprovider', FIXTURES],
    fixtures_timeout_s=1800, record=OUTPUTS['published'] + '/gate.json',
    passes_only_if='the manifest check (including prompt bytes from the pinned default.yaml), every source tracked, '
                   'unchanged from HEAD and stable during the gate, the fixtures passing with none skipped, the image '
                   'pins, every G0-G7 expectation, docker NetworkMode none, confirmed container stop and removal, no '
                   'minisweagent-* container listed afterwards, and no operator signal')
PYTEST_SUMMARY = re.compile(r'(?<!\d)\d+ (?:passed|failed|errors?|skipped|deselected|xfailed|xpassed)\b')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def source_rows(root, rels, run=S.sh):
    rows = OrderedDict()
    for s in rels:
        tracked = run(['git', '-C', str(root), 'ls-files', '--error-unmatch', s])[0] == 0
        rows[s] = OrderedDict(sha256=S.sha_file(root / s) if (root / s).is_file() else None, tracked=tracked,
                              unchanged_from_head=tracked and run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD',
                                                                   '--', s])[0] == 0)
    return rows


def source_digests(root):
    return OrderedDict((s, S.sha_file(root / s) if (root / s).is_file() else None) for s in SOURCES)


# ------------------------------------------------------------------ manifest binding
def expected_manifest(conv, req010):
    """The machine-checked sections, from the bound code (REQ-011 values via req011_pair, repair1 via req012_entry)."""
    m11 = P11.expected_manifest(conv, req010)
    return dict(request=REQUEST, lead_commit='40b4db2', lead_decision='docs/theory_feedback_20260924_req011_decision.md',
                source_commit='6074003', instance_id=S.TARGET, images=m11['images'],
                assignments=[dict(P11.assignment_row(1, 'small', conv), assignment_id='req012-1-small')],
                settings=dict(m11['settings'], configuration_binding=R.CONFIGURATION,
                              base_configuration_binding='yaml-v1'),
                repair1=R.repair1_record(), serving=P11.SERVING, evaluator=P11.EVALUATOR, caps=CAPS,
                memory_rule=P11.MEMORY, disk_rule=P11.DISK, watchdog=P11.WATCHDOG, gate=GATE, runtime=RUNTIME,
                outputs=OUTPUTS, prior_results=PRIOR_RESULTS)


def manifest_problems(manifest, conv, req010, template=None):
    expected = expected_manifest(conv, req010)
    problems = ['manifest %s differs from the bound value' % k for k in expected if manifest.get(k) != expected[k]]
    problems += ['manifest %s is missing' % k for k in P11.TEXT_KEYS + ('prompt_bytes',) if not manifest.get(k)]
    if req010.get('status') != 'QUALIFIED' or req010.get('target') != S.TARGET:
        problems.append('the REQ-010 summary does not record %s as QUALIFIED' % S.TARGET)
    if template is not None and manifest.get('prompt_bytes') != R.prompt_bytes(template):
        problems.append('manifest prompt_bytes differ from the pinned default.yaml')
    return problems


def probe_manifest(root, template=None):
    raw = (root / MANIFEST_REL).read_bytes()
    conv_path = root / P11.SERVING['conversion_record']
    template = R.frozen_template() if template is None else template
    problems = manifest_problems(json.loads(raw), json.loads(conv_path.read_bytes()),
                                 json.loads((root / P11.REQ010_SUMMARY_REL).read_bytes()), template)
    if S.sha_file(conv_path) != P11.SERVING['conversion_record_sha256']:
        problems.append('conversion record sha256 differs from the bound value')
    return not problems, OrderedDict(manifest=MANIFEST_REL, manifest_sha256=S.sha_bytes(raw), problems=problems,
                                     prompt_bytes=R.prompt_bytes(template))


# ------------------------------------------------------------------ probe admission (REQ-011 probes + REQ-012 parts)
def probe_sources(root, run=S.sh, base=S.probe_sources, compute_binding=None):
    ok, d = P11.probe_sources(root, run, base, compute_binding)
    d['req012_sources'] = source_rows(root, NEW_SOURCES, run)
    return ok and all(v['tracked'] and v['unchanged_from_head'] for v in d['req012_sources'].values()), d


def other_req012_processes(run=S.sh):
    _, rows = S.process_table(run)
    mine = S.ancestors(rows, os.getpid()) | {os.getpid()}
    return [pid for pid, _, argv in rows if pid not in mine and any(Path(x).name in OWN_SCRIPTS for x in argv[:3])]


def probe_conflicts(root, run=S.sh):
    ok, d = P11.probe_conflicts(root, run)
    d['req012_pause_file_present'] = (root / OUTPUTS['pause_file']).exists()
    d['other_req012_processes'] = other_req012_processes(run)
    return ok and not d['req012_pause_file_present'] and not d['other_req012_processes'], d


def repair_sandbox_problems(environment):
    """req011_pair.sandbox_problems, with the repair1 run_args (--network none) in place of the frozen ones."""
    if environment.get('run_args') != R.RUN_ARGS:
        return ['run_args %r are not exactly %s' % (environment.get('run_args'), ' '.join(R.RUN_ARGS))]
    return P11.sandbox_problems(dict(environment, run_args=list(R.FROZEN_RUN_ARGS)))


def probe_isolation(root, image_id, assignments):
    ok, d = P11.probe_isolation(root, image_id, assignments)   # environment, proxies, LITELLM_*, mini-swe-agent .env
    import yaml
    PE = R.PE
    cfg = yaml.safe_load((PE.MSWEA / 'src/minisweagent/config/default.yaml').read_text())
    problems = []
    for a in assignments:
        problems += repair_sandbox_problems(R.repair_config(PE.build_effective_config(
            cfg, alias=a['alias'], port=a['port'], image_id=image_id))['environment'])
    d.update(repair1_sandbox_problems=problems,
             networking='repair1 agent containers run with --network none (no egress); the live check is the gate '
                        'record (G4, G5), which the gate probe requires')
    return ok and not problems, d


GATE_AGREEMENT = ('passed', 'interrupted', 'manifest_sha256', 'source_digests', 'started_utc', 'finished_utc')


def probe_gate(root):
    """A passing gate record for this manifest sha256 and these source digests (the probe's precondition). The published
    record and the raw copy under work/ must agree on the fields that decide it."""
    rec, digests = P11.load_json(root / OUTPUTS['published'] / 'gate.json'), source_digests(root)
    raw = P11.load_json(root / OUTPUTS['raw'] / 'gate' / 'gate.json')
    d = OrderedDict(record=OUTPUTS['published'] + '/gate.json', present=rec is not None,
                    raw_record=OUTPUTS['raw'] + '/gate/gate.json', raw_present=raw is not None)
    if not isinstance(rec, dict):
        return False, d
    recorded = rec.get('source_digests') or {}
    d.update(passed=rec.get('passed') is True, finished_utc=rec.get('finished_utc'),
             manifest_sha256_equal=rec.get('manifest_sha256') == S.sha_file(root / MANIFEST_REL),
             changed_sources=sorted(k for k in set(digests) | set(recorded)
                                    if digests.get(k) is None or recorded.get(k) != digests.get(k)),
             raw_record_agrees=isinstance(raw, dict) and all(raw.get(k) == rec.get(k) for k in GATE_AGREEMENT))
    return (d['passed'] and d['manifest_sha256_equal'] and not d['changed_sources'] and d['raw_record_agrees']), d


def admission_probes(manifest):
    pins, queue = manifest['images'], manifest['assignments']
    return OrderedDict(manifest=probe_manifest, sources=probe_sources, runtime=S.probe_runtime,
                       images=lambda root: P11.probe_images(root, pins), conflicts=probe_conflicts,
                       isolation=lambda root: probe_isolation(root, pins['instance']['id'], queue),
                       disk=P11.probe_disk, models=lambda root: P11.probe_models(root, queue),
                       memory=lambda root: P11.probe_memory(root, queue), gate=probe_gate)


# ------------------------------------------------------------------ the no-model repair gate
def excerpt(text, n=1500):
    return text if len(text) <= 2 * n else '%s\n[... %d characters elided ...]\n%s' % (
        text[:n], len(text) - 2 * n, text[-n:])


def out_lines(text):
    return [x.strip() for x in (text or '').splitlines() if x.strip()]


def gate_checks(execute, base_commit):
    """G0-G7 through execute(command) -> (returncode, output); every expectation fails closed. Returns (rows, ok)."""
    rows = OrderedDict()

    def run(name, command):
        rc, out = execute(command)
        out = out if isinstance(out, str) else ''
        rows[name] = OrderedDict(command=command, returncode=rc,
                                 output_sha256=S.sha_bytes(out.encode('utf-8', 'surrogateescape')),
                                 output_chars=len(out), excerpt=excerpt(out))
        return rc, out_lines(out)

    def result(name, ok, **observed):
        rows[name].update(expectation=GATE_EXPECTATIONS.get(name[:2]), ok=bool(ok), observed=observed)
        return bool(ok)

    def astropy_lines(ls):
        return [x for x in ls if x.lower().startswith('astropy ')]
    rc, ls = run('G0', GATE_COMMANDS['G0'])
    result('G0', rc == 0 and ls == ['/testbed'], lines=ls[:3])
    rc, ls = run('G1', GATE_COMMANDS['G1'])
    result('G1', rc == 0 and ls == [IMAGE_HEAD, base_commit, 'SWE-bench', 'pyproject.toml'], lines=ls[:8],
           image_head=IMAGE_HEAD, base_commit=base_commit)
    rc, ls = run('G2', GATE_COMMANDS['G2'])
    g2 = ls[-2:] if rc == 0 and len(ls) >= 2 else None
    g2_ok = result('G2', g2 is not None and g2[0] == ASTROPY_INIT and '.dev' in g2[1], last_two_lines=g2)
    rc, ls = run('G3', GATE_COMMANDS['G3'])
    hit = astropy_lines(ls)
    g3_ok = result('G3', rc == 0 and len(hit) == 1 and hit[0].split()[-1] == '/testbed', astropy_lines=hit)
    rc, ls = run('G4', GATE_COMMANDS['G4'])
    result('G4', type(rc) is int and rc != 0)
    pip_rc, pip_lines = run('G5', GATE_COMMANDS['G5'])
    rc, ls = run('G5_then_G2', GATE_COMMANDS['G2'])
    after2 = result('G5_then_G2', g2_ok and rc == 0 and ls[-2:] == g2, last_two_lines=ls[-2:])
    rc, ls = run('G5_then_G3', GATE_COMMANDS['G3'])
    after3 = result('G5_then_G3', g3_ok and rc == 0 and astropy_lines(ls) == hit, astropy_lines=astropy_lines(ls))
    installed = [x for x in pip_lines if 'Successfully installed' in x]
    result('G5', type(pip_rc) is int and not installed and after2 and after3, pip_returncode=pip_rc,
           successfully_installed_lines=installed)
    rc, ls = run('G6', GATE_COMMANDS['G6'])
    summary = next((x for x in (ANSI.sub('', y) for y in reversed(ls)) if PYTEST_SUMMARY.search(x)), None)
    result('G6', rc in (0, 1) and summary is not None, summary_line=summary)
    rc, ls = run('G7', GATE_COMMANDS['G7'])
    result('G7', rc == 0 and '?? ' + SCRATCH in ls, status_lines=ls[:20])
    return rows, all(r['ok'] for r in rows.values())


def minisweagent_names(env, run=S.sh):
    """Names of every minisweagent-* container the colima VM lists (None if the listing failed)."""
    rc, listing, _ = run(['docker', 'ps', '-a', '--format', '{{.Names}}'], env=env, timeout=30)
    return None if rc != 0 else [n for n in listing.split() if n.startswith('minisweagent-')]


def container_session(start, work, cleanup, d):
    """start() -> env; work(env) -> ok; cleanup(env) on every exit. A first operator signal (S.Interrupted) is recorded
    in d and not raised further; if it cuts the cleanup short, the cleanup runs once more (S.raise_interrupted ignores
    every later signal)."""
    env, ok = None, False
    try:
        env = start()
        ok = work(env)
    except S.Interrupted as e:
        d['interrupted'] = str(e)
    except Exception as e:  # noqa: BLE001  recorded; the container is still removed
        d['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
    finally:
        try:
            cleanup(env)
        except S.Interrupted as e:
            d.setdefault('interrupted', str(e))
            d['cleanup_repeated_after_signal'] = True
            cleanup(env)
    return ok and 'interrupted' not in d and 'error' not in d


def gate_container(root, manifest, raw, clock=time.time):
    """G0-G7 in ONE container started exactly as the repair1 agent environment would be (no model, no server)."""
    import pandas as pd
    import yaml
    from minisweagent.environments.docker import DockerEnvironment
    PE = R.PE
    clean, removed = S.scrub_env(S.docker_env())
    os.environ.clear()
    os.environ.update(clean)                        # DOCKER_HOST = the colima dtr socket, as the episode child gets
    a, pin = manifest['assignments'][0], manifest['images']['instance']['id']
    cfg = yaml.safe_load((PE.MSWEA / 'src/minisweagent/config/default.yaml').read_text())
    frozen = PE.build_effective_config(cfg, alias=a['alias'], port=a['port'], image_id=pin)
    effective = R.repair_config(frozen)
    base = next(r['base_commit'] for r in pd.read_parquet(PE.DATA).to_dict('records') if r['instance_id'] == S.TARGET)

    class GateEnvironment(DockerEnvironment):
        def cleanup(self):                          # never the upstream asynchronous shell; removed below
            return None
    before = minisweagent_names(dict(os.environ))
    d = OrderedDict(environment=effective['environment'], environment_variables_removed=removed, base_commit=base,
                    instance_template_frozen=frozen['agent']['instance_template'],
                    instance_template_repair1=effective['agent']['instance_template'],
                    minisweagent_containers_listed_before=before, network={}, checks=None)
    holder = {}

    def start():
        if before != []:
            raise RuntimeError('not started: the VM listing of minisweagent-* containers is %r, not []' % (before,))
        env = holder['env'] = GateEnvironment(**effective['environment'])
        WC.write_once(raw / 'container_ownership.json', json.dumps(dict(container_id=env.container_id)) + '\n')
        return env

    def work(env):
        d['network'] = R.observe_network(env)
        d['checks'], ok = gate_checks(lambda cmd: (lambda o: (o.get('returncode'), o.get('output', '')))(
            env.execute({'command': cmd})), base)
        return ok

    def cleanup(env):
        cid = getattr(env or holder.get('env'), 'container_id', None)   # also when start() failed after the run
        d['cleanup'] = PE.cleanup_owned_container(cid, clock() + 120) if cid else None
        listed = minisweagent_names(dict(os.environ)) if cid is None and before == [] else None
        d['removed_by_name_after_a_failed_start'] = listed or []   # none were listed before, so these are the gate's
        d['removal'] = P11.remove_containers([cid] if cid else (listed or []), env=dict(os.environ))
        d['minisweagent_containers_listed_after'] = minisweagent_names(dict(os.environ))
    ok = container_session(start, work, cleanup, d)
    return (ok and d['network'].get('network_mode') == 'none' and (d['cleanup'] or {}).get('confirmed') is True
            and d['removal']['complete'] and d['minisweagent_containers_listed_after'] == []), d


def gate_sources(root, run=S.sh):
    rows = source_rows(root, SOURCES, run)
    return all(v['sha256'] and v['tracked'] and v['unchanged_from_head'] for v in rows.values()), rows


def run_fixtures(root, raw, run=S.sh):
    env = dict(S.scrub_env(dict(os.environ))[0], PYTHONPATH=str(root / 'src'))
    cmd = [str(root / GATE['fixtures'][0])] + GATE['fixtures'][1:-1] + [str(root / FIXTURES)]
    rc, out, err = run(cmd, env=env, timeout=GATE['fixtures_timeout_s'])
    with open(raw / 'fixtures_stdout.txt', 'x') as fh:
        fh.write((out or '') + (err or ''))
    summary = (out_lines(ANSI.sub('', out or '')) or [None])[-1]
    ok = rc == 0 and summary is not None and ' passed' in summary and 'skipped' not in summary
    return ok, OrderedDict(command=GATE['fixtures'], returncode=rc, summary=summary)


def gate_probes(manifest, raw):
    return OrderedDict(manifest=probe_manifest, sources=gate_sources, fixtures=lambda root: run_fixtures(root, raw),
                       images=lambda root: P11.probe_images(root, manifest['images']),
                       container=lambda root: gate_container(root, manifest, raw))


def gate_preflight(root, run=S.sh, manifest_probe=probe_manifest):
    """Read-only; a refusal here creates no namespace and consumes nothing."""
    m_ok, m = manifest_probe(root)
    s_ok, rows = gate_sources(root, run)
    d = OrderedDict(manifest_problems=m['problems'], sources_not_tracked_or_changed=[
        k for k, v in rows.items() if not (v['sha256'] and v['tracked'] and v['unchanged_from_head'])],
        other_req012_processes=other_req012_processes(run),
        minisweagent_containers_listed=minisweagent_names(S.scrub_env(S.docker_env())[0], run))
    return m_ok and s_ok and not d['other_req012_processes'] and d['minisweagent_containers_listed'] == [], d


def run_gate_probes(root, probes, rec):
    """S.admission's loop, except that a check runs only while every earlier one passed (a skipped check fails) and a
    first operator signal is recorded in rec['interrupted'] and ends the loop."""
    for name, fn in probes.items():
        if rec.get('interrupted') or not all(rec[k]['ok'] for k in probes if k in rec):
            rec[name] = OrderedDict(ok=False, detail=OrderedDict(skipped='an earlier gate check failed or a signal '
                                                                          'arrived'))
            continue
        try:
            ok, detail = fn(root)
        except S.Interrupted as e:
            ok, detail = False, OrderedDict(interrupted=str(e))
        except Exception as e:  # noqa: BLE001  a probe that cannot run is a failed check
            ok, detail = False, OrderedDict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
        rec[name] = OrderedDict(ok=bool(ok), detail=detail)
        if isinstance(detail, dict) and detail.get('interrupted'):
            rec['interrupted'] = detail['interrupted']
    return rec


def gate_main(root=ROOT, probes=None, clock=time.time, preflight=None):
    raw, pub = root / OUTPUTS['raw'] / 'gate', root / OUTPUTS['published']
    if raw.exists() or (pub / 'gate.json').exists():
        print('DTR-REQ-012 gate is single-shot: %s/gate or %s/gate.json already exists'
              % (OUTPUTS['raw'], OUTPUTS['published']), file=sys.stderr)
        return 3
    ok, pre = (preflight or gate_preflight)(root)
    if not ok:
        print('DTR-REQ-012 gate refused before its namespace (nothing consumed): %s'
              % json.dumps(S.sanitize(pre)), file=sys.stderr)
        return 3
    manifest_bytes = (root / MANIFEST_REL).read_bytes()
    manifest = json.loads(manifest_bytes)
    probes = probes if probes is not None else gate_probes(manifest, raw)
    raw.mkdir(parents=True, exist_ok=False)
    pub.mkdir(parents=True, exist_ok=True)
    start, before = clock(), source_digests(root)
    rec = OrderedDict(checked_utc=S.utc(start), preflight=pre)
    old = {sig: signal.signal(sig, S.raise_interrupted) for sig in SIGNALS}
    try:
        run_gate_probes(root, probes, rec)
    except S.Interrupted as e:                      # a signal between two checks
        rec['interrupted'] = str(e)
    finally:
        for sig in old:
            signal.signal(sig, signal.SIG_IGN)       # later signals never cut the record short
        try:
            rec['checks_ok'] = all((rec.get(k) or {}).get('ok') is True for k in probes)
            rec.setdefault('interrupted', None)
            rec.update(request=REQUEST, kind='DTR-REQ-012 no-model repair gate (no model, no server, one container)',
                       manifest_file=MANIFEST_REL, manifest_sha256=S.sha_bytes(manifest_bytes),
                       configuration=R.CONFIGURATION, prompt_bytes=manifest.get('prompt_bytes'),
                       repair1=manifest.get('repair1'), gate=manifest.get('gate'), started_utc=S.utc(start),
                       finished_utc=S.utc(clock()), source_digests=before,
                       sources_stable_during_gate=before == source_digests(root))
            rec['passed'] = rec['checks_ok'] and rec['sources_stable_during_gate'] and rec['interrupted'] is None
            P11.write_raw(raw / 'gate.json', rec)
            S.write_json_x(pub / 'gate.json', rec)
            hits = S.username_hits(pub)
            if hits:
                S.write_json_x(pub / 'USERNAME_FOUND.json', OrderedDict(files=hits, action='do not publish until '
                                                                                          'redacted'))
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
    print(json.dumps(S.sanitize(dict(passed=rec['passed'], interrupted=rec['interrupted'], failed_checks=[
        k for k, v in rec.items() if isinstance(v, dict) and v.get('ok') is False]))))
    return 0 if rec['passed'] else 2


# ------------------------------------------------------------------ serving and watchdog (REQ-012 labels)
class Servers(P11.Servers):
    """pilot_runner.Servers through the REQ-011 subclass; the ownership record is re-labelled for DTR-REQ-012."""

    def _record(self):
        super()._record()
        rec = json.loads(PR.SERVERS.read_text())
        rec['holder'] = HOLDER
        tmp = PR.SERVERS.with_suffix('.tmp')
        tmp.write_text(json.dumps(rec, indent=1) + '\n')
        os.replace(tmp, PR.SERVERS)


def spawn_watchdog(raw, deadline, env, *, servers_record=PR.SERVERS, root=PR.ROOT, python=sys.executable,
                   popen=subprocess.Popen, clock=time.time, **overrides):
    """req011_pair.spawn_watchdog with this runner's holder and script (P11 hard-codes both); the loop it starts is
    req011_pair.watchdog, unchanged."""
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
    """req011_pair.run_pair's sequence for the one REQ-012 assignment: scrubbed environment, watchdog before the load,
    the episode, server stop, then grading; every cleanup cut short by a first signal is retried once."""
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


# ------------------------------------------------------------------ summary
def outcome_source(state, exit_status, eligible):
    """req011_pair.outcome_source plus 'stall_guard' for an episode the observational guard ended."""
    if not eligible and state == 'completed' and exit_status == R.STALL:
        return 'stall_guard'
    return P11.outcome_source(state, exit_status, eligible)


def repair_facts(run_dir, control_dir):
    rec = P11.load_json(control_dir / 'repair_record.json') or {}
    guard, eff = rec.get('guard') or {}, rec.get('effective_config') or {}
    network = guard.get('network') or {}
    info = (P11.load_json(run_dir / 'trajectory.json') or {}).get('info') or {}
    return OrderedDict(
        repair_record_present=bool(rec), configuration=rec.get('configuration'), stall_guard_fired=guard.get('fired'),
        stall_guard_fired_before_call=guard.get('fired_before_call'), guard_turns_recorded=len(guard.get('turns') or []),
        network_mode_observed=network.get('network_mode'), run_args_at_container_start=network.get('run_args'),
        effective_config_verified=eff.get('verified'), effective_config_problems=eff.get('problems'),
        effective_config_sha256=eff.get('effective_config_sha256'),
        instance_template_sha256=eff.get('instance_template_sha256'),
        agent_type=(info.get('config') or {}).get('agent_type'))


def prior_results(root):
    out = OrderedDict()
    for rel, expected in PRIOR_RESULTS.items():
        sha = S.sha_file(root / rel) if (root / rel).is_file() else None
        out[rel] = OrderedDict(expected_sha256=expected, sha256=sha, unchanged=sha == expected)
    rec = P11.load_json(root / REQ011_SUMMARY) or {}
    out['req011_eligible_submissions'] = OrderedDict(
        eligible=(rec.get('outcome_sources') or {}).get('eligible_submission'), of=len(rec.get('assignments') or []))
    out['statement'] = 'the earlier 0/32 fixed-backend yaml-v1 block and the 0/2 REQ-011 pair are reported unchanged'
    return out


def finish(ctx, summary, manifest):
    """Complete the assignment row (from the ledger when the run was cut short), write and publish."""
    root, raw, records, states = ctx['root'], ctx['raw'], ctx['records'], ctx['ledger'].states()
    seen = {r['order'] for r in records}
    records += [OrderedDict((k, a[k]) for k in ('order', 'assignment_id', 'backend', 'alias', 'port'))
                for a in manifest.get('assignments', []) if a['order'] not in seen]
    rows = []
    for r in sorted(records, key=lambda r: r['order']):
        row, st = OrderedDict(r), states.get(r['order'])
        if 'state' not in row or (st and st['state'] == 'interrupted'):
            row.update(run_id=(st or {}).get('run_id'), state=st['state'] if st else 'not_started: probe %s' % (
                (summary.get('status') or 'blocked').lower()))
        run_dir = raw / row['run_id'] if row.get('run_id') else None
        if 'request_accounting' not in row:
            row['request_accounting'] = P11.account(P11.load_json(run_dir / 'episode.json'), CAPS) if run_dir \
                else OrderedDict(counted=0, accounting='not_started')
        if run_dir is not None and run_dir.is_dir():
            try:                                            # one unreadable record never costs the summary
                row.update(P11.episode_facts(run_dir, row['run_id'], root, raw / 'control' / row['run_id']))
                row['repair1'] = repair_facts(run_dir, raw / 'control' / row['run_id'])
            except Exception as e:  # noqa: BLE001
                row['episode_facts_error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
        row['outcome_source'] = outcome_source(row.get('state'), row.get('exit_status'), row.get('eligible') is True)
        row.setdefault('grade', OrderedDict(status='no grade: %s' % (
            'assignment not started' if not row.get('run_id') else 'grading not reached (%s)' % summary.get('status'))))
        rows.append(row)
    ints = lambda k: sum(x[k] for x in rows if type(x.get(k)) is int)  # noqa: E731
    end, counted = ctx['clock'](), sum(x['request_accounting']['counted'] for x in rows)
    logical, physical = ints('logical_calls'), ints('physical_requests')
    summary.update(
        finished_utc=S.utc(end), wall_seconds=round(end - ctx['start'], 1), probe_cap_s=CAPS['pair_wall_s'],
        within_cap=end - ctx['start'] <= CAPS['pair_wall_s'], assignments=rows,
        requests=OrderedDict(logical_reported_total=logical, physical_reported_total=physical,
                             physical_counted_total=counted, max_logical=CAPS['max_logical_requests'],
                             max_physical=CAPS['max_physical_requests'],
                             within_caps=logical <= CAPS['max_logical_requests']
                             and counted <= CAPS['max_physical_requests'], non_task_generation_requests=0),
        denominator='the one assignment, whatever its state',
        outcome_sources=OrderedDict((k, sum(x['outcome_source'] == k for x in rows)) for k in OUTCOME_SOURCES),
        outcome_source_rule='stall_guard = a completed episode whose exit is %s; otherwise req011_pair.outcome_source '
                            '(agent = %s; time_limit = %s; anything else = infrastructure_or_supervision, which is not '
                            'evidence about competence). Every non-eligible outcome is an operational zero.'
                            % (R.STALL, list(P11.AGENT_EXITS), list(P11.TIME_EXITS)),
        prompt_bytes=manifest.get('prompt_bytes'), prior_results=prior_results(root),
        interpretations=manifest.get('interpretations'), inherited_labels=manifest.get('inherited_labels'),
        semantics_differences=manifest.get('semantics_differences'), scope=manifest.get('scope'),
        published=OUTPUTS['published'] + '/probe')
    P11.write_raw(raw / 'pair_summary.json', summary)
    P11.publish(raw, ctx['pub'], [r['run_id'] for r in rows if r.get('run_id') and (raw / r['run_id']).is_dir()])
    return summary


def main(argv=None, root=ROOT, probes=None, runner=None, clock=time.time, gate_check=None, preflight=None):
    ap = argparse.ArgumentParser(description='DTR-REQ-012 no-model repair gate and single 7B DEVELOPMENT probe')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--admission-only', action='store_true', help='print the probe admission record; start nothing')
    mode.add_argument('--gate', action='store_true', help='the no-model repair gate (one container, no model)')
    ap.add_argument('--watchdog', metavar='CONFIG', help=argparse.SUPPRESS)   # internal: started by run_probe
    args = ap.parse_args(argv)
    if args.watchdog:
        return P11.watchdog(args.watchdog)
    if args.gate:
        return gate_main(root, probes, clock, preflight)
    raw, pub = root / OUTPUTS['raw'] / 'probe', root / OUTPUTS['published'] / 'probe'
    if not args.admission_only:
        if raw.exists() or pub.exists():
            print('DTR-REQ-012 probe is single-shot: %s/probe or %s/probe already exists; no automatic resume or '
                  're-dispatch' % (OUTPUTS['raw'], OUTPUTS['published']), file=sys.stderr)
            return 3
        ok, detail = (gate_check or probe_gate)(root)
        if not ok:
            print('DTR-REQ-012 probe refused before its namespace: no passing gate record for this manifest and these '
                  'sources: %s' % json.dumps(S.sanitize(detail)), file=sys.stderr)
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
    summary = OrderedDict(request=REQUEST, kind='single-episode DEVELOPMENT repair probe summary (the file name '
                                                'pair_summary.json is that of the reused req011_pair publication)',
                          manifest=MANIFEST_REL, manifest_sha256=adm['manifest_sha256'],
                          admission_sha256=P11.write_raw(raw / 'admission.json', adm), configuration=R.CONFIGURATION,
                          started_utc=S.utc(start), probe_deadline_utc=S.utc(start + CAPS['pair_wall_s']), status=None,
                          stop_reason=None, interrupted_or_error=None)
    sources = (adm.get('sources') or {}).get('detail') or {}
    ctx = dict(root=root, raw=raw, pub=pub, start=start, pair_deadline=start + CAPS['pair_wall_s'], clock=clock,
               manifest=manifest, manifest_sha256=adm['manifest_sha256'], summary=summary, records=[],
               ledger=P11.Ledger(raw / 'ledger.jsonl', clock),
               sources={k: v['sha256'] for key in ('req011_sources', 'req012_sources')
                        for k, v in (sources.get(key) or {}).items()},
               runtime=sources.get('cue_runtime'))
    if not adm['admitted']:
        summary.update(status='BLOCKED', executed=False, failed_admission_checks=[
            k for k, v in adm.items() if isinstance(v, dict) and v.get('ok') is False])
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
