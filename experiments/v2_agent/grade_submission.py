"""DTR-REQ-002: grade one agent smoke-episode submission with the pinned f7bbbb2 harness (stock path) plus the M03 strict
rule. Runs in work/venvs/swebench_f7bbbb2 against the approved runtime. An empty submission is NOT evaluated (the
harness drops empty predictions) and is recorded as operational zero; nothing else is substituted.
  python experiments/v2_agent/grade_submission.py <episode_dir>
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import qualify_instances as Q  # noqa: E402
from grading_conformance import declared_outcome  # noqa: E402

DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'


def main():
    ep = Path(sys.argv[1]).resolve()
    rec = json.loads((ep / 'episode.json').read_text())
    iid, sub = rec['instance_id'], (ep / 'submission.diff').read_text()
    run_id = 'agent-%s-%s' % (rec['backend'], iid.replace('__', '-'))
    grade = dict(instance_id=iid, backend=rec['backend'], exit_status=rec['exit_status'], submission_sha256=hashlib.sha256(sub.encode()).hexdigest(),
                 evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9', run_id=run_id)
    if not sub.strip():
        grade.update(evaluated=False, reason='empty submission (not Submitted, or no tracked-file changes)', upstream_resolved=False,
                     strict_outcome='unresolved (empty submission)', operational_resolved=0)
    else:
        work = ROOT / 'work/runs/agent_grading'
        work.mkdir(parents=True, exist_ok=True)
        preds = work / (run_id + '.preds.json')
        preds.write_text(json.dumps({iid: dict(model_name_or_path=rec['backend_alias'], instance_id=iid, model_patch=sub)}))
        cmd = [sys.executable, '-m', 'swebench.harness.run_evaluation', '--dataset_name', str(DATA), '--split', 'train',
               '--predictions_path', str(preds), '--instance_ids', iid, '--run_id', run_id, '--namespace', 'none',
               '--max_workers', '1', '--timeout', '1800', '--cache_level', 'instance', '--report_dir', str(work)]
        p = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
        logd = work / 'logs/run_evaluation' / run_id / rec['backend_alias'] / iid
        report_fp, log_fp = logd / 'report.json', logd / 'test_output.txt'
        report = json.loads(report_fp.read_text()) if report_fp.exists() else None
        import pandas as pd
        from swebench.harness.grading import get_logs_eval
        from swebench.harness.test_spec.test_spec import make_test_spec
        row = next(r for r in pd.read_parquet(DATA).to_dict('records') if r['instance_id'] == iid)
        inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
        (f2p, _), (p2p, _) = Q.parse_test_list(inst, 'FAIL_TO_PASS'), Q.parse_test_list(inst, 'PASS_TO_PASS')
        strict, smap = 'unknown_evaluator_failure', {}
        if log_fp.exists():
            smap, found = get_logs_eval(make_test_spec(inst), str(log_fp))
            strict = declared_outcome(f2p, p2p, smap, log_ok=found)
        up = bool(report and report.get(iid, {}).get('resolved'))
        grade.update(evaluated=True, harness_exit=p.returncode, upstream_report=report, upstream_resolved=up, strict_outcome=strict,
                     operational_resolved=int(strict == 'resolved'),
                     required_status={t: smap.get(t) for t in list(f2p) + list(p2p)} if smap else None,
                     patch_applied=bool(report and report.get(iid, {}).get('patch_successfully_applied')))
        if log_fp.exists():
            (ep / 'eval_test_output.txt').write_text(log_fp.read_text())
    (ep / 'grade.json').write_text(json.dumps(grade, indent=1, default=str) + '\n')
    print(json.dumps({k: grade.get(k) for k in ('backend', 'exit_status', 'evaluated', 'patch_applied', 'upstream_resolved', 'strict_outcome')}))


if __name__ == '__main__':
    main()
