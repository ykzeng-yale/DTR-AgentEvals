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


def qualify(client, inst, m01, platform_rec):
    from swebench.harness.grading import get_logs_eval
    from swebench.harness.test_spec.test_spec import make_test_spec
    iid = inst['instance_id']
    rec = dict(instance_id=iid, repo=inst['repo'], version=inst['version'], started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    q = Q.qualify(inst)
    (f2p, e1), (p2p, e2) = Q.parse_test_list(inst, 'FAIL_TO_PASS'), Q.parse_test_list(inst, 'PASS_TO_PASS')
    rec['limitations'] = q['limitations']
    ts = make_test_spec(inst)
    # 1. stock gold (unmodified harness)
    t0 = time.time()
    p = subprocess.run([sys.executable, '-m', 'swebench.harness.run_evaluation', '--dataset_name', str(DATA), '--split', 'train',
                        '--predictions_path', 'gold', '--instance_ids', iid, '--run_id', STOCK_RUN_ID, '--namespace', 'none',
                        '--max_workers', '1', '--timeout', str(TIMEOUT), '--cache_level', 'instance', '--report_dir', 'reports'],
                       cwd=RUN, capture_output=True, text=True)
    rec['stock_wall_seconds'] = time.time() - t0
    rec['stock_exit'] = p.returncode
    sdir = RUN / 'logs/run_evaluation' / STOCK_RUN_ID / 'gold' / iid
    (OUT / iid).mkdir(parents=True, exist_ok=False)
    (OUT / iid / 'stock_stdout_tail.txt').write_text(p.stdout[-4000:] + '\n--- stderr ---\n' + p.stderr[-4000:])
    if not (sdir / 'report.json').exists() or not (sdir / 'test_output.txt').exists():
        rec.update(stage_failed='stock_gold', diagnosis='no stock report/test output (image build or evaluation failure; see run_instance/build logs)',
                   run_instance_log_tail=(sdir / 'run_instance.log').read_text()[-3000:] if (sdir / 'run_instance.log').exists() else None)
        return rec
    stock_log = (sdir / 'test_output.txt').read_text()
    stock_report = json.loads((sdir / 'report.json').read_text())
    stock_eval_sh = (sdir / 'eval.sh').read_text()
    stock_map, stock_found = get_logs_eval(ts, str(sdir / 'test_output.txt'))
    stock_strict = declared_outcome(f2p, p2p, stock_map, log_ok=stock_found)
    (OUT / iid / 'stock_gold_test_output.txt').write_text(stock_log)
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
            (OUT / iid / ('adapter_%s_attempt%d_test_output.txt' % (mode, i))).write_text(lg['text'])
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
    todo = [t for t in man['tasks'] if t['instance_id'] != 'pallets__flask-5014']
    status = dict(manifest=str(MANIFEST.relative_to(ROOT)), selected=len(man['tasks']), reused=['pallets__flask-5014'], planned_new=[t['instance_id'] for t in todo],
                  completed=[], stopped=None)
    for t in todo:
        iid = t['instance_id']
        if PAUSE.exists():
            status['stopped'] = 'paused by %s before %s (shared-host coordination)' % (PAUSE, iid); break
        free = vm_free_gb()
        if free is not None and free < MIN_FREE_GB:
            status['stopped'] = 'VM disk guard: %.1f GB free < %d GB before %s' % (free, MIN_FREE_GB, iid); break
        inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in rows[iid].items()}
        try:
            rec = qualify(client, inst, m01[iid], platform_rec)
        except Exception as e:  # noqa: BLE001  retained as a diagnosis
            rec = dict(instance_id=iid, stage_failed='exception', error='%s: %s' % (type(e).__name__, str(e)[:500]), traceback=traceback.format_exc()[-3000:])
        rec['vm_free_gb_before'] = free
        rec['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (OUT / iid).mkdir(parents=True, exist_ok=True)
        with open(OUT / iid / 'summary.json', 'x') as fh:
            fh.write(json.dumps(rec, indent=1, default=str) + '\n')
        status['completed'].append(dict(instance_id=iid, qualified=rec.get('qualified', False), stage_failed=rec.get('stage_failed'),
                                        acceptance=rec.get('acceptance')))
        (OUT / 'status.json').write_text(json.dumps(status, indent=1, default=str) + '\n')
        print(iid, 'qualified=%s' % rec.get('qualified'), rec.get('stage_failed') or '', flush=True)
    status['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    (OUT / 'status.json').write_text(json.dumps(status, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
