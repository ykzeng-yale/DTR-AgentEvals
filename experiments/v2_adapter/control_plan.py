"""DTR-REQ-002 (lead 180d74e; decision 7f9673a): NON-EXECUTING control-plan template for the pre-sampling no-change / reference-patch
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
ADAPTER = dict(version='control-adapter-v2 (lead 7f9673a; F2P allowlist and completion gate per c85173a)',
               sha256=hashlib.sha256((ROOT / 'experiments/v2_adapter/control_adapter.py').read_bytes()).hexdigest())

PINS = dict(dataset='princeton-nlp/SWE-bench_Verified@c104f84 (local parquet; a Hugging Face name would load UNPINNED data)',
            dataset_parquet_sha256='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd',
            evaluator='SWE-bench/SWE-bench@f7bbbb2ccdf479001d6467c9e34af59e44a840f9 (package 4.1.0, editable install)',
            dependency_lock='results/v2_adapter/m01_c104f840_f7bbbb2/dependency_lock.txt',
            m01_summary='results/v2_adapter/m01_c104f840_f7bbbb2/summary.json')

CONTROLS = dict(   # lead decision 7f9673a: one separately versioned adapter (control_adapter.py) with two modes
    reference=dict(mechanism='control_adapter mode "reference": dataset reference patch through the pinned application step, '
                             'then the identical M01 eval script once; on the approved runtime it must be compared with the '
                             'unmodified pinned stock gold path (--predictions_path gold) on the same task/image, disagreements kept',
                   qualification='completed interpretable execution, every required identity accounted for, and every required '
                                 'FAIL_TO_PASS and PASS_TO_PASS test observed PASSED (M03 strict rule); otherwise diagnose'),
    no_change=dict(mechanism='control_adapter mode "no_change": same digest-pinned image/base commit, bypasses ONLY prediction '
                             'application (patch_application = not_applicable), invokes the identical M01 hash-checked eval script '
                             'once (it applies the test patch itself); no fabricated patch, no empty git-apply, no test edits',
                   qualification='completed interpretable execution with all required identities accounted for, all required '
                                 'PASS_TO_PASS observed PASSED (unless the declared empty-P2P limitation applies), EVERY required '
                                 'FAIL_TO_PASS status in {PASSED, FAILED} with at least one FAILED (anything else retained raw -> '
                                 'diagnose; lead c85173a), a valid completion marker; a false strict score alone '
                                 'does NOT qualify (timeout, missing report/tests, evaluator or setup failure -> diagnose)',
                   resolved_by='lead 7f9673a (supersedes the open issue raised in 0d3f9da: the unmodified CLI drops empty '
                               'predictions, run_evaluation.py L458-L470)'))

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
    diagnosis=PH('REQUIRED_IF_NOT_MET'), author_execution_permission_ref=PH('LINK_TO_AUTHOR_APPROVAL'),
    control_mode=None, adapter_version=ADAPTER['version'], adapter_source_sha256=PH('SHA256_OF_ADAPTER_USED'),
    prediction_identity=None, patch_application=PH('not_applicable|applied|failed'), repo_state_pre=PH('HASH'),
    repo_state_post=PH('HASH'), attempts=PH('[attempt records; at most one retry on timeout/missing report]'),
    report_scope=PH('explicit scope statement; no fabricated upstream success markers'), qualification_reason=PH('TEXT'),
    stock_gold_path_comparison=PH('reference only: agreement/disagreement with the unmodified --predictions_path gold run'))

COMMAND_TEMPLATES = dict(  # UNTESTED; flags read from run_evaluation.py L583-L674 at f7bbbb2; run only on a verified x86_64 host
    reference='python -m swebench.harness.run_evaluation --dataset_name <PATH_TO_SHA_VERIFIED_PARQUET> --split train '
              '--predictions_path gold --instance_ids <INSTANCE_ID ...> --run_id <RUN_ID> --namespace none --max_workers <N> '
              '--timeout 1800 --cache_level env --report_dir <REPORT_DIR>',
    no_change='control_adapter.run_control(mode="no_change", ...) with an approved Runtime binding (NOT YET WRITTEN; '
              'written only on the approved x86_64 host); the unmodified CLI cannot run it (drops empty predictions)',
    reference_adapter='control_adapter.run_control(mode="reference", reference_patch=<dataset patch>, ...) - compared with '
                      'the stock CLI gold command above on the same task/image',
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
                       control_mode=control, prediction_identity='dataset_reference_patch' if control == 'reference' else 'no_prediction',
                       expected_strict_outcome=('qualified: every required F2P/P2P PASSED' if control == 'reference' else
                                                'qualified: completed with a valid completion marker, identities accounted, P2P PASSED%s, '
                                                'every F2P in {PASSED, FAILED} with >=1 FAILED (a false strict score alone is insufficient)' %
                                                (' (empty-P2P limitation declared)' if r['limitations'] else '')),
                       arch_expected=r['arch'], limitations=r['limitations'])
            out.append(rec)
    return rows, eligible, out


def main():
    rows, eligible, recs = plan()
    art = dict(request='DTR-REQ-002 non-executing control-plan template (lead 180d74e)',
               status='TEMPLATE ONLY: nothing executed; commands untested; host/runtime/digests are placeholders',
               blockers=['(a) author execution permission for the harness controls (unanswered since 2026-09-21 15:16 UTC)',
                         '(b) an x86_64 host with a container runtime (this host: arm64, no docker/podman/colima)'],
               resolved_lead_decision='7f9673a: separately versioned control adapter (control_adapter.py); no-change bypasses only '
                                      'prediction application; qualification requires completed interpretable execution',
               planned_adapter=dict(path='experiments/v2_adapter/control_adapter.py', version=ADAPTER['version'],
                                    source_sha256=ADAPTER['sha256'], note='refreshed for lead c85173a; the runtime run records the hash actually used'),
               pins=PINS, m01_instances_sha256=hashlib.sha256((M01 / 'instances.jsonl').read_bytes()).hexdigest(),
               counts=dict(m01_rows=len(rows), eligible=len(eligible), planned_records=len(recs),
                           empty_pass_to_pass_limitation=sum(1 for r in eligible if r['limitations'])),
               controls=CONTROLS, command_templates=COMMAND_TEMPLATES, record_schema=sorted(RECORD), records=recs)
    OUT.write_text(json.dumps(art, indent=1) + '\n')
    print(json.dumps(art['counts']))


if __name__ == '__main__':
    main()
