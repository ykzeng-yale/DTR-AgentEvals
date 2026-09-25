"""DTR-REQ-014 (lead b9ffb29, docs/theory_feedback_20260924_req013_capacity_decision.md): the REQ-013 live design (ONE
Qwen2.5-Coder-14B DEVELOPMENT episode on astropy__astropy-14598 under the unchanged configuration yaml-v1-repair1)
under a separately versioned capacity rule. The committed manifest configs/v2_req014_14b_capacity_probe_20260924.json
is the specification: its declared rules govern this runner. The probe is not a success rate, not a paired comparison
and not CONFIRM evidence.

    .venv/bin/python experiments/v2_agent/req014_pair.py --prereq                                      (no model)
    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req014_pair.py --admission-only   (read-only)
    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req014_pair.py                    (the probe)

A thin layer over the committed REQ-013 runner (req013_pair.py, and through it req012_pair.py and req011_pair.py),
imported read-only and never edited. Reused unchanged: the admission probes, the REQ-012 gate precondition and
configuration proof (req013_pair.probe_precondition, with its manifest name rebound to this manifest for the call), the
REQ-013 step-1 check, serving, the watchdog loop, the queue and schedule, the episode runner and its settle, grading
and publication. New here: the versioned capacity rule (admission, post-load and in-episode thresholds on physical
memory free and VM/host disk free; swap recorded, not gated), the in-episode supervision that stops only this request's
owned agent and server and classifies a 'capacity_interruption', the resource time series, and the --prereq
current-host watchdog/source re-verification (req013_watchdog_check, unedited, with its output rebound). The stop is one
SIGALRM followed at once by the owned server stop; req014_entry's latch (supervision.entry_latch) makes the entry refuse
every later query even when a container command swallowed the signal, and a container whose ID was never recorded is
swept by supervision.unrecorded_container.
"""
from __future__ import annotations

import argparse
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
for _p in (Path(__file__).resolve().parent, ROOT / 'experiments/v2_adapter'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req013_pair as P13  # noqa: E402  the committed REQ-013 runner, imported read-only

P12, P11, R, PR, S, A = P13.P12, P13.P11, P13.R, P13.PR, P13.S, P13.A
GiB = P11.GiB
rebound = P13.rebound
REQUEST = 'DTR-REQ-014'
MANIFEST_REL = 'configs/v2_req014_14b_capacity_probe_20260924.json'
LEAD_DECISION = 'docs/theory_feedback_20260924_req013_capacity_decision.md'
HOLDER = 'DTR-AgentEvals worker (DTR-REQ-014 14B capacity probe)'
CAPS = dict(P13.CAPS)                                 # identical to REQ-013/REQ-012
RUNTIME = dict(P13.RUNTIME, orchestrator='experiments/v2_agent/req014_pair.py',
               entry='experiments/v2_agent/req014_entry.py')
OUTPUTS = dict(raw='work/runs/req014_14b_capacity_probe_20260924',
               published='results/v2_agent/req014_14b_capacity_probe_20260924', pause_file='work/REQ014_PAUSE',
               private_receipts=A.PRIVATE_RECEIPTS_REL)
NEW_SOURCES = ('experiments/v2_agent/req014_pair.py', 'experiments/v2_agent/req014_entry.py', MANIFEST_REL,
               'tests/test_req014_capacity.py')
SOURCES = P13.SOURCES + NEW_SOURCES
OWN_SCRIPTS = ('req014_pair.py', 'req014_entry.py')
PRIOR_RESULTS = P13.PRIOR_RESULTS                     # REQ-013 produced no probe result
CAPACITY = 'capacity_interruption'
NOT_GRADED = 'not graded: capacity interruption (never an algorithmic zero and never a submitted patch)'
SERIES = 'resource_samples.jsonl'
CAPACITY_PROBES = ('memory', 'disk', 'swap')
LATCH_RECORD = 'capacity_latch.json'                 # written by req014_entry into the episode's control directory
LATCH_OVERRIDES = [                                  # req014_entry.LATCH_OVERRIDES (checked by the fixtures)
    'pilot_episode.request_timeout -> req014_entry latch: the frozen function first, then, once a SIGALRM has been '
    'received, pilot_episode.EpisodeDeadline (no request is dispatched after the signal)',
    "the SIGALRM handler installed by req012_entry.main -> req014_entry chain (installed at the first request_timeout "
    "call): the signal is counted, then the frozen handler raises EpisodeDeadline; after the inference phase has "
    "ended the signal is only counted",
    'cue_terminal.run_terminal_phase -> req014_entry marker: records the end of the inference phase, then the frozen '
    'function']

# ------------------------------------------------------------------ the versioned capacity rule (req014-capacity-v1)
MEMORY = dict(P11.MEMORY, admission_min_free_pct=50, post_load_min_free_pct=20, episode_min_free_pct=10)
DISK = dict(P11.DISK, vm_min_gib=30, host_min_gib=25, episode_vm_min_gib=20, episode_host_min_gib=15)
THRESHOLDS = OrderedDict((phase, OrderedDict(physical_free_pct=pct, vm_disk_free_gib=vm, host_disk_free_gib=host))
                         for phase, pct, vm, host in (
    ('admission', MEMORY['admission_min_free_pct'], DISK['vm_min_gib'], DISK['host_min_gib']),
    ('post_load', MEMORY['post_load_min_free_pct'], DISK['vm_min_gib'], DISK['host_min_gib']),
    ('episode', MEMORY['episode_min_free_pct'], DISK['episode_vm_min_gib'], DISK['episode_host_min_gib'])))
SWAP = OrderedDict(
    command=['sysctl', '-n', 'vm.swapusage'], gated=False,
    parse="exactly one each of 'total = ', 'used = ' and 'free = <number><unit>', unit K, M or G read as KiB, MiB or "
          "GiB; "
          "a nonzero return code or a missing or repeated field is 'unavailable'",
    rule='total/used/free recorded at admission, after the load and in every episode sample; no value is gated. The '
         'reading must be available at admission and after the load (every observation there fails closed); during '
         'the episode an unavailable reading is recorded and stops nothing',
    replaces="REQ-013 swap_rule ('unused swap >= 4 GiB'), superseded by the lead", note=P13.SWAP['note'])
MEASURE_TIMEOUTS = OrderedDict(physical_free_pct=3, vm_disk_free_gib=4, swap=1)
SUPERVISION = OrderedDict(
    version='req014-capacity-v1', thresholds=THRESHOLDS,
    comparison='a value passes when it is >= the minimum of its phase and fails when it is strictly below; an '
               'unavailable or unparsable physical free %, VM disk or host disk value fails closed in every phase',
    measurements=OrderedDict(
        physical_free_pct="`memory_pressure`: the integer N of 'System-wide memory free percentage: N%' "
                          '(req011_pair.memory_free_pct), return code 0',
        vm_disk_free_gib='req010_sentinel.COLIMA ssh --profile dtr -- df -Pk /var/lib/docker with '
                         'req010_sentinel.docker_env(): return code 0 and exactly one df data row (at least 6 fields; '
                         '1024-blocks, Used and Available all digits; Capacity ending in %), other output lines '
                         'ignored; the Available KiB field (the 4th) / 2^20',
        host_disk_free_gib='shutil.disk_usage(<repository root>).free / 2^30, in process',
        swap='swap_record.command, parsed as swap_record.parse'),
    measurement_timeouts_s=MEASURE_TIMEOUTS,
    admission_measurements='the admission probes memory (req011_pair.probe_memory: memory_pressure with its 30 s '
                           'timeout and the projection), disk (VM df with a 60 s timeout, host, work reserve) and swap',
    sample_interval_s=5, max_gap_s=10,
    sampling='post_load: one sample after the owned 14B server has loaded and passed the served-identity check and '
             'before the entry child is spawned; episode: while the parent waits on the entry child, samples start '
             'sample_interval_s apart (start to start; the first at once). Each sample runs its measurements in '
             'sequence, each with its own timeout (3 + 4 + 1 = 8 s at most), so consecutive samples start at most '
             'max_gap_s apart unless the host itself stalls; every gap is recorded and reported, and a late sample '
             'is not a missing one',
    stop='on a failing or unavailable episode value, or a sample that cannot be taken or recorded, while the entry '
         'child is still running (it is polled again right after the sample; exited_child): (1) SIGALRM to the entry '
         "child PID only. The entry's alarm handler (req012_entry.main's, chained by entry_latch) raises "
         'pilot_episode.EpisodeDeadline, and from then on every query is refused before dispatch, also when the '
         'exception was swallowed by a container command (the pinned DockerEnvironment.execute turns any Exception '
         'into a returncode -1 observation); a signal after the inference phase has ended is only counted. The '
         "frozen terminal path follows: the Submitted-only endpoint (submission ''), the all-exit diagnostic, "
         'container cleanup and the records. (2) At once the owned 14B server is stopped (req011_pair.stop_server: '
         'the listener-checked Servers.stop), so nothing can be generated after the signal and its memory is '
         'released. (3) Wait up to caps.child_cleanup_grace_s from the SIGALRM (never past the child wait deadline); '
         'if the child is still alive, kill its process group. (4) The reused req011_pair settle kills what is left '
         'of that group and removes only the container recorded in container_ownership.json; if no ownership record '
         'matched this run, unrecorded_container applies. Nothing else is signalled or removed. The watchdog, the '
         'wall-clock deadlines and the cleanup caps are unchanged',
    entry_latch=OrderedDict(
        entry='experiments/v2_agent/req014_entry.py', overrides=LATCH_OVERRIDES,
        record='control/<run_id>/' + LATCH_RECORD,
        rule='runtime overrides of the entry process only, installed after admission; no request byte changes. The '
             'natural deadline is unchanged (its SIGALRM runs the frozen handler and the frozen request_timeout '
             'refuses first). After a capacity SIGALRM the next query is refused before dispatch as after the '
             'natural deadline, so the agent leaves through the frozen exception path (exit_status EpisodeDeadline) '
             'and the terminal phase and records run. The record lists the overrides, the signals received, whether '
             'the first came after the inference phase had ended and the queries refused by the latch; '
             'entry_admitted.json and repair_record.json keep the two repair1 runtime_overrides'),
    unrecorded_container=(
        'after a capacity interruption in which no container_ownership.json matched this run (the stop can land '
        'while `docker run -d` is in flight, before the container ID is known): the dtr VM containers are listed '
        '(docker ps -a --no-trunc, ID and name) just before the entry child is spawned and again after the settle. A '
        'container is removed (req011_pair.remove_containers, by exact ID) only if its name starts with '
        'minisweagent-, neither its ID nor its name is in the pre-spawn listing, and `docker container inspect` '
        'reports the pinned instance image ID (images.instance.id). Nothing else is removed, and an unavailable '
        'listing removes nothing (as the REQ-012 gate rule for a container started before its ID is known). '
        'Recorded as unrecorded_container_sweep in capacity_interruption.json'),
    exited_child=('a failing sample after which the entry child is found to have exited on its own interrupts '
                  "nothing: the breach is recorded under capacity.breach_after_child_exit, the assignment keeps the "
                  "reused runner's state and outcome, and the normal sequence stops the server"),
    classification="the assignment state is 'capacity_interruption' (an authoritative ledger end event follows the "
                   "reused runner's): never graded, never eligible, never an algorithmic or operational zero, "
                   "whatever the child's exit_status (EpisodeDeadline, or even Submitted), also when the signal "
                   "arrived after the child's inference phase had ended (the latch record says so). Probe status "
                   'CAPACITY_INTERRUPTION. A post-load failure stops the owned server before any agent request: probe '
                   'status BLOCKED, no episode',
    outcome_rule_precedence=(
        "The reused req012_pair.finish writes outcome_source_rule ending 'Every non-eligible outcome is an "
        "operational zero.' That sentence does not apply to a row whose outcome_source is capacity_interruption, nor "
        'to a row not started because the probe was BLOCKED for capacity at admission or after the load (the reused '
        'req011_pair.outcome_source labels it infrastructure_or_supervision). supervision.classification and '
        'interpretations.capacity and capacity_interruption govern those rows: they are not outcomes, never zeros '
        'and never graded. pair_summary.json repeats this rule as capacity_outcome_rule_precedence'),
    series=OrderedDict(
        raw=OUTPUTS['raw'] + '/probe/' + SERIES, published=OUTPUTS['published'] + '/probe/' + SERIES,
        fields=['phase', 't', 'utc', 'physical_free_pct', 'vm_disk_free_gib', 'host_disk_free_gib', 'swap_total_gib',
                'swap_used_gib', 'swap_free_gib', 'measurement_errors', 'measurement_seconds', 'sample_seconds',
                'gap_s (episode samples)', 'problems'],
        durability='one JSON line per sample, appended, flushed and fsync-ed before the sample is acted on; the '
                   'published copy is sanitized (repository path -> ., home -> ~) with raw and published sha256',
        summary=['samples', 'samples_by_phase', 'min_physical_free_pct', 'min_vm_disk_free_gib',
                 'min_host_disk_free_gib', 'peak_swap_used_gib', 'max_episode_sampling_gap_s',
                 'episode_gaps_over_max', 'samples_with_measurement_errors', 'samples_with_problems',
                 'unparsable_lines']))
PREREQ = OrderedDict(
    watchdog_host_check=OUTPUTS['published'] + '/watchdog_host_check.json', raw=OUTPUTS['raw'] + '/watchdog_check',
    command='.venv/bin/python experiments/v2_agent/req014_pair.py --prereq',
    rule='no model: every source of this runner (REQ-011 to REQ-014) tracked and unchanged from HEAD, else nothing is '
         'written; then experiments/tools/req013_watchdog_check.py main, unedited, with its OUT, RAW and REQUEST '
         'rebound to this record, its raw directory and DTR-REQ-014 (write-once, sanitized). The probe requires the '
         'record tracked and unchanged from HEAD, passed true, request DTR-REQ-014, and its recorded req011_pair.py '
         'and tests/test_req011_pair.py sha256 equal to the current files',
    when="before the probe namespace (a refusal consumes nothing) and again as the admission probe 'prereq'")
SAME_AS_REQ013 = ('instance_id', 'images', 'settings', 'repair1', 'prompt_bytes', 'serving', 'evaluator', 'caps',
                  'watchdog', 'precondition', 'step1', 'prior_results')


# ------------------------------------------------------------------ manifest binding
def expected_manifest(conv, req010):
    """REQ-013's machine-checked sections (req013_pair.expected_manifest) with the REQ-014 labels and capacity rule."""
    m13 = P13.expected_manifest(conv, req010)
    out = dict(m13, request=REQUEST, lead_commit='b9ffb29', lead_decision=LEAD_DECISION, source_commit='16d1d9b',
               assignments=[dict(m13['assignments'][0], assignment_id='req014-1-large')], memory_rule=MEMORY,
               disk_rule=DISK, swap_record=SWAP, supervision=SUPERVISION, prereq=PREREQ, runtime=RUNTIME,
               outputs=OUTPUTS)
    del out['swap_rule']
    return out


def manifest_problems(manifest, conv, req010, m13, template=None):
    expected = expected_manifest(conv, req010)
    text = P11.TEXT_KEYS + ('kind', 'prompt_bytes')
    problems = ['manifest %s differs from the bound value' % k for k in expected if manifest.get(k) != expected[k]]
    problems += ['manifest %s is missing' % k for k in text if not manifest.get(k)]
    problems += ['manifest %s differs from the REQ-013 manifest' % k for k in SAME_AS_REQ013
                 if manifest.get(k) != m13.get(k)]
    problems += ['manifest section %s is not part of the REQ-014 design' % k
                 for k in sorted(set(manifest) - set(expected) - set(text))]
    strip = lambda rows: [dict(a, assignment_id=None) for a in rows or []]  # noqa: E731
    if strip(manifest.get('assignments')) != strip(m13.get('assignments')):
        problems.append('the assignment is not the REQ-013 14B row (apart from its assignment_id)')
    if req010.get('status') != 'QUALIFIED' or req010.get('target') != S.TARGET:
        problems.append('the REQ-010 summary does not record %s as QUALIFIED' % S.TARGET)
    if template is not None and manifest.get('prompt_bytes') != R.prompt_bytes(template):
        problems.append('manifest prompt_bytes differ from the pinned default.yaml')
    return problems


def probe_manifest(root, template=None):
    raw = (root / MANIFEST_REL).read_bytes()
    template = R.frozen_template() if template is None else template
    problems = manifest_problems(json.loads(raw), P13.load(root, P11.SERVING['conversion_record']),
                                 P13.load(root, P11.REQ010_SUMMARY_REL), P13.load(root, P13.MANIFEST_REL), template)
    if S.sha_file(root / P11.SERVING['conversion_record']) != P11.SERVING['conversion_record_sha256']:
        problems.append('conversion record sha256 differs from the bound value')
    return not problems, OrderedDict(manifest=MANIFEST_REL, manifest_sha256=S.sha_bytes(raw), problems=problems,
                                     prompt_bytes=R.prompt_bytes(template))


# ------------------------------------------------------------------ precondition, step 1 and the prerequisite
def digest(path):
    return S.sha_file(path) if Path(path).is_file() else None


def probe_gate(root, **kwargs):
    """req013_pair.probe_precondition (the passing REQ-012 gate and the configuration proof) for THIS manifest."""
    with rebound(P13, MANIFEST_REL=MANIFEST_REL):
        return P13.probe_precondition(root, **kwargs)


def probe_prereq(root, run=S.sh):
    rel = PREREQ['watchdog_host_check']
    row = P12.source_rows(root, (rel,), run)[rel]
    rec = P11.load_json(root / rel) or {}
    src = rec.get('scenario_source') or {}
    current = lambda key, rel2: src.get(key) is not None and src.get(key) == digest(root / rel2)  # noqa: E731
    d = OrderedDict(record=rel, sha256=row['sha256'], tracked=row['tracked'],
                    unchanged_from_head=row['unchanged_from_head'], passed=rec.get('passed') is True,
                    request=rec.get('request'),
                    watchdog_source_current=current('watchdog_source_sha256', 'experiments/v2_agent/req011_pair.py'),
                    fixture_file_current=current('fixture_file_sha256', 'tests/test_req011_pair.py'),
                    rule=PREREQ['rule'])
    return (row['tracked'] and row['unchanged_from_head'] and d['passed'] and d['request'] == REQUEST
            and d['watchdog_source_current'] and d['fixture_file_current']), d


def preconditions(root, run=S.sh, **gate_kwargs):
    checks = OrderedDict(gate=probe_gate(root, **gate_kwargs), step1=P13.probe_step1(root, run),
                         prereq=probe_prereq(root, run))
    return all(ok for ok, _ in checks.values()), OrderedDict((k, d) for k, (_, d) in checks.items())


def prereq_main(root=ROOT, run=S.sh, check=None):
    """No model: the source checks, then the unedited REQ-013 watchdog host check written under REQ-014 (write-once)."""
    rows = P12.source_rows(root, SOURCES, run)
    bad = [k for k, v in rows.items() if not (v['sha256'] and v['tracked'] and v['unchanged_from_head'])]
    if bad:
        print('DTR-REQ-014 prereq refused (nothing written): sources not tracked or changed from HEAD: %s' % bad,
              file=sys.stderr)
        return 3
    if str(ROOT / 'experiments/tools') not in sys.path:
        sys.path.insert(0, str(ROOT / 'experiments/tools'))
    import req013_watchdog_check as W   # imports the REQ-011 fixture module (pytest): run with .venv/bin/python
    with rebound(W, OUT=PREREQ['watchdog_host_check'], RAW=PREREQ['raw'], REQUEST=REQUEST):
        return (check or W.main)(root=root)


# ------------------------------------------------------------------ measurements
SWAP_FIELD = re.compile(r'\b(total|used|free) = ([0-9]+(?:\.[0-9]+)?)([KMG])\b')


def capped(run, seconds):
    return lambda cmd, env=None, timeout=60: run(cmd, env=env, timeout=min(timeout, seconds))


def vm_disk_free_gib(run=S.sh, timeout=60):
    cmd = [str(S.COLIMA), 'ssh', '--profile', 'dtr', '--', 'df', '-Pk', '/var/lib/docker']
    rc, out, _ = run(cmd, env=S.docker_env(), timeout=timeout)
    rows = [f for f in (x.split() for x in (out or '').splitlines())
            if len(f) >= 6 and all(v.isdigit() for v in f[1:4]) and f[4].endswith('%')]
    return int(rows[0][3]) / (1 << 20) if rc == 0 and len(rows) == 1 else None


def host_disk_free_gib(root, usage=shutil.disk_usage):
    return usage(str(root)).free / GiB


def swap_usage(run=S.sh, timeout=30):
    """{total, used, free} in bytes, or None."""
    rc, out, _ = run(list(SWAP['command']), timeout=timeout)
    hits = SWAP_FIELD.findall(out or '') if rc == 0 else []
    if sorted(h[0] for h in hits) != ['free', 'total', 'used']:
        return None
    return OrderedDict((name, int(float(value) * P13.UNITS[unit])) for name, value, unit in hits)


def swap_gib(usage):
    return OrderedDict(('swap_%s_gib' % k, None if not usage else round(usage[k] / GiB, 3))
                       for k in ('total', 'used', 'free'))


def measure(root, run=S.sh, usage=shutil.disk_usage, clock=time.monotonic):
    """One observation of each quantity, each with its own timeout; a failure is recorded as unavailable (never
    raised)."""
    errors, seconds = OrderedDict(), OrderedDict()

    def take(name, fn):
        t0 = clock()
        try:
            value = fn()
        except Exception as e:  # noqa: BLE001  recorded; the value is unavailable
            value, errors[name] = None, '%s: %s' % (type(e).__name__, str(e)[:200])
        seconds[name] = round(clock() - t0, 3)
        if value is None:
            errors.setdefault(name, 'unavailable or unparsable')
        return value
    t = MEASURE_TIMEOUTS
    out = OrderedDict(
        physical_free_pct=take('physical_free_pct', lambda: P11.memory_free_pct(capped(run, t['physical_free_pct']))),
        vm_disk_free_gib=take('vm_disk_free_gib', lambda: vm_disk_free_gib(run, t['vm_disk_free_gib'])),
        host_disk_free_gib=take('host_disk_free_gib', lambda: host_disk_free_gib(root, usage)))
    out.update(swap_gib(take('swap', lambda: swap_usage(run, t['swap']))))
    out.update(measurement_errors=errors, measurement_seconds=seconds)
    return out


def capacity_problems(sample, phase):
    """Every failed or unavailable threshold of the phase (an empty list passes)."""
    problems = []
    for key, low in THRESHOLDS[phase].items():
        value = sample.get(key)
        if type(value) not in (int, float):
            problems.append('%s unavailable (fails closed)' % key)
        elif value < low:
            problems.append('%s %s is below %s' % (key, round(value, 3), low))
    if phase != 'episode' and sample.get('swap_used_gib') is None:
        problems.append('the swap record is unavailable (recorded, not gated; every observation is required here)')
    return problems


def append_line(path, obj):
    with open(path, 'a') as fh:
        fh.write(json.dumps(obj, default=str) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def make_sampler(path, measure_fn, clock=time.time):
    """sample(phase): measure, evaluate the phase thresholds, append durably, return the sample."""
    last = []

    def sample(phase):
        t = clock()
        s = OrderedDict(phase=phase, t=t, utc=S.utc(t))
        s.update(measure_fn())
        s['sample_seconds'] = round(clock() - t, 3)
        if phase == 'episode':
            s['gap_s'] = round(t - last[-1], 3) if last else None
            last.append(t)
        s['problems'] = capacity_problems(s, phase)
        append_line(path, s)
        return s
    return sample


def admission_sample(adm, t):
    detail = lambda k: (adm.get(k) or {}).get('detail') or {}  # noqa: E731
    s = OrderedDict(phase='admission', t=t, utc=S.utc(t), physical_free_pct=detail('memory').get('memory_free_pct'),
                    vm_disk_free_gib=detail('disk').get('vm_disk_free_gib'),
                    host_disk_free_gib=detail('disk').get('host_disk_free_gib'))
    s.update((k, detail('swap').get(k)) for k in ('swap_total_gib', 'swap_used_gib', 'swap_free_gib'))
    s.update(source='the admission probes memory, disk and swap (admission.json)',
             problems=capacity_problems(s, 'admission'))
    return s


# ------------------------------------------------------------------ admission (REQ-013 probes with the REQ-014 rule)
def probe_memory(root, assignments, run=S.sh):
    """req011_pair.probe_memory (memory_pressure and the model + KV + VM projection) at the REQ-014 threshold."""
    _, d = P11.probe_memory(root, assignments, run)
    free, limit = d['memory_free_pct'], d['projection_limit_bytes']
    d.update(rule=MEMORY, replaced_rule=P11.MEMORY)
    return (free is not None and free >= MEMORY['admission_min_free_pct'] and limit is not None
            and all(v <= limit for v in d['projection_bytes'].values())), d


def probe_disk(root, run=S.sh, usage=shutil.disk_usage):
    vm, host = vm_disk_free_gib(run), host_disk_free_gib(root, usage)   # an exception fails the probe (S.admission)
    reserve = A.free_space_check(root / 'work', host_reserve_bytes=CAPS['host_reserve_bytes'], disk_usage=usage)
    d = OrderedDict(vm_disk_free_gib=vm, host_disk_free_gib=host, work_free_space_refusal=reserve, rule=DISK,
                    replaced_rule=P11.DISK)
    return (vm is not None and vm >= DISK['vm_min_gib'] and host is not None and host >= DISK['host_min_gib']
            and reserve is None), d


def probe_swap(root, run=S.sh):
    usage = swap_usage(run)
    return usage is not None, OrderedDict(command=SWAP['command'], observed=usage is not None, gated=False,
                                          rule=SWAP['rule'], **swap_gib(usage))


def probe_sources(root, run=S.sh, base=S.probe_sources, compute_binding=None):
    ok, d = P13.probe_sources(root, run, base, compute_binding)
    d['req014_sources'] = P12.source_rows(root, NEW_SOURCES, run)
    return ok and all(v['tracked'] and v['unchanged_from_head'] for v in d['req014_sources'].values()), d


def other_req014_processes(run=S.sh):
    _, rows = S.process_table(run)
    mine = S.ancestors(rows, os.getpid()) | {os.getpid()}
    return [pid for pid, _, argv in rows if pid not in mine and any(Path(x).name in OWN_SCRIPTS for x in argv[:3])]


def probe_conflicts(root, run=S.sh):
    ok, d = P13.probe_conflicts(root, run)
    d['req014_pause_file_present'] = (root / OUTPUTS['pause_file']).exists()
    d['other_req014_processes'] = other_req014_processes(run)
    return ok and not d['req014_pause_file_present'] and not d['other_req014_processes'], d


def admission_probes(manifest):
    """req013_pair.admission_probes with the REQ-014 manifest, sources, conflicts and capacity probes, plus prereq."""
    probes, queue = P13.admission_probes(manifest), manifest['assignments']
    probes.update(manifest=probe_manifest, sources=probe_sources, conflicts=probe_conflicts, disk=probe_disk,
                  memory=lambda root: probe_memory(root, queue), swap=probe_swap, gate=probe_gate)
    probes['prereq'] = probe_prereq
    return probes


# ------------------------------------------------------------------ serving, watchdog (REQ-014 labels)
class Servers(P11.Servers):
    """pilot_runner.Servers through the REQ-011 subclass; the ownership record is re-labelled for DTR-REQ-014."""

    def _record(self):
        super()._record()
        rec = json.loads(PR.SERVERS.read_text())
        rec['holder'] = HOLDER
        tmp = PR.SERVERS.with_suffix('.tmp')
        tmp.write_text(json.dumps(rec, indent=1) + '\n')
        os.replace(tmp, PR.SERVERS)


def spawn_watchdog(raw, deadline, env, popen=subprocess.Popen, **kwargs):
    """req013_pair.spawn_watchdog with the REQ-014 label and holder, started through this script (the popen wrapper
    replaces only the script path); the loop is req011_pair.watchdog, unchanged."""
    def launch(cmd, **options):
        return popen([cmd[0], str(Path(__file__).resolve())] + list(cmd[2:]), **options)
    with rebound(P13, REQUEST=REQUEST, HOLDER=HOLDER):
        return P13.spawn_watchdog(raw, deadline, env, popen=launch, **kwargs)


# ------------------------------------------------------------------ post-load gate and in-episode supervision
def take_sample(sampler, phase):
    try:
        s = sampler(phase)
        return s, s['problems']
    except Exception as e:  # noqa: BLE001  a sample that cannot be taken or recorded fails closed
        return None, ['the %s sample could not be taken or recorded: %s: %s' % (phase, type(e).__name__, str(e)[:200])]


def make_serve(servers, ctx, sampler, base=None):
    """req011_pair.make_serve (load, GET-only served identity, the inherited 10 % check), then the post-load gate before
    the entry is spawned: a failure stops the owned server and raises the gate (BLOCKED, no episode)."""
    base = base or P11.make_serve(servers, ctx)

    def serve(a):
        inherited = None
        try:
            base(a)
        except P11.Gate as e:
            if 'checks' not in (ctx['served'].get(a['backend']) or {}):
                raise                                  # nothing finished loading: not a post-load capacity question
            inherited = e
        s, problems = take_sample(sampler, 'post_load')
        if problems:
            ctx['capacity_block'] = OrderedDict(stage='post-load', breach=problems, sample=s,
                                                inherited_gate=None if inherited is None else str(inherited))
            P11.stop_server(servers, ctx)
            ctx['capacity_block']['server_stopped'] = servers.live is None
            raise P11.Gate('capacity (post-load): %s' % '; '.join(problems))
        if inherited is not None:
            raise inherited
    return serve


WAIT_WALL = S.wait_wall            # the original; S.wait_wall is rebound only while the entry child is supervised


def interrupt(p, deadline, out, caps, clock, stop_server=None):
    """SIGALRM to the entry child only, at once the owned server stop, then the child cleanup grace (from the signal)
    and the child's process group if the child is still alive. Fills and returns `out`."""
    t0 = clock()
    out.update(utc=S.utc(t0), child_pid=p.pid, stop_method=SUPERVISION['stop'])
    try:
        os.kill(p.pid, signal.SIGALRM)
        out['sigalrm_sent'] = True
    except ProcessLookupError:
        out['sigalrm_sent'] = False
    if stop_server is not None:                     # no generation after the signal, and its memory is released
        out['server_stopped_after_sigalrm'] = stop_server()
        out['server_stop_seconds_after_sigalrm'] = round(clock() - t0, 3)
    try:
        WAIT_WALL(p, min(t0 + caps['child_cleanup_grace_s'], deadline), clock=clock, step=1.0)
        out['child_exited_within_grace'] = True
    except subprocess.TimeoutExpired:
        out['child_exited_within_grace'] = False
        out['process_group_gone_after_kill'] = S.kill_group(p.pid, reap=p.poll)
    out['child_returncode'] = p.poll()
    return out


def supervised_wait(ctx, sampler, caps=CAPS, interval=None, stop_server=None):
    """A drop-in for req010_sentinel.wait_wall (same arguments and wall-clock semantics) that samples while it waits."""
    interval = SUPERVISION['sample_interval_s'] if interval is None else interval

    def wait(p, deadline, clock=time.time, step=None):
        next_at = clock()
        while p.poll() is None:
            if clock() >= deadline:
                raise subprocess.TimeoutExpired('child', 0)
            if clock() >= next_at:
                s, problems = take_sample(sampler, 'episode')
                if problems and p.poll() is not None:        # it ended on its own meanwhile: nothing to interrupt
                    ctx.setdefault('capacity_breach_after_child_exit', []).append(OrderedDict(
                        utc=S.utc(clock()), breach=problems, sample=s, child_returncode=p.returncode,
                        rule=SUPERVISION['exited_child']))
                    return
                if problems:
                    rec = ctx.get('capacity_rec') or {}
                    cap = ctx['capacity_interruption'] = OrderedDict(   # set first: a later signal still sees it
                        classification=CAPACITY, run_id=rec.get('run_id'), order=rec.get('order'), breach=problems,
                        breaching_sample=s)
                    interrupt(p, deadline, cap, caps, clock, stop_server)
                    return
                next_at = s['t'] + interval
            try:
                p.wait(timeout=max(0.05, min(next_at, deadline) - clock()))
            except subprocess.TimeoutExpired:
                pass
    return wait


def container_listing(ctx):
    """[(ID, name)] of every container the dtr VM lists, or None if the listing failed."""
    rc, out, _ = ctx['run'](['docker', 'ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.Names}}'], env=ctx['env'],
                            timeout=max(5, min(30, (ctx['pair_deadline'] - ctx['clock']()) / 3)))
    return None if rc != 0 else [tuple(x.split()[:2]) for x in (out or '').splitlines() if len(x.split()) >= 2]


def sweep_unrecorded(ctx, before):
    """supervision.unrecorded_container: remove only new minisweagent-* containers of the pinned instance image."""
    out = OrderedDict(rule=SUPERVISION['unrecorded_container'], listed_before_spawn=before, listed_now=None,
                      new_minisweagent_containers=None, images=None, removed_ids=[], removal=None)
    now = container_listing(ctx) if before is not None else None
    out['listed_now'] = now
    if before is None or now is None:
        out['reason'] = 'a container listing was unavailable: nothing is removed'
        return out
    known = {x for row in before for x in row}
    new = [[cid, name] for cid, name in now if name.startswith('minisweagent-') and cid not in known
           and name not in known]
    images = OrderedDict()
    for cid, _ in new:
        rc, image, _ = ctx['run'](['docker', 'container', 'inspect', '--format', '{{.Image}}', cid], env=ctx['env'],
                                  timeout=30)
        images[cid] = (image or '').strip() if rc == 0 else None
    out.update(new_minisweagent_containers=new, images=images, pinned_image=ctx['image_id'],
               removed_ids=[cid for cid, _ in new if images[cid] == ctx['image_id']])
    out['removal'] = P11.remove_containers(out['removed_ids'], run=ctx['run'], env=ctx['env'],
                                           deadline=ctx['pair_deadline'], clock=ctx['clock'])
    return out


def make_episode_runner(ctx, servers, sampler, caps=CAPS, interval=None):
    """req011_pair.make_episode_runner, unchanged, with its child wait supervised; after a capacity interruption the
    assignment is classified 'capacity_interruption' (the owned server was stopped right after the SIGALRM, and is
    stopped again here if that failed) and an unrecorded container is swept (supervision.unrecorded_container)."""
    base = P11.make_episode_runner(ctx, caps)

    def stop_server():
        P11.stop_server(servers, ctx)                 # only this request's owned server (listener-checked)
        return servers.live is None

    def run(a, counted_before, rec):
        ctx['capacity_rec'] = rec
        before = container_listing(ctx)               # just before the entry is spawned
        with rebound(S, wait_wall=supervised_wait(ctx, sampler, caps, interval, stop_server)):
            gate = base(a, counted_before, rec)
        cap = ctx.get('capacity_interruption')
        if cap is None:
            return gate
        cap.update(server_stopped=stop_server(), state_reported_by_the_reused_runner=rec.get('state'),
                   process_group_gone=rec.get('process_group_gone'), owned_container=rec.get('owned_container'),
                   container_removal=rec.get('container_removal'))
        control = ctx['raw'] / 'control' / rec['run_id']
        if rec.get('owned_container') is None:
            cap['unrecorded_container_sweep'] = sweep_unrecorded(ctx, before)
        cap['entry_latch'] = P11.load_json(control / LATCH_RECORD)
        rec.update(state=CAPACITY, capacity_interruption=cap)
        ctx['ledger'].end(a['order'], state=CAPACITY, run_id=rec.get('run_id'))
        P11.write_raw(control / 'capacity_interruption.json', cap)
        sweep = (cap.get('unrecorded_container_sweep') or {}).get('removal')
        extra = [gate] if gate else []
        if sweep is not None and not sweep['complete']:
            extra.append('unrecorded container removal unconfirmed')
        return 'capacity interruption: %s%s' % ('; '.join(cap['breach']), ' (and %s)' % '; '.join(extra) if extra
                                                else '')
    return run


def supervise(ctx, servers, sampler, serve=None, grader=None, interval=None):
    """The REQ-013 sequence (queue, server stop, grading) with the post-load gate and the supervised episode; a capacity
    interruption is never graded."""
    try:
        stop = P11.run_episodes(ctx['manifest']['assignments'], ctx['pair_deadline'],
                                make_serve(servers, ctx, sampler, serve),
                                make_episode_runner(ctx, servers, sampler, CAPS, interval), ctx['records'],
                                clock=ctx['clock'], pause=ctx['root'] / OUTPUTS['pause_file'], caps=CAPS)
    finally:
        P11.stop_server(servers, ctx)
        ctx['summary']['watchdog'] = P11.release_watchdog(ctx.get('watchdog'), servers)
    grade = grader or P11.make_grader(ctx, CAPS)
    for rec in ctx['records']:
        if not rec.get('run_id'):
            rec['grade'] = OrderedDict(status='no grade: assignment not started')
        elif rec.get('state') == CAPACITY:
            rec['grade'] = OrderedDict(status=NOT_GRADED)
        else:
            rec['grade'] = OrderedDict(status='ungraded: grading did not complete (interrupted or error)')
            rec['grade'] = grade(rec)
    return stop


def run_probe(ctx):
    """req013_pair.run_probe's setup and cleanup (scrubbed environment, watchdog before the load, backstops) around
    supervise()."""
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
    sampler = make_sampler(raw / SERIES, lambda: measure(root), ctx['clock'])
    backstops = ctx.setdefault('backstops', OrderedDict())
    try:
        ctx['watchdog'], ctx['watchdog_ready'] = spawn_watchdog(raw, ctx['pair_deadline'], dict(os.environ))
        return supervise(ctx, servers, sampler)
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


# ------------------------------------------------------------------ summary and publication
def series_stats(rows):
    def values(key):
        return [r[key] for r in rows if type(r.get(key)) in (int, float)]

    def low(key):
        return min(values(key)) if values(key) else None
    gaps = values('gap_s')
    return OrderedDict(
        samples=len(rows),
        samples_by_phase=OrderedDict((p, sum(r.get('phase') == p for r in rows)) for p in THRESHOLDS),
        min_physical_free_pct=low('physical_free_pct'), min_vm_disk_free_gib=low('vm_disk_free_gib'),
        min_host_disk_free_gib=low('host_disk_free_gib'),
        peak_swap_used_gib=max(values('swap_used_gib')) if values('swap_used_gib') else None,
        max_episode_sampling_gap_s=max(gaps) if gaps else None,
        episode_gaps_over_max=sum(g > SUPERVISION['max_gap_s'] for g in gaps),
        samples_with_measurement_errors=sum(bool(r.get('measurement_errors')) for r in rows),
        samples_with_problems=sum(bool(r.get('problems')) for r in rows))


def capacity_record(ctx):
    """The series statistics and its sanitized published copy, plus the post-load block and the interruption."""
    src, dst = ctx['raw'] / SERIES, ctx['pub'] / SERIES
    data = src.read_bytes() if src.exists() else b''
    rows, unparsable = [], 0
    for line in data.decode('utf-8', 'replace').splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:                            # counted, never fatal
            row = None
        if isinstance(row, dict):
            rows.append(row)
        else:
            unparsable += 1
    published = None
    if src.exists():
        clean = S.sanitize(data.decode('utf-8', 'replace')).encode()
        with open(dst, 'xb') as fh:
            fh.write(clean)
        published = OrderedDict(raw=str(src.relative_to(ctx['root'])), published=str(dst.relative_to(ctx['root'])),
                                raw_sha256=S.sha_bytes(data), published_sha256=S.sha_bytes(clean),
                                sanitized=clean != data)
    return OrderedDict(version=SUPERVISION['version'], thresholds=THRESHOLDS,
                       series=OrderedDict(series_stats(rows), unparsable_lines=unparsable), series_files=published,
                       post_load_block=ctx.get('capacity_block'), interruption=ctx.get('capacity_interruption'),
                       breach_after_child_exit=ctx.get('capacity_breach_after_child_exit'),
                       outcome_rule=SUPERVISION['classification'])


def reclassify_cut_short(ctx):
    """A capacity interruption whose runner was cut short (a signal) before it reclassified its row: classify the row
    here, with the same authoritative ledger end event."""
    cap = ctx.get('capacity_interruption') or {}
    for r in ctx['records']:
        if cap.get('run_id') and r.get('run_id') == cap['run_id'] and r.get('state') != CAPACITY:
            r.update(state_reported_by_the_reused_runner=r.get('state'), state=CAPACITY, capacity_interruption=cap,
                     capacity_state_set_by='finish (the runner was cut short before its own reclassification)')
            r.setdefault('grade', OrderedDict(status=NOT_GRADED))
            try:
                ctx['ledger'].end(r['order'], state=CAPACITY, run_id=r['run_id'])
            except Exception as e:  # noqa: BLE001  recorded; the row is still classified
                r['capacity_ledger_error'] = '%s: %s' % (type(e).__name__, str(e)[:200])


def finish(ctx, summary, manifest):
    """req012_pair.finish (as req013_pair.finish, with REQ-014 outputs), with 'capacity_interruption' as its own outcome
    source and never eligible; the capacity record and the outcome-rule precedence are added to the summary first."""
    reclassify_cut_short(ctx)
    interrupted = {r.get('run_id') for r in ctx['records'] if r.get('state') == CAPACITY}
    base_facts, base_source = P11.episode_facts, P12.outcome_source

    def facts(run_dir, run_id, root=ROOT, control_dir=None):
        out = base_facts(run_dir, run_id, root, control_dir)
        if run_id in interrupted:
            out.update(eligible_without_the_capacity_rule=out.get('eligible'), eligible=False)
        return out

    def source(state, exit_status, eligible):
        return CAPACITY if state == CAPACITY else base_source(state, exit_status, eligible)
    try:                                              # the capacity record never costs the summary or publication
        summary['capacity'] = capacity_record(ctx)
    except Exception as e:  # noqa: BLE001  recorded
        summary['capacity'] = OrderedDict(
            version=SUPERVISION['version'], error='%s: %s' % (type(e).__name__, str(e)[:300]),
            post_load_block=ctx.get('capacity_block'), interruption=ctx.get('capacity_interruption'),
            breach_after_child_exit=ctx.get('capacity_breach_after_child_exit'),
            outcome_rule=SUPERVISION['classification'])
    summary['capacity_outcome_rule_precedence'] = SUPERVISION['outcome_rule_precedence']
    with rebound(P12, OUTPUTS=OUTPUTS, PRIOR_RESULTS=PRIOR_RESULTS, outcome_source=source,
                 OUTCOME_SOURCES=P12.OUTCOME_SOURCES + (CAPACITY,)), rebound(P11, episode_facts=facts):
        return P12.finish(ctx, summary, manifest)


def status_of(ctx, stop):
    return ('CAPACITY_INTERRUPTION' if ctx.get('capacity_interruption') else 'BLOCKED' if ctx.get('capacity_block')
            else 'STOPPED' if stop else 'COMPLETED')


def main(argv=None, root=ROOT, probes=None, runner=None, clock=time.time, precondition=None):
    ap = argparse.ArgumentParser(description='DTR-REQ-014 single 14B DEVELOPMENT probe (versioned capacity rule)')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--admission-only', action='store_true', help='print the admission record; start nothing')
    mode.add_argument('--prereq', action='store_true', help='no model: source checks and the host watchdog check')
    ap.add_argument('--watchdog', metavar='CONFIG', help=argparse.SUPPRESS)   # internal: started by run_probe
    args = ap.parse_args(argv)
    if args.watchdog:
        return P11.watchdog(args.watchdog)
    if args.prereq:
        return prereq_main(root)
    raw, pub = root / OUTPUTS['raw'] / 'probe', root / OUTPUTS['published'] / 'probe'
    if not args.admission_only:
        if raw.exists() or pub.exists():
            print('DTR-REQ-014 probe is single-shot: %s/probe or %s/probe already exists; no automatic resume or '
                  're-dispatch' % (OUTPUTS['raw'], OUTPUTS['published']), file=sys.stderr)
            return 3
        ok, detail = (precondition or preconditions)(root)
        if not ok:
            print('DTR-REQ-014 probe refused before its namespace (nothing consumed): the REQ-012 gate, the '
                  'configuration proof, REQ-013 step 1 or the REQ-014 prerequisite did not pass: %s'
                  % json.dumps(S.sanitize(detail), default=str), file=sys.stderr)
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
    try:                                              # a later sample of the same file then fails closed
        append_line(raw / SERIES, admission_sample(adm, start))
        series_error = None
    except Exception as e:  # noqa: BLE001  recorded in the summary
        series_error = '%s: %s' % (type(e).__name__, str(e)[:300])
    summary = OrderedDict(request=REQUEST, kind='single-episode DEVELOPMENT 14B capacity-probe summary (the file name '
                                                'pair_summary.json is that of the reused req011_pair publication)',
                          manifest=MANIFEST_REL, manifest_sha256=adm['manifest_sha256'],
                          admission_sha256=P11.write_raw(raw / 'admission.json', adm), configuration=R.CONFIGURATION,
                          started_utc=S.utc(start), probe_deadline_utc=S.utc(start + CAPS['pair_wall_s']), status=None,
                          stop_reason=None, interrupted_or_error=None, step1=P13.step1_facts(root),
                          prereq=OrderedDict(record=PREREQ['watchdog_host_check'],
                                             sha256=digest(root / PREREQ['watchdog_host_check'])))
    if series_error:
        summary['admission_sample_not_recorded'] = series_error
    sources = (adm.get('sources') or {}).get('detail') or {}
    ctx = dict(root=root, raw=raw, pub=pub, start=start, pair_deadline=start + CAPS['pair_wall_s'], clock=clock,
               manifest=manifest, manifest_sha256=adm['manifest_sha256'], summary=summary, records=[],
               ledger=P11.Ledger(raw / 'ledger.jsonl', clock),
               sources={k: v['sha256'] for key in ('req011_sources', 'req012_sources', 'req013_sources',
                                                   'req014_sources') for k, v in (sources.get(key) or {}).items()},
               runtime=sources.get('cue_runtime'))
    if not adm['admitted']:
        failed = [k for k, v in adm.items() if isinstance(v, dict) and v.get('ok') is False]
        summary.update(status='BLOCKED', executed=False, failed_admission_checks=failed,
                       capacity_checks_failed=[k for k in failed if k in CAPACITY_PROBES])
        finish(ctx, summary, manifest)
        print(json.dumps(S.sanitize({k: summary[k] for k in ('status', 'failed_admission_checks')})))
        return 2
    old = {sig: signal.signal(sig, S.raise_interrupted) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        summary['stop_reason'] = (runner or run_probe)(ctx)
        summary['status'] = status_of(ctx, summary['stop_reason'])
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
