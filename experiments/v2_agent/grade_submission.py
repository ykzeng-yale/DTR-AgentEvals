"""DTR-REQ-002: grade one agent smoke-episode submission with the pinned f7bbbb2 harness (stock path) plus the M03 strict
rule. Runs in work/venvs/swebench_f7bbbb2 against the approved runtime. An empty submission is NOT evaluated (the
harness drops empty predictions) and is recorded as operational zero; nothing else is substituted.
Identity repair (lead e360831): unique evaluator run ID per episode+patch, eligibility and image checks, no-clobber
preflight and report acceptance only for the identical patch (grade_identity.py).
  python experiments/v2_agent/grade_submission.py <episode_dir>
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import qualify_instances as Q  # noqa: E402
sys.path.insert(0, str(ROOT / "experiments/v2_agent"))
import grade_identity as GI  # noqa: E402
from grading_conformance import declared_outcome  # noqa: E402

DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'


def main():
    import subprocess as sp
    ep = Path(sys.argv[1]).resolve()
    rec = json.loads((ep / 'episode.json').read_text())
    iid, sub = rec['instance_id'], (ep / 'submission.diff').read_text()
    grade_path = ep / 'grade.json'
    base = dict(instance_id=iid, backend=rec['backend'], exit_status=rec['exit_status'], episode_run_id=rec.get('run_id'),
                submission_sha256=GI.sha(sub), evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9')
    docker = str(Path.home() / '.local/dtr-runtime/bin/docker')
    image_id = sp.run([docker, 'image', 'inspect', '--format', '{{.Id}}', 'sweb.eval.x86_64.%s:latest' % iid],
                      capture_output=True, text=True).stdout.strip()
    try:
        GI.eligibility(rec, sub, image_id)
        run_id = GI.evaluator_run_id(rec, sub)
    except GI.GradeRefused as e:
        grade = dict(base, evaluated=False, reason=str(e), upstream_resolved=False, strict_outcome='unresolved (not evaluated)',
                     operational_resolved=0)
        with open(grade_path, 'x') as fh:
            fh.write(json.dumps(grade, indent=1) + '\n')
        print(json.dumps({k: grade[k] for k in ('backend', 'exit_status', 'evaluated', 'reason')}))
        return
    work = ROOT / 'work/runs/agent_grading'
    work.mkdir(parents=True, exist_ok=True)
    preds = work / (run_id + '.preds.json')
    logd = work / 'logs/run_evaluation' / run_id / rec['backend_alias'] / iid
    GI.preflight(preds, work / 'logs/run_evaluation' / run_id, grade_path)
    with open(preds, 'x') as fh:
        fh.write(json.dumps({iid: dict(model_name_or_path=rec['backend_alias'], instance_id=iid, model_patch=sub)}))
    cmd = [sys.executable, '-m', 'swebench.harness.run_evaluation', '--dataset_name', str(DATA), '--split', 'train',
           '--predictions_path', str(preds), '--instance_ids', iid, '--run_id', run_id, '--namespace', 'none',
           '--max_workers', '1', '--timeout', '1800', '--cache_level', 'instance', '--report_dir', str(work)]
    p = sp.run(cmd, cwd=work, capture_output=True, text=True)
    report = GI.accept_report(logd, iid, sub)                    # raises on a stale/mismatched report
    import pandas as pd
    from swebench.harness.grading import get_logs_eval
    from swebench.harness.test_spec.test_spec import make_test_spec
    row = next(r for r in pd.read_parquet(DATA).to_dict('records') if r['instance_id'] == iid)
    inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
    (f2p, _), (p2p, _) = Q.parse_test_list(inst, 'FAIL_TO_PASS'), Q.parse_test_list(inst, 'PASS_TO_PASS')
    strict, smap, log_fp = 'unknown_evaluator_failure', {}, logd / 'test_output.txt'
    if log_fp.exists():
        smap, found = get_logs_eval(make_test_spec(inst), str(log_fp))
        strict = declared_outcome(f2p, p2p, smap, log_ok=found)
    grade = dict(base, evaluated=True, evaluator_run_id=run_id, image_id=image_id, harness_exit=p.returncode, upstream_report=report,
                 upstream_resolved=bool(report and report.get(iid, {}).get('resolved')), strict_outcome=strict,
                 operational_resolved=int(strict == 'resolved'),
                 required_status={t: smap.get(t) for t in list(f2p) + list(p2p)} if smap else None,
                 patch_applied=bool(report and report.get(iid, {}).get('patch_successfully_applied')))
    with open(grade_path, 'x') as fh:
        fh.write(json.dumps(grade, indent=1, default=str) + '\n')
    if log_fp.exists():
        with open(ep / 'eval_test_output.txt', 'x') as fh:
            fh.write(log_fp.read_text())
    print(json.dumps({k: grade.get(k) for k in ('backend', 'exit_status', 'evaluated', 'patch_applied', 'upstream_resolved', 'strict_outcome')}))


if __name__ == '__main__':
    main()
