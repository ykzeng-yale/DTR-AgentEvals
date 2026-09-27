"""Retrospective admission diagnosis; never modifies frozen control receipts."""
import json
from pathlib import Path
from matplotlib_eval_inputs import replay,sha

def reconcile(baseline_raw,reference_raw,baseline,reference):
    # Receipt provenance must already be independently established by audit_files.
    keys=('run_id','task','source_commit','source_hashes','release_sha256','inputs_sha256','manifest_sha256','reference_patch_sha256','sandbox')
    if any(baseline[k]!=reference[k] for k in keys):raise ValueError('control identity conflict')
    out=[]
    for raw,r,mode in [(baseline_raw,baseline,'baseline'),(reference_raw,reference,'reference')]:
        if r['mode']!=mode or sha(raw)!=r['raw_output_sha256']:raise ValueError('raw/arm binding')
        if not r['raw_output_complete'] or not r['cleanup']['owned_absent']:raise ValueError('incomplete control')
        v=replay(raw,r['returncode'],mode,cleanup_confirmed=True,provenance_verified=True,infrastructure_error=r['infrastructure_error'])
        if not v['markers_valid'] or v['bad_markers'] or r['returncode'] not in (0,1) or r['infrastructure_error'] is not None:raise ValueError('infrastructure unknown')
        out.append(v)
    b,f=out
    if not b['control_accepted']:raise ValueError('negative control did not reproduce declared bug')
    if not f['declared_statuses'] or any(v!='PASSED' for v in f['declared_statuses'].values()):raise ValueError('reference declared endpoint not resolved')
    if b['extra_statuses']!=f['extra_statuses']:raise ValueError('extra status changes require separate diagnosis')
    return dict(retrospective=True,original_gate_preserved=[b['control_accepted'],f['control_accepted']],
        declared_endpoint_discrimination=True,extra_status_maps_equal=True,whole_file_clean=reference['returncode']==0,
        model_competence=False,execution_authorized=False,
        limitation='Operational control eligibility for future development only; no stock-harness equivalence or new prospective control success.')

def audit_files(root):
    import subprocess
    from matplotlib_eval_contract import bind_prepared,inventory
    raw=[];reports=[]
    for mode in ('baseline','reference'):
        p=Path(root)/mode;r=json.loads((p/'terminal.json').read_bytes());facts=json.loads((p/'prepared.json').read_bytes())
        diff=bind_prepared(facts,mode)
        if diff!=(p/'source.prepared.diff').read_bytes() or sha(diff)!=r['applied_patch_sha256']:raise ValueError('prepared patch binding')
        if r['source_hashes']!=inventory():raise ValueError('source inventory changed')
        for name,pin in r['source_hashes'].items():
            if sha(subprocess.check_output(['git','show',r['source_commit']+':'+name]))!=pin:raise ValueError('source commit binding')
        raw.append((p/'test.output').read_bytes());reports.append(r)
    return reconcile(*raw,*reports)
