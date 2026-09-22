"""DTR-REQ-002 runtime smoke check (lead bae161f) on pallets__flask-5014: stock gold vs adapter reference vs adapter
no_change, on the same image digests, runtime, resources and declared 1,800 s timeout. Authorized by the author on
2026-09-22. Runs in work/venvs/swebench_f7bbbb2 after the stock run
  python -m swebench.harness.run_evaluation ... --predictions_path gold --instance_ids pallets__flask-5014
         --run_id smoke-stock-gold-2 --namespace none --max_workers 1 --timeout 1800 --cache_level instance
has built the images (run from work/runs/smoke_flask_20260922). Explicit smoke check: a pass qualifies this task and
environment only; failures are retained as runtime diagnoses.
"""
from __future__ import annotations
import hashlib, json, platform, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import control_adapter as A  # noqa: E402
import docker_runtime as DR  # noqa: E402
import qualify_instances as Q  # noqa: E402
from grading_conformance import declared_outcome  # noqa: E402

IID = 'pallets__flask-5014'
DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
DATA_SHA = 'a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
RUN = ROOT / 'work/runs/smoke_flask_20260922'
STOCK_RUN_ID = 'smoke-stock-gold-2'   # rerun with --cache_level instance: the first run (smoke-stock-gold, cache_level env)
STOCK = RUN / 'logs/run_evaluation' / STOCK_RUN_ID / 'gold' / IID   # removed its instance image, so its digest could not be reused
OUT = ROOT / 'results/v2_adapter/smoke_flask_20260922'
TIMEOUT = 1800


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return 'unavailable: %s' % e


def main():
    import docker
    import pandas as pd
    import swebench
    from swebench.harness.grading import get_logs_eval
    from swebench.harness.test_spec.test_spec import make_test_spec

    if sha(DATA.read_bytes()) != DATA_SHA:
        raise SystemExit('dataset checksum mismatch')
    row = next(r for r in pd.read_parquet(DATA).to_dict('records') if r['instance_id'] == IID)
    inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
    q = Q.qualify(inst)
    ts = make_test_spec(inst)
    m01 = next(json.loads(x) for x in (ROOT / 'results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl').read_text().splitlines()
               if json.loads(x)['instance_id'] == IID)
    client = docker.from_env()
    imgs = {k: client.images.get(getattr(ts, k + '_image_key')) for k in ('base', 'env', 'instance')}
    digests = {k: v.id for k, v in imgs.items()}
    platform_rec = dict(host_arch=platform.machine(), host_os=platform.platform(), vm_kernel_arch=client.info().get('Architecture'),
                        vm_kernel=client.info().get('KernelVersion'), vm_os=client.info().get('OperatingSystem'),
                        docker_server=client.version().get('Version'),
                        image_userland_arch={k: v.attrs.get('Architecture') for k, v in imgs.items()},
                        translation_mode='rosetta (colima --vm-type vz --vz-rosetta)',
                        rosetta_pkg=sh('pkgutil --pkg-info com.apple.pkg.RosettaUpdateAuto | grep version'),
                        colima=sh('PATH=$HOME/.local/dtr-runtime/bin:$PATH colima list --profile dtr 2>/dev/null | tail -1'),
                        resource_limits=dict(cpus=client.info().get('NCPU'), mem_bytes=client.info().get('MemTotal')),
                        declared_timeout_seconds=TIMEOUT)
    # --- stock gold path (unmodified harness) ---
    stock_log = (STOCK / 'test_output.txt').read_text()
    stock_report = json.loads((STOCK / 'report.json').read_text())
    stock_eval_sh = (STOCK / 'eval.sh').read_text()
    stock_map, stock_found = get_logs_eval(ts, str(STOCK / 'test_output.txt'))
    (f2p, e1), (p2p, e2) = Q.parse_test_list(inst, 'FAIL_TO_PASS'), Q.parse_test_list(inst, 'PASS_TO_PASS')   # M02 parser
    if f2p is None or p2p is None:
        raise SystemExit('test lists not parseable: %s %s' % (e1, e2))
    stock_strict = declared_outcome(f2p, p2p, stock_map, log_ok=stock_found)
    # --- adapter reference and no_change on the same digests ---
    rec_inst = dict(instance_id=IID, eval_script_sha256=m01['eval_script_sha256'], FAIL_TO_PASS=f2p, PASS_TO_PASS=p2p,
                    empty_p2p_declared=bool(q['limitations']))
    parse = DR.parser_binding(ts)
    out = {}
    for mode in ('reference', 'no_change'):
        rt = DR.DockerRuntime(client, ts, 'dtr-smoke-%s' % mode.replace('_', ''))
        rec = A.run_control(mode, rec_inst, rt, ts.eval_script, parse, digests,
                            reference_patch=inst['patch'] if mode == 'reference' else None, timeout=TIMEOUT)
        rec['runtime_events'] = rt.events
        out[mode] = (rec, rt.logs)
    ref, nch = out['reference'][0], out['no_change'][0]
    ref_map = ref['attempts'][-1].get('per_test_status') or {}
    req = list(f2p) + list(p2p)
    map_diff = {t: (stock_map.get(t), ref_map.get(t)) for t in req if stock_map.get(t) != ref_map.get(t)}
    acceptance = dict(
        pins_and_script_hashes_agree=(sha(ts.eval_script) == m01['eval_script_sha256'] == sha(stock_eval_sh) == ref['eval_script_sha256'] == nch['eval_script_sha256']),
        stock_reference_required_test_maps_agree=not map_diff,
        stock_reference_strict_outcomes_agree=(stock_strict == 'resolved') == bool(ref['strict_verified_resolved']),
        reference_passes_required_tests=ref['qualification'] == 'qualified',
        no_change_meets_rule=nch['qualification'] == 'qualified')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'logs').mkdir(exist_ok=True)
    (OUT / 'logs/stock_gold_test_output.txt').write_text(stock_log)
    for mode, (rec, logs) in out.items():
        for i, lg in enumerate(logs, 1):
            (OUT / 'logs' / ('adapter_%s_attempt%d_test_output.txt' % (mode, i))).write_text(lg['text'])
            rec['attempts'][i - 1]['eval_runtime_seconds'] = lg['runtime_seconds']
    summ = dict(request='DTR-REQ-002 runtime smoke check (lead bae161f): stock gold vs adapter reference vs adapter no_change',
                authorization='author 2026-09-22 ("yes"; "do all directly for all you need")', instance_id=IID,
                scope='explicit smoke check: qualifies this task/environment only; not a representative sample; no model inference',
                pins=dict(dataset_sha256=DATA_SHA, evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9', package=swebench.__version__,
                          eval_script_sha256=sha(ts.eval_script), m01_eval_script_sha256=m01['eval_script_sha256'],
                          stock_eval_sh_sha256=sha(stock_eval_sh), adapter_version=A.ADAPTER_VERSION, adapter_source_sha256=A.adapter_source_sha256()),
                platform=platform_rec, image_digests=digests, image_keys={k: getattr(ts, k + '_image_key') for k in ('base', 'env', 'instance')},
                required_tests=dict(fail_to_pass=len(f2p), pass_to_pass=len(p2p)),
                stock=dict(report=stock_report, get_logs_eval_found=stock_found, strict_outcome=stock_strict,
                           required_status={t: stock_map.get(t) for t in req}, log_sha256=sha(stock_log)),
                adapter_reference=ref, adapter_no_change=nch, stock_vs_reference_required_status_differences=map_diff,
                acceptance=acceptance, smoke_check_passed=all(acceptance.values()))
    (OUT / 'summary.json').write_text(json.dumps(summ, indent=1, default=str) + '\n')
    print(json.dumps(dict(acceptance=acceptance, passed=summ['smoke_check_passed'], stock_strict=stock_strict,
                          stock_resolved=stock_report.get(IID, {}).get('resolved'), reference=ref['qualification'], ref_reason=ref['reason'],
                          no_change=nch['qualification'], nc_reason=nch['reason'], image_arch=platform_rec['image_userland_arch'],
                          vm_arch=platform_rec['vm_kernel_arch']), indent=1))


if __name__ == '__main__':
    main()
