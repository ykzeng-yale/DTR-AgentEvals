"""Checks for the consolidated evidence table (lead 64cc65a): every row is source-linked to commit-pinned blobs, no bare
pipe breaks the Markdown table, and the committed artifact equals a regeneration from the immutable commits."""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence_table as E  # noqa: E402

PIN = re.compile(r'\]\(https://github\.com/ykzeng-yale/DTR-AgentEvals/blob/[0-9a-f]{12}/[^)]+\)')


def test_rows_are_source_linked_and_regenerate_identically():
    rows = E.rows()
    assert len(rows) == 11
    for r in rows:
        assert r['links'] and all(PIN.search(l) for l in r['links']), r['study']
        assert not any('|' in str(r[k]) for k in ('study', 'cells', 'reps', 'result', 'adverse', 'validation'))
        assert 'CONFIRM' not in r['study'] and r['validation']
    committed = json.loads(E.OUT_JSON.read_text())
    assert committed['rows'] == json.loads(json.dumps(rows)) and committed['planned_not_run'] == E.PLANNED
