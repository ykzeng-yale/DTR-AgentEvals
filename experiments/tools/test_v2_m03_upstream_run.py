"""Checks on the committed M03 part-1 execution artifact: every source-derived upstream outcome was confirmed by the
executed pinned grader, and the executed counts-as-pass set equals the pre-registered discrepancy list."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import grading_conformance as GC  # noqa: E402

ART = Path(__file__).resolve().parents[2] / 'results/v2_adapter/m03_upstream_grader_run_20260922/summary.json'


def test_executed_upstream_grader_confirms_source_derived_column():
    s = json.loads(ART.read_text())
    assert s['evaluator']['commit'].startswith('f7bbbb2') and s['fixtures'] == len(GC.FIXTURES) == 11
    assert s['source_derived_upstream_confirmed'] == 11 and all(r['source_derived_confirmed'] for r in s['rows'])
    pre = sorted(d['id'] for d in GC.discrepancies() if d['severity'] == 'COUNTS AS PASS UPSTREAM')
    assert sorted(s['counts_as_pass_upstream_but_not_declared']) == pre == ['G05-one-f2p-skipped', 'G06-all-f2p-skipped',
                                                                             'G07-p2p-skipped', 'G08-f2p-xfail']
    g10 = next(r for r in s['rows'] if r['id'] == 'G10-bad-log-marker')
    assert g10['log_found'] is False and g10['upstream_executed_via_log'] is False
