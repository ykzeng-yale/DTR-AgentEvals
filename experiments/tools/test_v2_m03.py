"""M03 fixtures: declared grading rule with upstream discrepancies, and the new-file-only reset regression (no execution)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import eval_script_check as E  # noqa: E402
import grading_conformance as C  # noqa: E402

BASE = 'abc123'
NEW_ONLY = 'diff --git a/tests/test_new.py b/tests/test_new.py\nnew file mode 100644\n--- /dev/null\n+++ b/tests/test_new.py\n@@ -0,0 +1 @@\n+def test_x(): pass\n'
MIXED = NEW_ONLY + 'diff --git a/tests/test_old.py b/tests/test_old.py\n--- a/tests/test_old.py\n+++ b/tests/test_old.py\n@@ -1 +1 @@\n-x\n+y\n'


def script(resets):
    return ['source /opt/miniconda3/bin/activate', 'cd /testbed', *resets, "git apply -v - <<'EOF_1'",
            ": 'START_TEST_OUTPUT'", 'pytest tests', ": 'END_TEST_OUTPUT'", *resets]


@pytest.mark.parametrize('fid,sm,ok,declared,upstream', C.FIXTURES)
def test_declared_rule_matches_fixture_table(fid, sm, ok, declared, upstream):
    assert C.declared_outcome(C.F2P, C.P2P, sm, ok) == declared


def test_absence_never_counts_as_pass_under_the_declared_rule():
    for fid, sm, ok, declared, _ in C.FIXTURES:
        if any(sm.get(t) != C.PASSED for t in C.F2P + C.P2P) or not ok or not sm:
            assert declared != 'resolved', fid


def test_discrepancies_are_exactly_the_skipped_and_xfail_cases():
    d = {x['id']: x['severity'] for x in C.discrepancies()}
    assert {k for k, v in d.items() if v == 'COUNTS AS PASS UPSTREAM'} == {
        'G05-one-f2p-skipped', 'G06-all-f2p-skipped', 'G07-p2p-skipped', 'G08-f2p-xfail'}
    assert {k for k, v in d.items() if v == 'label only'} == {'G10-bad-log-marker', 'G11-empty-parsed-map'}


def test_patch_file_parsing():
    assert E.patch_files(NEW_ONLY) == ([], ['tests/test_new.py'])
    assert E.patch_files(MIXED) == (['tests/test_old.py'], ['tests/test_new.py'])


def test_pre_fix_new_file_only_script_fails_R1():
    # pre-#518 construction: `git checkout {base} {' '.join([])}` -> a bare checkout
    problems = E.check_reset_commands(script(['git checkout %s ' % BASE]), NEW_ONLY, BASE)
    assert any(p.startswith('R1') for p in problems) and any(p.startswith('R3') for p in problems)


def test_post_fix_new_file_only_script_passes():
    assert E.check_reset_commands(script(['rm -f tests/test_new.py']), NEW_ONLY, BASE) == []


def test_post_fix_mixed_script_passes_and_preserves_unrelated_paths():
    good = script(['git checkout %s tests/test_old.py' % BASE, 'rm -f tests/test_new.py'])
    assert E.check_reset_commands(good, MIXED, BASE) == []
    touches_setup = script(['git checkout %s tests/test_old.py tox.ini' % BASE, 'rm -f tests/test_new.py'])
    assert any(p.startswith('R2') for p in E.check_reset_commands(touches_setup, MIXED, BASE))


def test_reset_must_bracket_the_test_run():
    only_before = ['cd /testbed', 'rm -f tests/test_new.py', "git apply -v - <<'EOF_1'", ": 'END_TEST_OUTPUT'"]
    assert any(p.startswith('R3 after') for p in E.check_reset_commands(only_before, NEW_ONLY, BASE))


# ---- regressions from the lead's adversarial probes (docs/audits/m03_review_bfed7e1.json), read from the audit file
def _lead_cases():
    import json
    a = json.loads((Path(__file__).resolve().parents[2] / 'docs' / 'audits' / 'm03_review_bfed7e1.json').read_text())
    return a, {c['name']: c['commands'] for c in a['cases']}


def test_lead_probe_incomplete_resets_per_phase_is_rejected():
    a, cases = _lead_cases()
    probs = E.check_reset_commands(cases['incomplete_resets_per_phase'], a['test_patch'], a['base_commit'])
    assert any(p.startswith('R3 before') for p in probs) and any(p.startswith('R2 after') for p in probs)


def test_lead_probe_reversed_markers_is_rejected():
    a, cases = _lead_cases()
    assert any(p.startswith('R4') for p in E.check_reset_commands(cases['reversed_markers'], a['test_patch'], a['base_commit']))


def test_lead_positive_control_passes():
    a, cases = _lead_cases()
    assert E.check_reset_commands(cases['complete_per_phase'], a['test_patch'], a['base_commit']) == []


@pytest.mark.parametrize('cmd', ['git reset --hard abc123', 'git clean -fd', 'git stash', 'rm tests/test_new.py',
                                 'git checkout main tests/test_old.py', 'git restore tests/test_old.py'])
def test_unsupported_reset_syntax_fails_closed(cmd):
    bad = script(['git checkout %s tests/test_old.py' % BASE, 'rm -f tests/test_new.py', cmd])
    assert any(p.startswith('UNSUPPORTED') for p in E.check_reset_commands(bad, MIXED, BASE))


def test_missing_or_duplicate_markers_fail_closed():
    good = script(['git checkout %s tests/test_old.py' % BASE, 'rm -f tests/test_new.py'])
    no_end = [c for c in good if 'END_TEST_OUTPUT' not in c]
    assert any(p.startswith('R4') for p in E.check_reset_commands(no_end, MIXED, BASE))
    assert any(p.startswith('R4') for p in E.check_reset_commands(good + ["git apply -v x"], MIXED, BASE))
