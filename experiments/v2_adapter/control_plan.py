"""DTR-REQ-002 (lead 180d74e): NON-EXECUTING control-plan template for the pre-sampling no-change / reference-patch
controls (experiment_protocol_v2.md infrastructure gate; M03 decision). Pure data: it reads the committed M01 records and
writes a plan with explicit placeholders. It imports no container, subprocess or SWE-bench code and runs nothing.
Commands in the runbook are UNTESTED templates; host, runtime and image digests are placeholders, never guessed.
  python control_plan.py   -> results/v2_adapter/control_plan_template_20260921.json
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M01 = ROOT / 'results/v2_adapter/m01_c104f840_f7bbbb2'
OUT = ROOT / 'results/v2_adapter/control_plan_template_20260921.json'
PH = lambda name: '<%s>' % name                           # explicit placeholder, filled only on a verified host

PINS = dict(dataset='princeton-nlp/SWE-bench_Verified@c104f84 (local parquet; a Hugging Face name would load UNPINNED data)',
            dataset_parquet_sha256='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd',
            evaluator='SWE-bench/SWE-bench@f7bbbb2ccdf479001d6467c9e34af59e44a840f9 (package 4.1.0, editable install)',
            dependency_lock='results/v2_adapter/m01_c104f840_f7bbbb2/dependency_lock.txt',
            m01_summary='results/v2_adapter/m01_c104f840_f7bbbb2/summary.json')

CONTROLS = dict(
    reference=dict(patch='dataset `patch` field (gold), via --predictions_path gold',
                   expected='STRICT verified pass: nonempty FAIL_TO_PASS and every FAIL_TO_PASS and PASS_TO_PASS test observed PASSED '
                            '(SKIPPED/XFAIL/missing do not pass); upstream report preserved beside the strict score'),
    no_change=dict(patch='NONE (base_commit + test_patch only)',
                   expected='STRICT verified FAIL: at least one FAIL_TO_PASS test not observed PASSED',
                   open_issue='the unmodified CLI cannot run this control: run_evaluation drops empty predictions before any '
                              'container starts (run_evaluation.py L458-L470, read from source). Calling run_instance directly would '
                              'write an empty patch.diff and try GIT_APPLY_CMDS (L64-L67, L158-L184); whether git apply / patch accept '
                              'an empty file was NOT tested here (inferred to fail -> EvaluationError). A mechanism (e.g. running the '
                              'generated eval script in the instance image without applying a prediction, graded by the pinned parser) '
                              'needs a LEAD DECISION before execution.'))

RECORD = dict(  # expected acceptance record per instance x control (every field required; placeholders until executed)
    run_id=PH('RUN_ID'), instance_id=None, control=None, host_id=PH('HOST_ID'), host_arch_uname_m=PH('MUST_EQUAL_x86_64'),
    container_runtime=PH('RUNTIME_NAME_AND_VERSION'), evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9',
    dataset_parquet_sha256=PINS['dataset_parquet_sha256'], dependency_lock_sha256=PH('SHA256_OF_LOCK_ON_HOST'),
    eval_script_sha256_expected=None, eval_script_sha256_observed=PH('FROM_TEST_SPEC_ON_HOST'),
    base_image_key=None, env_image_key=None, instance_image_key=None,
    base_image_digest=PH('RESOLVED_ON_HOST'), env_image_digest=PH('RESOLVED_ON_HOST'), instance_image_digest=PH('RESOLVED_ON_HOST'),
    patch_sha256=PH('SHA256_OF_APPLIED_PATCH_OR_EMPTY'), started_utc=PH('ISO8601'), finished_utc=PH('ISO8601'),
    exit_status=PH('HARNESS_EXIT'), evaluation_status=PH('completed|unknown_evaluator_failure (timeout/no report; one retry, identical patch hash)'),
    report_json_sha256=PH('SHA256'), test_log_sha256=PH('SHA256'), per_test_status=PH('{test_id: PASSED|FAILED|SKIPPED|XFAIL|ERROR|MISSING}'),
    upstream_resolved=PH('BOOL_FROM_UPSTREAM_REPORT'), strict_verified_resolved=PH('BOOL_FROM_M03_STRICT_RULE'),
    expected_strict_outcome=None, meets_expectation=PH('BOOL'), qualification=PH('qualified|diagnose (never silent exclusion)'),
    diagnosis=PH('REQUIRED_IF_NOT_MET'), author_execution_permission_ref=PH('LINK_TO_AUTHOR_APPROVAL'))

COMMAND_TEMPLATES = dict(  # UNTESTED; flags read from run_evaluation.py L583-L674 at f7bbbb2; run only on a verified x86_64 host
    reference='python -m swebench.harness.run_evaluation --dataset_name <PATH_TO_SHA_VERIFIED_PARQUET> --split train '
              '--predictions_path gold --instance_ids <INSTANCE_ID ...> --run_id <RUN_ID> --namespace none --max_workers <N> '
              '--timeout 1800 --cache_level env --report_dir <REPORT_DIR>',
    no_change='NOT AVAILABLE through the unmodified CLI (see controls.no_change.open_issue); awaiting lead decision',
    notes=['a local .parquet is loaded with split="train" by load_swebench_dataset (utils.py L147-L148); --split is then unused',
           '--namespace none builds images locally; the default namespace pulls mutable "latest" tags - record every digest',
           'no project credentials on the host; disposable isolated workers; network only for image builds'])


def plan():
    rows = [json.loads(x) for x in (M01 / 'instances.jsonl').read_text().splitlines()]
    eligible = [r for r in rows if r['qualification'] == 'eligible' and r.get('construction') == 'ok']
    out = []
    for r in eligible:
        for control in ('no_change', 'reference'):
            rec = dict(RECORD, instance_id=r['instance_id'], control=control, eval_script_sha256_expected=r['eval_script_sha256'],
                       base_image_key=r['base_image_key'], env_image_key=r['env_image_key'], instance_image_key=r['instance_image_key'],
                       expected_strict_outcome='strict_verified_resolved == True' if control == 'reference' else 'strict_verified_resolved == False',
                       arch_expected=r['arch'], limitations=r['limitations'])
            out.append(rec)
    return rows, eligible, out


def main():
    rows, eligible, recs = plan()
    art = dict(request='DTR-REQ-002 non-executing control-plan template (lead 180d74e)',
               status='TEMPLATE ONLY: nothing executed; commands untested; host/runtime/digests are placeholders',
               blockers=['(a) author execution permission for the harness controls (unanswered since 2026-09-21 15:16 UTC)',
                         '(b) an x86_64 host with a container runtime (this host: arm64, no docker/podman/colima)'],
               open_lead_decision='mechanism for the no-change control (the unmodified harness cannot evaluate an empty patch)',
               pins=PINS, m01_instances_sha256=hashlib.sha256((M01 / 'instances.jsonl').read_bytes()).hexdigest(),
               counts=dict(m01_rows=len(rows), eligible=len(eligible), planned_records=len(recs),
                           empty_pass_to_pass_limitation=sum(1 for r in eligible if r['limitations'])),
               controls=CONTROLS, command_templates=COMMAND_TEMPLATES, record_schema=sorted(RECORD), records=recs)
    OUT.write_text(json.dumps(art, indent=1) + '\n')
    print(json.dumps(art['counts']))


if __name__ == '__main__':
    main()
