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
    docker = str(Path.home() / '.local/dtr-runtime/bin/docker')
    image_id = sp.run([docker, 'image', 'inspect', '--format', '{{.Id}}', 'sweb.eval.x86_64.%s:latest' % iid],
                      capture_output=True, text=True).stdout.strip()
    work = ROOT / 'work/runs/agent_grading'
    work.mkdir(parents=True, exist_ok=True)

    def run_harness(run_id, preds):
        cmd = [sys.executable, '-m', 'swebench.harness.run_evaluation', '--dataset_name', str(DATA), '--split', 'train',
               '--predictions_path', str(preds), '--instance_ids', iid, '--run_id', run_id, '--namespace', 'none',
               '--max_workers', '1', '--timeout', '1800', '--cache_level', 'instance', '--report_dir', str(work)]
        p = sp.run(cmd, cwd=work, capture_output=True, text=True)
        return dict(returncode=p.returncode, stderr_tail=p.stderr[-2000:])

    def strict_fn(logd):
        import pandas as pd
        from swebench.harness.grading import get_logs_eval
        from swebench.harness.test_spec.test_spec import make_test_spec
        row = next(r for r in pd.read_parquet(DATA).to_dict('records') if r['instance_id'] == iid)
        inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
        (f2p, _), (p2p, _) = Q.parse_test_list(inst, 'FAIL_TO_PASS'), Q.parse_test_list(inst, 'PASS_TO_PASS')
        log_fp = Path(logd) / 'test_output.txt'
        if not log_fp.exists():
            return 'unknown_evaluator_failure', None
        smap, found = get_logs_eval(make_test_spec(inst), str(log_fp))
        return declared_outcome(f2p, p2p, smap, log_ok=found), {t: smap.get(t) for t in list(f2p) + list(p2p)}

    grade = GI.grade_flow(rec, sub, image_id, work, ep / 'grade.json', run_harness, strict_fn, rec.get('backend_alias', 'model'))
    print(json.dumps({k: grade.get(k) for k in ('backend', 'exit_status', 'classification', 'grade_valid', 'operational_resolved')}))

if __name__ == '__main__':
    main()
