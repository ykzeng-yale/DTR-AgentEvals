"""DTR-REQ-002 repository-diversity runtime qualification (lead 93588ab; manifest configs/v2_runtime_smoke_expansion_20260922.json).
Authorized by the author (2026-09-22). Runs in work/venvs/swebench_f7bbbb2 on the approved runtime (Colima arm64 VM,
Rosetta amd64). Development runtime qualification only: not performance evaluation or CONFIRM.

For each selected task NOT already completed (flask is reused), serially, with the manifest's limits:
  1. stock gold: unmodified `python -m swebench.harness.run_evaluation --predictions_path gold --instance_ids <id>
     --namespace none --max_workers 1 --timeout 1800 --cache_level instance` (keeps the instance image so the
     adapter uses the identical digest)
  2. adapter reference and adapter no_change (control_adapter v2 + docker_runtime binding) on that digest
  3. the bae161f acceptance: pins/script hashes agree; stock/reference required-test maps and strict outcomes agree;
     reference qualifies; no_change qualifies (declared empty-P2P limitation honoured)
Every selected task is recorded; build/stock/adapter failures are retained as diagnoses (no substitution). Outputs are
no-clobber per task. Between tasks the batch honours a pause file (work/runs/qualification_20260922/PAUSE) for shared-
host coordination and a VM disk guard; neither changes a result, and a stop leaves an explicit incomplete record.
  python experiments/v2_adapter/qualification_batch.py
"""
from __future__ import annotations
import hashlib, json, os, platform, subprocess, sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import control_adapter as A  # noqa: E402
import docker_runtime as DR  # noqa: E402
import qualify_instances as Q  # noqa: E402
from grading_conformance import declared_outcome  # noqa: E402

MANIFEST = ROOT / 'configs/v2_runtime_smoke_expansion_20260922.json'
DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
DATA_SHA = 'a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
RUN = ROOT / 'work/runs/qualification_20260922'
OUT = ROOT / 'results/v2_adapter/qualification_20260922'
PAUSE = RUN / 'PAUSE'
STOCK_RUN_ID = 'qual-stock-gold'
TIMEOUT = 1800
MIN_FREE_GB = 20
COLIMA = str(Path.home() / '.local/dtr-runtime/bin/colima')


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def vm_free_gb():
    out = subprocess.run([COLIMA, 'ssh', '--profile', 'dtr', '--', 'df', '-Pk', '/var/lib/docker'], capture_output=True, text=True,
                         env=dict(os.environ, PATH=str(Path(COLIMA).parent) + ':' + os.environ.get('PATH', ''))).stdout.splitlines()
    try:
        return int(out[-1].split()[3]) / 1024 / 1024
    except Exception:  # noqa: BLE001
        return None


def qualify(client, inst, m01, platform_rec, attempt_dir, stock_run_id):
    from swebench.harness.grading import get_logs_eval
    from swebench.harness.test_spec.test_spec import make_test_spec
    iid = inst['instance_id']
    rec = dict(instance_id=iid, repo=inst['repo'], version=inst['version'], stock_run_id=stock_run_id, attempt_dir=attempt_dir.name,
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    q = Q.qualify(inst)
    (f2p, e1), (p2p, e2) = Q.parse_test_list(inst, 'FAIL_TO_PASS'), Q.parse_test_list(inst, 'PASS_TO_PASS')
    rec['limitations'] = q['limitations']
    ts = make_test_spec(inst)
    # 1. stock gold (unmodified harness)
    t0 = time.time()
    p = subprocess.run([sys.executable, '-m', 'swebench.harness.run_evaluation', '--dataset_name', str(DATA), '--split', 'train',
                        '--predictions_path', 'gold', '--instance_ids', iid, '--run_id', stock_run_id, '--namespace', 'none',
                        '--max_workers', '1', '--timeout', str(TIMEOUT), '--cache_level', 'instance', '--report_dir', 'reports'],
                       cwd=RUN, capture_output=True, text=True)
    rec['stock_wall_seconds'] = time.time() - t0
    rec['stock_exit'] = p.returncode
    sdir = RUN / 'logs/run_evaluation' / stock_run_id / 'gold' / iid
    (attempt_dir / 'stock_stdout_tail.txt').write_text(p.stdout[-4000:] + '\n--- stderr ---\n' + p.stderr[-4000:])
    if not (sdir / 'report.json').exists() or not (sdir / 'test_output.txt').exists():
        rec.update(stage_failed='stock_gold', diagnosis='no stock report/test output (image build or evaluation failure; see run_instance/build logs)',
                   run_instance_log_tail=(sdir / 'run_instance.log').read_text()[-3000:] if (sdir / 'run_instance.log').exists() else None)
        return rec
    stock_log = (sdir / 'test_output.txt').read_text()
    stock_report = json.loads((sdir / 'report.json').read_text())
    stock_eval_sh = (sdir / 'eval.sh').read_text()
    stock_map, stock_found = get_logs_eval(ts, str(sdir / 'test_output.txt'))
    stock_strict = declared_outcome(f2p, p2p, stock_map, log_ok=stock_found)
    (attempt_dir / 'stock_gold_test_output.txt').write_text(stock_log)
    imgs = {k: client.images.get(getattr(ts, k + '_image_key')) for k in ('base', 'env', 'instance')}
    digests = {k: v.id for k, v in imgs.items()}
    rec_inst = dict(instance_id=iid, eval_script_sha256=m01['eval_script_sha256'], FAIL_TO_PASS=f2p, PASS_TO_PASS=p2p,
                    empty_p2p_declared=bool(q['limitations']))
    parse = DR.parser_binding(ts)
    out = {}
    for mode in ('reference', 'no_change'):
        rt = DR.DockerRuntime(client, ts, 'dtr-qual-%s-%s' % (iid.replace('__', '-').lower(), mode.replace('_', '')))
        r = A.run_control(mode, rec_inst, rt, ts.eval_script, parse, digests,
                          reference_patch=inst['patch'] if mode == 'reference' else None, timeout=TIMEOUT)
        r['runtime_events'] = rt.events
        for i, lg in enumerate(rt.logs, 1):
            (attempt_dir / ('adapter_%s_attempt%d_test_output.txt' % (mode, i))).write_text(lg['text'])
            r['attempts'][i - 1]['eval_runtime_seconds'] = lg['runtime_seconds']
        out[mode] = r
    ref, nch = out['reference'], out['no_change']
    ref_map = ref['attempts'][-1].get('per_test_status') or {}
    req = list(f2p) + list(p2p)
    map_diff = {t: (stock_map.get(t), ref_map.get(t)) for t in req if stock_map.get(t) != ref_map.get(t)}
    acc = dict(pins_and_script_hashes_agree=(sha(ts.eval_script) == m01['eval_script_sha256'] == sha(stock_eval_sh) == ref['eval_script_sha256'] == nch['eval_script_sha256']),
               stock_reference_required_test_maps_agree=not map_diff,
               stock_reference_strict_outcomes_agree=(stock_strict == 'resolved') == bool(ref['strict_verified_resolved']),
               reference_passes_required_tests=ref['qualification'] == 'qualified',
               no_change_meets_rule=nch['qualification'] == 'qualified')
    rec.update(image_digests=digests, image_userland_arch={k: v.attrs.get('Architecture') for k, v in imgs.items()},
               required_tests=dict(fail_to_pass=len(f2p), pass_to_pass=len(p2p)),
               stock=dict(resolved=stock_report.get(iid, {}).get('resolved'), strict_outcome=stock_strict, get_logs_eval_found=stock_found,
                          required_status_counts={s: sum(1 for t in req if stock_map.get(t) == s) for s in set(stock_map.get(t) for t in req)}),
               adapter_reference=ref, adapter_no_change=nch, stock_vs_reference_required_status_differences=map_diff,
               acceptance=acc, qualified=all(acc.values()), platform=platform_rec)
    return rec


class ConflictingRecord(SystemExit):
    pass


EVALUATOR_COMMIT = 'f7bbbb2ccdf479001d6467c9e34af59e44a840f9'
LEGACY_MANIFEST = OUT / 'legacy_hash_manifest.json'


def expected_identity(manifest_path=MANIFEST):
    man = json.loads(Path(manifest_path).read_text())
    return dict(manifest_sha256=sha(Path(manifest_path).read_bytes()), source_sha256=man['source_sha256'],
                dataset_sha256=DATA_SHA, evaluator_commit=EVALUATOR_COMMIT)


def is_terminal(rec):
    """A finished qualification verdict (qualified + acceptance) or a finished diagnosis (stage_failed)."""
    if rec.get('status') == 'running' or not rec.get('finished_utc'):
        return False
    return (isinstance(rec.get('qualified'), bool) and isinstance(rec.get('acceptance'), dict)) or bool(rec.get('stage_failed'))


def task_state(out, iid, expected=None, legacy=None):
    """completed (terminal record with verified identity, or listed by hash in the legacy manifest) | incomplete | new.
    Unparsable, wrong-instance or wrong-source records fail explicitly BEFORE any execution (lead fd5f42c): a matching
    instance ID alone is never enough."""
    check_legacy(legacy, expected)
    d = Path(out) / iid
    if not d.exists():
        return 'new', None, None
    legacy_ok = {(e['instance_id'], e['sha256']) for e in (legacy or {}).get('records', [])}
    unbound = None
    for s in [d / 'summary.json'] + sorted(d.glob('attempt-*/summary.json')):
        if not s.exists():
            continue
        raw = s.read_bytes()
        try:
            rec = json.loads(raw)
        except ValueError:
            raise ConflictingRecord('unparsable summary %s: refusing to guess' % s)
        if rec.get('instance_id') != iid:
            raise ConflictingRecord('summary %s names %r, not %r' % (s, rec.get('instance_id'), iid))
        digest = hashlib.sha256(raw).hexdigest()
        ev = rec.get('identity', {}).get('evaluator_commit') or rec.get('platform', {}).get('evaluator_commit')
        if expected and ev and ev != expected['evaluator_commit']:
            raise ConflictingRecord('summary %s names evaluator %s, expected %s' % (s, ev, expected['evaluator_commit']))
        if not is_terminal(rec):
            continue                                                # e.g. a running or ID-only record stays incomplete
        if 'identity' in rec:
            if expected and rec['identity'] != expected:
                raise ConflictingRecord('summary %s has source/manifest identity %r, expected %r' % (s, rec['identity'], expected))
            return 'completed', s, digest
        if (iid, digest) in legacy_ok:                               # legacy record bound by an immutable hash manifest
            return 'completed', s, digest
        unbound = unbound or s
    if unbound is not None:                                          # terminal but not bound: reconcile, never rerun (lead 7cb2062)
        raise ConflictingRecord('terminal record %s has no identity and no valid legacy hash binding: needs reconciliation, '
                                'not an automatic rerun' % unbound)
    return 'incomplete', d, None


def check_legacy(legacy, expected):
    """A legacy hash manifest is admissible only if its FULL expected_identity equals the current expected identity."""
    if legacy is None:
        return
    if not expected or legacy.get('expected_identity') != expected:
        raise ConflictingRecord('legacy hash manifest identity %r does not match expected %r: stale manifest refused'
                                % (legacy.get('expected_identity'), expected))


def build_legacy_manifest(out, expected, path=None):
    """Bind existing (pre-identity) terminal records by immutable SHA-256 without rewriting them; verified on re-read."""
    path = Path(path or Path(out) / 'legacy_hash_manifest.json')
    recs = []
    for d in sorted(Path(out).iterdir()):
        s = d / 'summary.json'
        if d.is_dir() and s.exists():
            raw = s.read_bytes(); rec = json.loads(raw)
            if rec.get('instance_id') == d.name and is_terminal(rec) and 'identity' not in rec:
                ev = rec.get('platform', {}).get('evaluator_commit')
                if ev and ev != expected['evaluator_commit']:
                    raise ConflictingRecord('legacy %s names evaluator %s' % (s, ev))
                verdict = isinstance(rec.get('qualified'), bool) and isinstance(rec.get('acceptance'), dict)
                recs.append(dict(instance_id=d.name, summary='%s/summary.json' % d.name, sha256=hashlib.sha256(raw).hexdigest(),
                                 terminal='verdict' if verdict else 'stage_failed', qualified=rec.get('qualified') if verdict else False))
    man = dict(note='immutable hash binding of legacy qualification records written before identity fields (lead fd5f42c); records not rewritten',
               expected_identity=expected, records=recs)
    with open(path, 'x') as fh:
        fh.write(json.dumps(man, indent=1) + '\n')
    for r in recs:                                                   # independent re-read check
        assert hashlib.sha256((Path(out) / r['summary']).read_bytes()).hexdigest() == r['sha256']
    return man


def run_queue(todo, out, qualify_fn, status, pause=None, free_fn=None, min_free=MIN_FREE_GB, stamp=None, expected=None, legacy=None):
    """Restart-safe serial queue (lead e360831): completed tasks are validated and skipped BEFORE any execution; an
    incomplete prior attempt is retained and a new no-clobber attempt directory (with its own stock run ID, so no cached
    harness report is reused) is created before the stock run; conflicting records fail explicitly."""
    stamp = stamp or (lambda: time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    status.setdefault('completed', []); status.setdefault('skipped_completed', []); status.setdefault('incomplete_prior_attempts', [])
    states = {iid: task_state(out, iid, expected, legacy) for iid in todo}   # every conflict raises before ANY execution
    for iid in todo:
        state, path, digest = states[iid]
        if state == 'completed':
            status['skipped_completed'].append(dict(instance_id=iid, summary=str(Path(path).relative_to(out)), sha256=digest))
            continue
        if pause is not None and Path(pause).exists():
            status['stopped'] = 'paused before %s (shared-host coordination)' % iid
            break
        free = free_fn() if free_fn else None
        if free is not None and free < min_free:
            status['stopped'] = 'VM disk guard: %.1f GB free < %d GB before %s' % (free, min_free, iid)
            break
        if state == 'incomplete':
            status['incomplete_prior_attempts'].append(dict(instance_id=iid, retained=str(Path(path).relative_to(out))))
            tag = stamp()
            attempt_dir, stock_run_id = Path(out) / iid / ('attempt-' + tag), 'qual-stock-gold-' + tag
        else:
            attempt_dir, stock_run_id = Path(out) / iid, STOCK_RUN_ID
        attempt_dir.mkdir(parents=True, exist_ok=False)                 # output preflight BEFORE the stock run
        try:
            rec = qualify_fn(iid, attempt_dir, stock_run_id)
        except Exception as e:  # noqa: BLE001  retained as a diagnosis
            rec = dict(instance_id=iid, stage_failed='exception', error='%s: %s' % (type(e).__name__, str(e)[:500]),
                       traceback=traceback.format_exc()[-3000:])
        rec['vm_free_gb_before'] = free
        if expected:
            rec['identity'] = expected
        rec['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with open(attempt_dir / 'summary.json', 'x') as fh:
            fh.write(json.dumps(rec, indent=1, default=str) + '\n')
        status['completed'].append(dict(instance_id=iid, attempt=str(attempt_dir.relative_to(out)), qualified=rec.get('qualified', False),
                                        stage_failed=rec.get('stage_failed'), acceptance=rec.get('acceptance')))
        (Path(out) / 'status.json').write_text(json.dumps(status, indent=1, default=str) + '\n')
        print(iid, 'qualified=%s' % rec.get('qualified'), rec.get('stage_failed') or '', flush=True)
    return status


def main():
    import docker
    import pandas as pd
    import swebench
    if sha(DATA.read_bytes()) != DATA_SHA:
        raise SystemExit('dataset checksum mismatch')
    man = json.loads(MANIFEST.read_text())
    if sha((ROOT / man['source']).read_bytes()) != man['source_sha256']:
        raise SystemExit('M01 source hash differs from the manifest')
    rows = {r['instance_id']: r for r in pd.read_parquet(DATA).to_dict('records')}
    m01 = {json.loads(x)['instance_id']: json.loads(x) for x in (ROOT / man['source']).read_text().splitlines()}
    RUN.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    client = docker.from_env()
    info = client.info()
    platform_rec = dict(host_arch=platform.machine(), vm_kernel_arch=info.get('Architecture'), vm_kernel=info.get('KernelVersion'),
                        vm_os=info.get('OperatingSystem'), docker_server=client.version().get('Version'), translation_mode='rosetta (colima vz)',
                        resource_limits=dict(cpus=info.get('NCPU'), mem_bytes=info.get('MemTotal')), declared_timeout_seconds=TIMEOUT,
                        evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9', package=swebench.__version__,
                        adapter_version=A.ADAPTER_VERSION, adapter_source_sha256=A.adapter_source_sha256())
    todo = [t['instance_id'] for t in man['tasks'] if t['instance_id'] != 'pallets__flask-5014']
    status = dict(manifest=str(MANIFEST.relative_to(ROOT)), selected=len(man['tasks']), reused=['pallets__flask-5014'], planned_new=todo,
                  completed=[], stopped=None)

    def qualify_fn(iid, attempt_dir, stock_run_id):
        inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in rows[iid].items()}
        return qualify(client, inst, m01[iid], platform_rec, attempt_dir, stock_run_id)

    legacy = json.loads(LEGACY_MANIFEST.read_text()) if LEGACY_MANIFEST.exists() else None
    status = run_queue(todo, OUT, qualify_fn, status, pause=PAUSE, free_fn=vm_free_gb, expected=expected_identity(), legacy=legacy)
    status['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    (OUT / 'status.json').write_text(json.dumps(status, indent=1, default=str) + '\n')

if __name__ == '__main__':
    main()
