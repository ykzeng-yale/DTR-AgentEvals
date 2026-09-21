"""Checks for the non-executing control-plan template (lead 180d74e): pure data (no execution imports), faithful to the
committed M01 records, explicit placeholders instead of guessed host/image values, and the no-change open issue."""
import ast, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import control_plan as P  # noqa: E402


def test_module_imports_nothing_that_executes():
    tree = ast.parse(Path(P.__file__).read_text())
    mods = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not mods & {'subprocess', 'docker', 'swebench', 'os', 'shutil', 'requests'}, mods


def test_plan_matches_m01_and_keeps_placeholders():
    rows, eligible, recs = P.plan()
    art = json.loads(P.OUT.read_text())
    assert len(eligible) == 500 and len(recs) == 1000 and art['records'] == json.loads(json.dumps(recs))
    m01 = {r['instance_id']: r for r in rows}
    for r in recs:
        src = m01[r['instance_id']]
        assert r['eval_script_sha256_expected'] == src['eval_script_sha256'] and r['arch_expected'] == 'x86_64'
        assert r['instance_image_key'] == src['instance_image_key']
        for k in ('instance_image_digest', 'env_image_digest', 'base_image_digest', 'host_id', 'container_runtime', 'author_execution_permission_ref'):
            assert r[k].startswith('<') and r[k].endswith('>'), k        # never a guessed value
        assert r['expected_strict_outcome'].endswith('True' if r['control'] == 'reference' else 'False')
    assert art['counts']['empty_pass_to_pass_limitation'] == 11
    assert 'LEAD DECISION' in art['controls']['no_change']['open_issue'] and 'NOT AVAILABLE' in art['command_templates']['no_change']
    assert art['status'].startswith('TEMPLATE ONLY')
