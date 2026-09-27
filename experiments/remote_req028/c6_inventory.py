"""Read-only pin inventory; does not load tests, datasets, models, or evaluators."""
import json,sys
from pathlib import Path
from c6_protocol import ROOT,HERE,sha,encode,put

def inventory():
    paths=['configs/v2_evaluator_selection_20260921.json',
        'experiments/v2_adapter/grading_conformance.py','experiments/v2_adapter/qualify_instances.py',
        'experiments/v2_agent/grade_submission.py','experiments/v2_agent/grade_identity.py',
        'docs/audits/evaluator_selection_audit_81128ee.json',
        'results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl',
        'docs/req028_c6_development_trajectory_20260927.md',
        'docs/req028_c0_prompt_20260927.json']
    row=next(json.loads(line) for line in (ROOT/paths[6]).read_text().splitlines()
             if json.loads(line)['instance_id']=='astropy__astropy-14598')
    audit=json.loads((ROOT/paths[5]).read_text())
    return dict(scope='candidate pins, not evaluator execution qualification',
        scientific_inputs={path:sha((ROOT/path).read_bytes()) for path in paths},
        strict_rule='all declared F2P and P2P observed PASSED; evaluator failures UNKNOWN',
        upstream_evaluator_commit=audit['candidate'],upstream_source_pins=audit['sources'],
        task_metadata_record=row,task_metadata_record_sha256=sha(encode(row)),
        task_test_manifest_gap='Local metadata pins content hash, 1 F2P/175 P2P and eval-script SHA; full named test-list manifest must be rebound on lead before evaluation approval',
        submission_source_gap='Pinned mini-swe environments/docker.py bytes and exact checker unavailable locally; no guessed sentinel acceptance',
        adapters_gap=['experiments/remote_req028/c6_sandbox_host.py','experiments/remote_req028/c6_submission_checker.py'],
        writable_sandbox_gap='Lead qualification in progress. No unbounded writable overlay assumed. /work/base-Python not qualified; original /testbed and activated testbed environment required by lead.',
        source_hashes={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(HERE.iterdir())
                       if p.is_file() and p.suffix in ('.py','.json')},
        execution_approved=False)

if __name__=='__main__':
    out=Path(sys.argv[1]);put(out.parent,out.name,inventory())
