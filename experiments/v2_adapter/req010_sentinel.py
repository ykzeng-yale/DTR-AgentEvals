"""DTR-REQ-010 (lead 20246b8, docs/theory_feedback_20260924_req009_decision.md): ONE DEVELOPMENT evaluator-qualification
sentinel on REQ-009 queue rank 1 (astropy__astropy-14598). No model, GPU or paid service; one worker.

The controls are the existing, validated `qualification_batch.qualify` (stock gold, adapter reference, adapter
no_change, five-key bae161f acceptance), called unchanged; its adapter keeps its own single identical retry for a
timeout, missing/unparsable report or invalid completion. This driver adds only:
  * binding (an admission check): REQ-009 queue sha256 and rank 1;
  * a contemporaneous admission record: exact source/lock/evaluator-tree hashes; amd64 translation and runtime; image
    keys and local digests; no conflicting worker/peer job (process argv, listeners, peer lease/window records); no
    leftover sentinel containers; isolation; >= 20 GiB free in the VM and >= 15 GiB on the host. Any failure -> BLOCKED,
    nothing run, no substitution;
  * a hard two-hour wall-clock cap from driver start through cleanup: the parent kills the child's process group at the
    attempt deadline (cap minus a cleanup reserve), and the child arms a backup alarm 30 s later, so the cap holds even if
    the parent dies. Parent SIGINT/SIGTERM/SIGHUP also stop the child, collect receipts and clean up;
  * at most one identical retry of the whole attempt, only for a stock-harness timeout or a missing stock report with
    test output present; a stock setup failure (no test output: image build or patch application) is a diagnosis;
  * raw harness trees and receipts kept per attempt under work/runs (git-ignored); published copies under
    results/v2_adapter/req010_sentinel_20260924/ are sanitized (repository path -> '.', home -> '~') and hashed.
Usage (from the pinned evaluator venv):
  work/venvs/swebench_f7bbbb2/bin/python experiments/v2_adapter/req010_sentinel.py [--admission-only]
"""
from __future__ import annotations

import argparse
import calendar
import getpass
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HOME = Path.home()
TARGET = 'astropy__astropy-14598'
REQ009_JSON = 'results/v2_adapter/req009_component_queue.json'
QUEUE_SHA = 'd19efbc4b14eb249f7cbe69429b4a6e53e962bee77ff6736d05bb20eb000d4cc'
DATA = 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
DATA_SHA = 'a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
INSTANCES = 'results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl'
INSTANCES_SHA = 'cee2e8760d9a1f3389031c709fd854af7d7a662499bd152ddeb62491f38dec64'
LOCK = 'results/v2_adapter/m01_c104f840_f7bbbb2/dependency_lock.txt'
LOCK_SHA = '3997c20233148bb7a240bd4131482aea8430b6c21e53d6ae1015129f3cc14208'
EVAL_TARBALL = 'work/upstream/SWE-bench-f7bbbb2.tar.gz'
EVAL_TARBALL_SHA = 'b36fe073d6057c20c714a09d2d05265ed658319f4bcf2c874037ac8cc0420c82'
EVALUATOR_COMMIT = 'f7bbbb2ccdf479001d6467c9e34af59e44a840f9'
EVAL_TREE = 'work/upstream/SWE-bench-' + EVALUATOR_COMMIT
VENV_PY = 'work/venvs/swebench_f7bbbb2/bin/python'
CONTROL_SOURCES = ('experiments/v2_adapter/qualification_batch.py', 'experiments/v2_adapter/control_adapter.py',
                   'experiments/v2_adapter/docker_runtime.py', 'experiments/v2_adapter/qualify_instances.py',
                   'experiments/v2_adapter/grading_conformance.py', 'experiments/v2_adapter/req010_sentinel.py', LOCK)
OUT = 'results/v2_adapter/req010_sentinel_20260924'
RUN = 'work/runs/req010_sentinel_20260924'
CAP_SECONDS = 7200
CLEANUP_RESERVE_SECONDS = 600          # the last attempt is killed this long before the cap, leaving time to clean up
CHILD_BACKUP_DELAY_SECONDS = 30        # the child's own alarm fires this long after the parent's deadline
KILL_GRACE_SECONDS = 20
MIN_VM_GB, MIN_HOST_GB = 20, 15
ADAPTER_CONTAINERS = tuple('dtr-qual-astropy-astropy-14598-%s-%d' % (m, n) for m in ('reference', 'nochange')
                           for n in (1, 2))
CONFLICT_EXECUTABLES = ('llama-server', 'ollama', 'vllm', 'mlx_lm.server')
CONFLICT_SCRIPTS = ('qualification_batch.py', 'pilot_runner.py', 'cue_runner.py', 'req010_sentinel.py')
CONFLICT_MODULES = ('swebench.harness.run_evaluation', 'mlx_lm.server', 'vllm.entrypoints.openai.api_server')
WATCHED_PORTS = (8091, 8092, 8191, 8193, 8291, 8293)
PEER_REPO_DIR = HOME / 'DTR-MultiRoundLLM'
PEER_REPO_API = 'ykzeng-yale/DTR-MultiRoundLLM'
PEER_STATUS_FILE = 'docs/experiments_status.md'
PEER_STATUS_MAX_AGE_SECONDS = 3 * 3600
CREDENTIAL_NAME = re.compile(r'(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|ACCESS_KEY|CREDENTIAL|AUTH|SESSION|COOKIE)', re.I)
COLIMA = HOME / '.local/dtr-runtime/bin/colima'
DOCKER_SOCK = HOME / '.colima/dtr/docker.sock'
STOCK_RECEIPTS = ('report.json', 'eval.sh', 'patch.diff', 'run_instance.log', 'test_output.txt')
_Z = r'(?:\.\d+)?(?:Z|[+-]00:?00)'
ISO = re.compile(r'(\d{4}-\d\d-\d\d)T(\d\d:\d\d(?::\d\d)?)' + _Z +
                 r'(?:\s+to\s+(?:(\d{4}-\d\d-\d\d)T)?(\d\d:\d\d(?::\d\d)?)' + _Z + ')?')
LOOSE_TIMESTAMP = re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d')


class Blocked(SystemExit):
    pass


class Interrupted(BaseException):
    pass


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def utc(t=None) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


def epoch(date: str, clock: str) -> float:
    return calendar.timegm(time.strptime(date + 'T' + (clock if clock.count(':') == 2 else clock + ':00'),
                                         '%Y-%m-%dT%H:%M:%S'))


def sanitize(obj):
    """Every occurrence of the repository path -> '.', of the home directory -> '~' (recursively)."""
    if isinstance(obj, str):
        return obj.replace(str(ROOT), '.').replace(str(HOME), '~')
    if isinstance(obj, dict):
        return OrderedDict((sanitize(k), sanitize(v)) for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return [sanitize(x) for x in obj]
    return obj


def write_json_x(path: Path, obj):
    text = json.dumps(sanitize(obj), indent=1, default=str) + '\n'
    with open(path, 'x') as fh:
        fh.write(text)
    return sha_bytes(text.encode())


def scrub_env(env: dict):
    """Child environment without credential-like variables; returns (env, removed variable NAMES only)."""
    removed = sorted(k for k in env if CREDENTIAL_NAME.search(k))
    return {k: v for k, v in env.items() if k not in removed}, removed


def sh(cmd, env=None, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, '', str(e)


def docker_env():
    env = dict(os.environ)
    env['DOCKER_HOST'] = 'unix://' + str(DOCKER_SOCK)
    env['PATH'] = str(COLIMA.parent) + ':' + env.get('PATH', '')
    return env


# ------------------------------------------------------------------ admission probes
def probe_binding(root: Path):
    q = json.loads((root / REQ009_JSON).read_bytes())
    listed = sha_bytes(''.join(i + '\n' for i in q['queue']).encode())
    d = OrderedDict(req009_record=REQ009_JSON, req009_record_sha256=sha_file(root / REQ009_JSON),
                    queue_sha256_recorded=q['queue_sha256'], queue_sha256_recomputed=listed, rank1=q['queue'][0],
                    rank1_reason=q['exclusion_reason'].get(TARGET), target=TARGET)
    ok = q['queue_sha256'] == listed == QUEUE_SHA and q['queue'][0] == TARGET and d['rank1_reason'] == 'candidate'
    return ok, d


def evaluator_tree_check(root: Path):
    """Every regular file of the pinned tarball must equal the installed editable tree (build/, __pycache__ and
    *.egg-info ignored); .py files in the tree that are not in the tarball are reported and fail the check."""
    mism, missing, members = [], [], set()
    tree = root / EVAL_TREE
    with tarfile.open(root / EVAL_TARBALL) as tf:
        for m in tf:
            if not m.isfile():
                continue
            relp = m.name.split('/', 1)[1] if '/' in m.name else m.name
            members.add(relp)
            p = tree / relp
            if not p.exists():
                missing.append(relp)
            elif sha_bytes(tf.extractfile(m).read()) != sha_file(p):
                mism.append(relp)

    def ignored(parts):
        return any(x in ('build', '__pycache__') or x.endswith('.egg-info') for x in parts)
    extra = sorted(str(p.relative_to(tree)) for p in tree.rglob('*.py')
                   if not ignored(p.relative_to(tree).parts) and str(p.relative_to(tree)) not in members)
    return OrderedDict(files_compared=len(members), mismatched=mism, missing=missing, extra_py=extra,
                       ok=not mism and not missing and not extra)


def probe_sources(root: Path):
    d = OrderedDict()
    d['dataset_sha256'] = sha_file(root / DATA) if (root / DATA).exists() else None
    d['instances_sha256'] = sha_file(root / INSTANCES)
    d['evaluator_tarball_sha256'] = sha_file(root / EVAL_TARBALL) if (root / EVAL_TARBALL).exists() else None
    d['lock_sha256'] = sha_file(root / LOCK)
    lock = [x for x in (root / LOCK).read_text().splitlines() if x and not x.startswith('#')]
    rc, freeze, _ = sh([str(root / VENV_PY), '-m', 'pip', 'freeze'])
    frozen = [x for x in freeze.splitlines() if x and not x.startswith('-e ')]
    d['venv_freeze_equals_lock_except_editable_evaluator'] = rc == 0 and sorted(frozen) == sorted(lock)
    rc, ver, _ = sh([str(root / VENV_PY), '-c', 'import swebench; print(swebench.__version__, swebench.__file__)'])
    parts = ver.split() if rc == 0 else []
    d['swebench_version'] = parts[0] if parts else None
    d['swebench_imported_from_pinned_tree'] = len(parts) > 1 and parts[1].startswith(str(root / EVAL_TREE))
    d['evaluator_tree'] = evaluator_tree_check(root) if d['evaluator_tarball_sha256'] == EVAL_TARBALL_SHA else None
    srcs = OrderedDict()
    for s in CONTROL_SOURCES:
        tracked = sh(['git', '-C', str(root), 'ls-files', '--error-unmatch', s])[0] == 0
        clean = sh(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--', s])[0] == 0
        srcs[s] = OrderedDict(sha256=sha_file(root / s), tracked=tracked, unchanged_from_head=clean)
    d['control_sources'] = srcs
    d['head_commit'] = sh(['git', '-C', str(root), 'rev-parse', 'HEAD'])[1].strip()
    ok = (d['dataset_sha256'] == DATA_SHA and d['instances_sha256'] == INSTANCES_SHA and d['lock_sha256'] == LOCK_SHA
          and d['evaluator_tarball_sha256'] == EVAL_TARBALL_SHA and bool(d['evaluator_tree'])
          and d['evaluator_tree']['ok'] and d['venv_freeze_equals_lock_except_editable_evaluator']
          and d['swebench_version'] == '4.1.0' and d['swebench_imported_from_pinned_tree']
          and all(v['tracked'] and v['unchanged_from_head'] for v in srcs.values()))
    return ok, d


def probe_runtime(root: Path, run=sh, colima_yaml=None):
    d = OrderedDict()
    rc, out, _ = run([str(COLIMA), 'list', '--json'], env=docker_env())
    prof = None
    for line in out.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if isinstance(j, dict) and j.get('name') == 'dtr':
            prof = j
    d['colima_profile'] = None if prof is None else OrderedDict((k, prof.get(k)) for k in ('name', 'status', 'arch',
                                                                                            'cpus', 'memory', 'disk'))
    binfmt = OrderedDict()
    for h in ('rosetta', 'qemu-x86_64'):
        rc, out, _ = run([str(COLIMA), 'ssh', '--profile', 'dtr', '--', 'cat', '/proc/sys/fs/binfmt_misc/' + h],
                         env=docker_env())
        binfmt[h] = (out.splitlines() or [''])[0].strip() if rc == 0 else 'absent'
    d['binfmt'] = binfmt
    if colima_yaml is None:
        cfg = HOME / '.colima/dtr/colima.yaml'
        colima_yaml = cfg.read_text() if cfg.exists() else ''
    vm = re.search(r'^vmType:\s*(\S+)', colima_yaml, re.M)
    d['colima_config'] = OrderedDict(vmType=vm.group(1) if vm else None,
                                     rosetta=bool(re.search(r'^rosetta:\s*true', colima_yaml, re.M)))
    rc, out, _ = run(['docker', 'info', '--format', '{{json .}}'], env=docker_env())
    try:
        info = json.loads(out) if rc == 0 else {}
    except ValueError:
        info = {}
    d['docker'] = OrderedDict(server=info.get('ServerVersion'), kernel_arch=info.get('Architecture'),
                              os=info.get('OperatingSystem'), ncpu=info.get('NCPU'), mem_bytes=info.get('MemTotal'),
                              running_containers=info.get('ContainersRunning'))
    d['translation_mode'] = 'rosetta (colima vz)' if binfmt['rosetta'] == 'enabled' else 'unverified'
    ok = (bool(prof) and prof.get('status') == 'Running' and d['colima_config'] == {'vmType': 'vz', 'rosetta': True}
          and binfmt['rosetta'] == 'enabled' and binfmt['qemu-x86_64'] in ('disabled', 'absent') and bool(info))
    return ok, d


def probe_images(root: Path, run=sh):
    m01 = next(json.loads(l) for l in (root / INSTANCES).read_text().splitlines() if json.loads(l)['instance_id'] == TARGET)
    keys = OrderedDict((k, m01[k + '_image_key']) for k in ('base', 'env', 'instance'))
    local = OrderedDict()
    for k, key in keys.items():
        rc, out, _ = run(['docker', 'image', 'inspect', '--format', '{{.Id}} {{.Architecture}}', key], env=docker_env())
        parts = out.split() if rc == 0 else []
        local[k] = OrderedDict(key=key, present=len(parts) == 2, digest=parts[0] if len(parts) == 2 else None,
                               arch=parts[1] if len(parts) == 2 else None)
    d = OrderedDict(image_keys=keys, local_images=local, eval_script_sha256=m01['eval_script_sha256'],
                    note='the instance image is built locally with --namespace none; digests of all three images are '
                         'recorded again after the attempt')
    ok = all(keys.values()) and all(v['arch'] == 'amd64' for v in local.values() if v['present'])
    return ok, d


def is_python(name: str) -> bool:
    return bool(re.match(r'^[Pp]ython(\d+(\.\d+)?)?$', name))


def conflicting(argv: list):
    """The matching rule for a conflicting job, from argument tokens (never substrings of inline code), or None."""
    if not argv:
        return None
    exe = Path(argv[0]).name
    if exe in CONFLICT_EXECUTABLES:
        return 'executable:' + exe
    if not is_python(exe):
        return None
    i = 1
    while i < len(argv) and argv[i].startswith('-') and argv[i] not in ('-m', '-c'):
        i += 2 if argv[i] in ('-X', '-W') else 1
    if i >= len(argv) or argv[i] == '-c':
        return None
    if argv[i] == '-m':
        return 'module:' + argv[i + 1] if i + 1 < len(argv) and argv[i + 1] in CONFLICT_MODULES else None
    script = Path(argv[i]).name
    if script in CONFLICT_SCRIPTS:
        return 'script:' + script
    if script == 'run.py' and '--stage' in argv[i + 1:]:
        return 'script:run.py --stage'
    return None


def process_table(run=sh):
    rc, out, _ = run(['ps', '-axww', '-o', 'pid=,ppid=,args='])
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2:]))
    return rc, rows


def ancestors(rows, pid):
    parent = {p: pp for p, pp, _ in rows}
    seen = set()
    while pid in parent and pid not in seen:
        seen.add(pid)
        pid = parent[pid]
    return seen


def window_ends(text: str):
    """End times (epoch) of every timestamp or 'start to end' span in a window record (a bare end time takes the start's
    date), and the number of timestamp-like tokens the parser could not read (fail closed if > 0)."""
    ends, consumed = [], 0
    for m in ISO.finditer(text):
        d1, t1, d2, t2 = m.groups()
        ends.append(epoch(d2 or d1, t2) if t2 else epoch(d1, t1))
        consumed += len(LOOSE_TIMESTAMP.findall(m.group(0)))
    return ends, len(LOOSE_TIMESTAMP.findall(text)) - consumed


def peer_status(peer_dir=PEER_REPO_DIR, run=sh, now=None):
    """Latest committed peer lease/run state (public API) and every peer window record (local clone at HEAD; never
    fetched or changed). Blocks unless the lease is 'none', the status is fresh and no window record reaches the future."""
    now = time.time() if now is None else now
    d = OrderedDict(peer_repo=PEER_REPO_API)
    rc, out, _ = run(['curl', '-s', '-m', '20', 'https://api.github.com/repos/%s/commits?per_page=1' % PEER_REPO_API])
    try:
        head = json.loads(out)[0]['sha']
    except (ValueError, IndexError, KeyError, TypeError):
        head = None
    d['remote_head'] = head
    text = ''
    if head:
        rc, out, _ = run(['curl', '-s', '-m', '20', 'https://raw.githubusercontent.com/%s/%s/%s'
                          % (PEER_REPO_API, head, PEER_STATUS_FILE)])
        text = out if rc == 0 else ''
    d['status_file'] = PEER_STATUS_FILE
    d['status_sha256'] = sha_bytes(text.encode()) if text else None
    m = re.search(r'\*\*Last updated: (\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)Z\*\*', text)
    d['status_last_updated'] = '%sT%sZ' % m.groups() if m else None
    lease = re.search(r'Run/lease:\s*\*\*([^*]+)\*\*', text)
    d['run_lease'] = lease.group(1).strip() if lease else None
    age = now - epoch(*m.groups()) if m else None
    d['status_age_seconds'] = None if age is None else round(age)
    rc, out, _ = run(['git', '-C', str(peer_dir), 'rev-parse', 'HEAD'])
    d['local_clone_head'] = out.strip() if rc == 0 else None
    rc, out, _ = run(['git', '-C', str(peer_dir), 'ls-tree', '-r', '--name-only', 'HEAD', 'docs'])
    windows = sorted(x for x in out.split() if re.search(r'window', x, re.I) and x.endswith('.json'))
    open_windows, unparsed = [], []
    for w in windows:
        rc, txt, _ = run(['git', '-C', str(peer_dir), 'show', 'HEAD:' + w])
        ends, n_unparsed = window_ends(txt)
        future = [e for e in ends if e > now]
        if future:
            open_windows.append(OrderedDict(file=w, latest_time=utc(max(future))))
        if n_unparsed:
            unparsed.append(OrderedDict(file=w, unparsed_timestamps=n_unparsed))
    d['window_records'] = windows
    d['window_records_reaching_the_future'] = open_windows
    d['window_records_with_unparsed_timestamps'] = unparsed
    d['local_clone_equals_remote_head'] = head is not None and d['local_clone_head'] == head
    ok = (head is not None and d['local_clone_equals_remote_head'] and d['run_lease'] is not None
          and d['run_lease'].lower() == 'none' and age is not None and 0 <= age <= PEER_STATUS_MAX_AGE_SECONDS
          and not open_windows and not unparsed)
    return ok, d


def probe_conflicts(root: Path, run=sh):
    rc, rows = process_table(run)
    mine = ancestors(rows, os.getpid()) | {os.getpid()}
    hits = [OrderedDict(pid=pid, executable=Path(argv[0]).name, rule=conflicting(argv))
            for pid, _, argv in rows if pid not in mine and conflicting(argv)]
    rc2, out, _ = run(['lsof', '-nP', '-iTCP', '-sTCP:LISTEN'])
    listeners = sorted({int(m) for m in re.findall(r':(\d+) \(LISTEN\)', out) if int(m) in WATCHED_PORTS})
    rc3, ps, _ = run(['docker', 'ps', '-a', '--format', '{{.Names}} {{.State}}'], env=docker_env())
    names = [l.split()[0] for l in ps.splitlines() if l.split()]
    running = [l.split()[0] for l in ps.splitlines() if len(l.split()) > 1 and l.split()[1] == 'running']
    leftovers = sorted(n for n in names if n in ADAPTER_CONTAINERS or n.startswith('sweb.eval.' + TARGET + '.'))
    pause = (root / 'work/runs/qualification_20260922/PAUSE').exists()
    pok, peer = peer_status(run=run)
    d = OrderedDict(ps_rc=rc, lsof_rc=rc2, docker_ps_rc=rc3, conflicting_processes=hits,
                    listeners_on_watched_ports=listeners, running_containers=running,
                    leftover_sentinel_containers=leftovers, shared_host_pause_file_present=pause, peer=peer)
    ok = (rc == 0 and rc2 in (0, 1) and rc3 == 0 and not hits and not listeners and not running and not leftovers
          and not pause and pok)
    return ok, d


def probe_isolation(root: Path):
    src = (root / 'experiments/v2_adapter/docker_runtime.py').read_text()
    create = re.search(r'containers\.create\((.*?)\)\n', src, re.S).group(1)
    _, removed = scrub_env(dict(os.environ))
    d = OrderedDict(adapter_create_has_no_volumes_env_privileges_or_host_network=not re.search(
                        r'volumes|environment|network_mode|privileged|cap_add', create),
                    child_env_credential_like_variables_removed=removed,
                    stock_harness='swebench run_evaluation copies files into its containers; no host mounts, host '
                                  'environment or credentials are passed',
                    networking='evaluation containers use the docker default bridge network (no host network); image '
                               'builds fetch sources over the network; recorded, not restricted by this driver')
    return d['adapter_create_has_no_volumes_env_privileges_or_host_network'], d


def probe_disk(root: Path, run=sh):
    rc, out, _ = run([str(COLIMA), 'ssh', '--profile', 'dtr', '--', 'df', '-Pk', '/var/lib/docker'], env=docker_env())
    try:
        vm = int(out.splitlines()[-1].split()[3]) / 1024 / 1024
    except (IndexError, ValueError):
        vm = None
    host = shutil.disk_usage(str(root)).free / 1024 ** 3
    d = OrderedDict(vm_free_gib=None if vm is None else round(vm, 1), host_free_gib=round(host, 1),
                    min_vm_gib=MIN_VM_GB, min_host_gib=MIN_HOST_GB)
    return vm is not None and vm >= MIN_VM_GB and host >= MIN_HOST_GB, d


PROBES = OrderedDict(binding=probe_binding, sources=probe_sources, runtime=probe_runtime, images=probe_images,
                     conflicts=probe_conflicts, isolation=probe_isolation, disk=probe_disk)


def admission(root: Path, probes=None) -> OrderedDict:
    rec = OrderedDict(checked_utc=utc())
    for name, fn in (probes if probes is not None else PROBES).items():
        try:
            ok, detail = fn(root)
        except Exception as e:  # noqa: BLE001  a probe that cannot run is a failed check
            ok, detail = False, OrderedDict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
        rec[name] = OrderedDict(ok=bool(ok), detail=detail)
    rec['admitted'] = all(v['ok'] for v in rec.values() if isinstance(v, dict) and 'ok' in v)
    return rec


# ------------------------------------------------------------------ attempt loop (pure; injected runner/collect/cleanup)
def classify_stock(stock_dir: Path) -> str:
    """timeout | missing_report (both retryable) | setup_failure (no test output: image build or patch application)
    | report_present."""
    t = stock_dir / 'test_output.txt'
    if not t.exists():
        return 'setup_failure'
    if 'Timeout error:' in t.read_text(errors='replace')[-400:]:
        return 'timeout'
    return 'report_present' if (stock_dir / 'report.json').exists() else 'missing_report'


def status_of(attempts: list) -> str:
    last = attempts[-1] if attempts else {}
    if last.get('not_started'):
        return 'NOT_STARTED' if len(attempts) == 1 else 'INCOMPLETE_CAP_BEFORE_RETRY'
    if last.get('stage_failed') == 'deadline':
        return 'INCOMPLETE_DEADLINE'
    if last.get('stage_failed') == 'interrupted':
        return 'INTERRUPTED'
    if last.get('stage_failed') == 'stock_gold':
        return 'DIAGNOSIS_STOCK_' + str(last.get('stock_failure', 'unknown')).upper()
    if last.get('stage_failed'):
        return 'DIAGNOSIS_' + str(last['stage_failed']).upper()
    return 'QUALIFIED' if last.get('qualified') is True else 'NOT_QUALIFIED'


def run_attempts(out: Path, run_attempt, collect, cleanup, clock, start: float, cap=CAP_SECONDS,
                 reserve=CLEANUP_RESERVE_SECONDS, stamp=None, preflight=None):
    """run_attempt(tag, stock_run_id, deadline) -> result dict (raises TimeoutError at the deadline, Interrupted on a
    signal); collect(tag, stock_run_id) -> (receipts dict, stock classification); cleanup(stock_run_id) -> dict;
    preflight() -> (ok, detail), re-checked before a retry. Collection errors are recorded, cleanup always runs and every
    started attempt writes its record no-clobber to out/<TARGET>/attempt-<n>-<stamp>/summary.json. An Interrupted raised
    anywhere is re-raised after the record is written, carrying the compact attempt list as `.attempts`."""
    stamp = stamp or (lambda: time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(clock())))
    attempts = []
    for n in (1, 2):
        deadline = start + cap - reserve
        if clock() >= deadline:
            attempts.append(OrderedDict(attempt=n, not_started='global cap reached before the attempt'))
            break
        if n == 2 and preflight is not None:
            ok, detail = preflight()
            if not ok:
                attempts.append(OrderedDict(attempt=n, not_started='retry preflight failed', preflight=detail))
                break
        tag = 'attempt-%d-%s' % (n, stamp())
        attempt_dir = out / TARGET / tag
        attempt_dir.mkdir(parents=True, exist_ok=False)
        stock_run_id = 'req010-stock-gold-%s' % tag
        t0 = clock()
        interrupted = None
        try:
            rec = run_attempt(tag, stock_run_id, deadline)
        except TimeoutError as e:
            rec = OrderedDict(instance_id=TARGET, stage_failed='deadline', diagnosis='two-hour cap', kill=str(e))
        except Interrupted as e:
            interrupted = e
            rec = OrderedDict(instance_id=TARGET, stage_failed='interrupted', diagnosis='driver received %s' % e)
        except Exception as e:  # noqa: BLE001  retained as a diagnosis
            rec = OrderedDict(instance_id=TARGET, stage_failed='exception', error='%s: %s' % (type(e).__name__, str(e)[:500]))
        rec = OrderedDict(rec)
        stock_class = 'unknown'
        try:
            try:
                rec['receipts'], stock_class = collect(tag, stock_run_id)
            except BaseException as e:  # noqa: BLE001  recorded; cleanup still runs
                interrupted = interrupted or (e if isinstance(e, Interrupted) else None)
                rec['receipts'] = OrderedDict(collect_error='%s: %s' % (type(e).__name__, str(e)[:300]))
        finally:
            try:
                rec['cleanup'] = cleanup(stock_run_id)
            except BaseException as e:  # noqa: BLE001
                interrupted = interrupted or (e if isinstance(e, Interrupted) else None)
                rec['cleanup'] = OrderedDict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
            if rec.get('stage_failed') == 'stock_gold':
                rec['stock_failure'] = stock_class
            if interrupted is not None and rec.get('stage_failed') != 'interrupted':
                rec['interrupted_after_attempt'] = str(interrupted)
            rec.update(attempt=n, stock_run_id=stock_run_id, attempt_wall_seconds=round(clock() - t0, 1),
                       finished_utc=utc(clock()))
            digest = write_json_x(attempt_dir / 'summary.json', rec)
            attempts.append(OrderedDict(attempt=n, dir=str(attempt_dir.relative_to(out)), summary_sha256=digest,
                                        qualified=rec.get('qualified'), stage_failed=rec.get('stage_failed'),
                                        stock_failure=rec.get('stock_failure'), acceptance=rec.get('acceptance'),
                                        cleanup_remaining=(rec['cleanup'] or {}).get('remaining'),
                                        kill=rec.get('kill')))
        if interrupted is not None:
            interrupted.attempts = attempts
            raise interrupted
        if not (rec.get('stage_failed') == 'stock_gold' and stock_class in ('timeout', 'missing_report')):
            break
        attempts[-1]['retry_reason'] = stock_class
    return attempts


# ------------------------------------------------------------------ real runner / receipts / cleanup
def group_members(pgid: int, run=sh):
    """Live (non-zombie) processes of a process group."""
    rc, out, _ = run(['ps', '-axo', 'pid=,pgid=,stat='])
    if rc != 0 or not out.strip():
        return None                                               # unknown: never reported as "gone"
    return [int(p) for p, g, st in (l.split()[:3] for l in out.splitlines() if len(l.split()) >= 3)
            if g.isdigit() and int(g) == pgid and 'Z' not in st]


def signal_group(pgid: int, sig):
    """killpg, falling back to each live member (macOS refuses killpg while an exited leader is unreaped)."""
    try:
        os.killpg(pgid, sig)
        return
    except ProcessLookupError:
        return
    except PermissionError:
        pass
    for pid in group_members(pgid) or []:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def kill_group(pgid: int, grace=None, reap=lambda: None):
    """SIGTERM, a grace period, then SIGKILL to every live member; returns whether no live member remains."""
    grace = KILL_GRACE_SECONDS if grace is None else grace
    reap()
    signal_group(pgid, signal.SIGTERM)
    end = time.time() + grace
    while time.time() < end and group_members(pgid) != []:
        reap()
        time.sleep(0.2)
    reap()
    signal_group(pgid, signal.SIGKILL)
    for _ in range(50):
        reap()
        if group_members(pgid) == []:
            return True
        time.sleep(0.2)
    return False


def wait_wall(p, deadline: float, clock=time.time, step=10.0):
    """Wait for the child against the WALL clock (monotonic time pauses while the host sleeps). Returns when the child
    exits; raises subprocess.TimeoutExpired once clock() >= deadline."""
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            if p.poll() is None:
                raise subprocess.TimeoutExpired('child', 0)
            return
        try:
            p.wait(timeout=min(step, max(0.1, remaining)))
            return
        except subprocess.TimeoutExpired:
            continue


def real_run_attempt(root: Path, env: dict, sources: dict, py=None, script=None):
    def run(tag: str, stock_run_id: str, deadline: float):
        raw = root / RUN / tag
        raw.mkdir(parents=True, exist_ok=False)
        (raw / 'admitted_sources.json').write_text(json.dumps(sources, indent=1))
        result_path = raw / 'child_result.json'
        with open(raw / 'child_stdout.txt', 'x') as log:
            p = subprocess.Popen([str(py or root / VENV_PY), str(script or HERE / 'req010_sentinel.py'), '--child',
                                  str(raw), stock_run_id, str(result_path), repr(deadline + CHILD_BACKUP_DELAY_SECONDS),
                                  str(os.getpid())], cwd=str(root), env=env, start_new_session=True, stdout=log,
                                 stderr=subprocess.STDOUT)
            try:
                wait_wall(p, deadline)
            except subprocess.TimeoutExpired:
                gone = kill_group(p.pid, reap=p.poll)
                raise TimeoutError('child group killed at %s; group confirmed gone: %s' % (utc(deadline), gone))
            except BaseException:
                kill_group(p.pid, grace=5, reap=p.poll)
                raise
        if not result_path.exists():
            raise RuntimeError('child exited %s without a result' % p.returncode)
        return json.loads(result_path.read_text())
    return run


def real_collect(root: Path):
    """Sanitized, hashed copies of the stock harness receipts, build logs and child output into the published dir.
    Published names never end in .log (git-ignored here); raw run-level files are hashed only."""
    def collect(tag: str, stock_run_id: str):
        raw = root / RUN / tag
        pub = root / OUT / TARGET / tag
        stock = raw / 'harness/logs/run_evaluation' / stock_run_id / 'gold' / TARGET
        files = [(stock / f, 'stock_' + f + ('.txt' if f.endswith('.log') else '')) for f in STOCK_RECEIPTS]
        files += [(p, 'build_%s.log.txt' % p.parent.name) for p in sorted((raw / 'harness/logs/build_images').rglob('*.log'))]
        files += [(p, p.name) for p in sorted(raw.glob('*.txt'))]
        receipts = OrderedDict()
        for src, name in files:
            if not src.exists():
                receipts[name] = OrderedDict(present=False)
                continue
            data = src.read_bytes()
            clean = sanitize(data.decode('utf-8', 'replace')).encode()
            with open(pub / name, 'xb') as fh:
                fh.write(clean)
            receipts[name] = OrderedDict(present=True, raw_sha256=sha_bytes(data), published_sha256=sha_bytes(clean),
                                         sanitized=clean != data)
        hashed_only = OrderedDict()
        for q in sorted((raw / 'harness/reports').glob('*.json')) + [raw / 'child_result.json']:
            if q.exists():
                hashed_only[sanitize(str(q))] = sha_file(q)
        receipts['_raw_hashed_only'] = hashed_only
        return receipts, classify_stock(stock)
    return collect


def container_names(stock_run_id: str):
    return sorted(set(ADAPTER_CONTAINERS) | {'sweb.eval.%s.%s' % (TARGET, stock_run_id)})


def real_cleanup(env: dict, run=sh):
    def clean(stock_run_id: str):
        wanted = set(container_names(stock_run_id))
        rc, out, _ = run(['docker', 'ps', '-a', '--format', '{{.Names}}'], env=env, timeout=30)
        mine = sorted(n for n in out.split() if n in wanted)
        rm_rc = run(['docker', 'rm', '-f'] + mine, env=env, timeout=60)[0] if mine else None
        rc2, out2, _ = run(['docker', 'ps', '-a', '--format', '{{.Names}}'], env=env, timeout=30)
        remaining = sorted(n for n in out2.split() if n in wanted) if rc2 == 0 else None
        return OrderedDict(list_rc=rc, found=mine, rm_rc=rm_rc, relist_rc=rc2, remaining=remaining,
                           complete=remaining == [])
    return clean


def should_stop(parent_pid: int, backup_deadline: float, getppid=os.getppid, clock=time.time):
    """Child watchdog condition: the launching parent is gone (re-parented) or the wall-clock backup deadline passed."""
    return getppid() != parent_pid or clock() >= backup_deadline


def backstop(stock_run_id: str):
    """Last resort inside the child: remove this run's containers from the VM, then kill the child's own group."""
    try:
        subprocess.run(['docker', 'rm', '-f'] + container_names(stock_run_id), capture_output=True, timeout=30)
    finally:
        os.killpg(0, signal.SIGKILL)


def child(raw_dir: str, stock_run_id: str, result_path: str, backup_deadline: str, parent_pid: str):
    """Runs inside the pinned evaluator venv: one unchanged `qualify` call for TARGET, guarded by a wall-clock and
    parent-death watchdog that removes this run's containers and kills the child's group."""
    backup, parent = float(backup_deadline), int(parent_pid)
    signal.signal(signal.SIGALRM, lambda *_: backstop(stock_run_id))
    signal.alarm(max(1, int(backup - time.time())))

    def watchdog():
        while True:
            if should_stop(parent, backup):
                backstop(stock_run_id)
            time.sleep(5)
    threading.Thread(target=watchdog, daemon=True).start()
    raw = Path(raw_dir)
    admitted = json.loads((raw / 'admitted_sources.json').read_text())
    changed = [s for s, h in admitted.items() if sha_file(ROOT / s) != h]
    if changed:
        raise SystemExit('sources changed since admission: %s' % changed)
    import platform as pf
    import docker
    import pandas as pd
    import swebench
    from swebench.harness.grading import get_logs_eval
    from swebench.harness.test_spec.test_spec import make_test_spec
    sys.path.insert(0, str(HERE))
    import qualification_batch as QB
    import control_adapter as A
    QB.RUN = raw / 'harness'
    QB.RUN.mkdir(parents=False, exist_ok=False)
    rows = pd.read_parquet(ROOT / DATA)
    row = rows[rows['instance_id'] == TARGET].to_dict('records')
    if len(row) != 1:
        raise SystemExit('target row not unique in the pinned dataset')
    inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row[0].items()}
    m01 = next(json.loads(l) for l in (ROOT / INSTANCES).read_text().splitlines() if json.loads(l)['instance_id'] == TARGET)
    client = docker.from_env()
    info = client.info()
    platform_rec = dict(host_arch=pf.machine(), vm_kernel_arch=info.get('Architecture'), vm_kernel=info.get('KernelVersion'),
                        vm_os=info.get('OperatingSystem'), docker_server=client.version().get('Version'),
                        translation_mode='rosetta (colima vz), verified at admission',
                        resource_limits=dict(cpus=info.get('NCPU'), mem_bytes=info.get('MemTotal')),
                        declared_timeout_seconds=QB.TIMEOUT, evaluator_commit=EVALUATOR_COMMIT, package=swebench.__version__,
                        adapter_version=A.ADAPTER_VERSION, adapter_source_sha256=A.adapter_source_sha256())
    rec = QB.qualify(client, inst, m01, platform_rec, raw, stock_run_id)
    extra = OrderedDict()
    try:                                                   # extras never cost the verdict
        ts = make_test_spec(inst)
        stock = QB.RUN / 'logs/run_evaluation' / stock_run_id / 'gold' / TARGET
        extra['test_spec_eval_script_sha256'] = QB.sha(ts.eval_script)
        extra['stock_eval_sh_sha256'] = QB.sha((stock / 'eval.sh').read_text()) if (stock / 'eval.sh').exists() else None
        extra['stock_container_run_args'] = (getattr(ts, 'docker_specs', None) or {}).get('run_args')
        if (stock / 'test_output.txt').exists():
            smap, found = get_logs_eval(ts, str(stock / 'test_output.txt'))
            req = list(json.loads(inst['FAIL_TO_PASS'])) + list(json.loads(inst['PASS_TO_PASS']))
            extra['stock_required_test_status'] = OrderedDict((t, smap.get(t)) for t in req)
            extra['stock_get_logs_eval_found'] = found
    except Exception as e:  # noqa: BLE001
        extra['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
    rec['sentinel_extra'] = extra
    with open(result_path, 'x') as fh:
        fh.write(json.dumps(rec, indent=1, default=str) + '\n')


def raise_interrupted(signum, _frame):
    """Only the first signal counts: later ones are ignored so cleanup and the records always complete."""
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, signal.SIG_IGN)
    raise Interrupted(signal.Signals(signum).name)


def username_hits(out: Path):
    user = getpass.getuser()
    return sorted(str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()
                  and user.encode() in p.read_bytes()) if len(user) >= 3 else []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--admission-only', action='store_true')
    ap.add_argument('--child', nargs=5, metavar=('RAW_DIR', 'STOCK_RUN_ID', 'RESULT', 'BACKUP_DEADLINE', 'PARENT_PID'))
    a = ap.parse_args(argv)
    if a.child:
        return child(*a.child)
    start = time.time()
    out = ROOT / OUT
    adm = admission(ROOT)
    adm['started_utc'] = utc(start)
    if a.admission_only:
        print(json.dumps(sanitize(adm), indent=1, default=str))
        return
    out.mkdir(parents=True, exist_ok=False)                        # no-clobber: a second launch refuses to start
    adm_sha = write_json_x(out / 'admission.json', adm)
    if not adm['admitted']:
        failed = [k for k, v in adm.items() if isinstance(v, dict) and v.get('ok') is False]
        write_json_x(out / 'sentinel_summary.json', OrderedDict(request='DTR-REQ-010', target=TARGET, status='BLOCKED',
                                                                failed_admission_checks=failed, executed=False,
                                                                admission_sha256=adm_sha))
        raise Blocked('DTR-REQ-010 BLOCKED at admission: %s (nothing executed, no substitution)' % failed)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, raise_interrupted)
    try:
        awake = subprocess.Popen(['caffeinate', '-i', '-s', '-w', str(os.getpid())])
    except OSError:
        awake = None
    env, _ = scrub_env(docker_env())
    sources = OrderedDict((k, v['sha256']) for k, v in adm['sources']['detail']['control_sources'].items())
    attempts, status, err, disk_before = [], None, None, None

    def preflight():
        c_ok, c = probe_conflicts(ROOT)
        d_ok, d = probe_disk(ROOT)
        return c_ok and d_ok, OrderedDict(conflicts_ok=c_ok, disk=d, conflicts=c)
    try:
        disk_before = probe_disk(ROOT)[1]
        attempts = run_attempts(out, real_run_attempt(ROOT, env, sources), real_collect(ROOT), real_cleanup(env),
                                time.time, start, preflight=preflight)
    except Interrupted as e:
        err, attempts = str(e), getattr(e, 'attempts', attempts)
        status = status_of(attempts) if attempts and attempts[-1].get('qualified') is not None else 'INTERRUPTED'
    except Exception as e:  # noqa: BLE001
        err, status = '%s: %s' % (type(e).__name__, str(e)[:300]), 'ERROR'
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        try:
            disk_after, images = probe_disk(ROOT)[1], probe_images(ROOT)[1]['local_images']
        except Exception as e:  # noqa: BLE001
            disk_after, images = OrderedDict(error=str(e)[:200]), None
        end = time.time()
        started = [x for x in attempts if not x.get('not_started')]
        summary = OrderedDict(
            request='DTR-REQ-010', target=TARGET, status=status or status_of(attempts), interrupted_or_error=err,
            attempts=attempts, admission_sha256=adm_sha, started_utc=utc(start), finished_utc=utc(end),
            wall_seconds=round(end - start, 1), cap_seconds=CAP_SECONDS, within_cap=end - start <= CAP_SECONDS,
            cleanup_complete=bool(started) and all(x.get('cleanup_remaining') == [] for x in started),
            process_groups_confirmed_gone=all('confirmed gone: True' in x['kill'] for x in started if x.get('kill')),
            disk_before=disk_before, disk_after=disk_after, images_after=images,
            adapter_retry_rule=('the reused control adapter (control_adapter.py, unchanged) retries once, identically, on a '
                                'timeout or a missing/unparsable report; its invalid-completion branch cannot be reached '
                                'with the pinned get_logs_eval (found=False always comes with an empty map). The stock '
                                'harness writes report.json for logs with bad codes, which is not retried.'),
            scope='one DEVELOPMENT evaluator qualification; no model, GPU or paid service; qualifies at most this issue, '
                  'image and environment; releases no competence pilot')
        write_json_x(out / 'sentinel_summary.json', summary)
        hits = username_hits(out)
        if hits:
            write_json_x(out / 'USERNAME_FOUND.json', OrderedDict(files=hits, action='do not publish until redacted'))
        if awake is not None:
            awake.terminate()
    print(json.dumps(sanitize(summary), indent=1, default=str))


if __name__ == '__main__':
    main()
