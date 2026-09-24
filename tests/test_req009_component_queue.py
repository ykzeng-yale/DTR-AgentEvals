"""DTR-REQ-009 component screen and design queue: hand-built fixtures, expectations written out by hand."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('req009', ROOT / 'experiments/v2_adapter/req009_component_queue.py')
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

C1 = 'a' * 40
C2 = 'b' * 40


def prow(iid, repo, tests, paths, commit=C1):
    patch = ''.join('diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1 +1 @@\n-x\n+y\n' % (p, p, p, p) for p in paths)
    return dict(instance_id=iid, repo=repo, base_commit=commit, FAIL_TO_PASS=json.dumps(tests), patch=patch)


def test_edge_rules_by_hand():
    rows = [prow('r__r-1', 'o/r', ['t::a'], ['x.py'], C1),
            prow('r__r-2', 'o/r', ['t::a', 't::b'], ['y.py'], C2),   # shares test t::a with r-1 -> edge
            prow('r__r-3', 'o/r', ['t::c'], ['x.py'], C2),           # shares path x.py with r-1 but other commit -> no
            prow('r__r-4', 'o/r', ['t::d'], ['y.py', 'z.py'], C2),   # same commit + shared y.py with r-2 -> edge
            prow('s__s-1', 'o/s', ['t::a'], ['x.py'], C1)]            # same test and commit as r-1 but other repo -> no
    edges = M.build_edges(M.edge_fields(rows))
    assert [(e['a'], e['b']) for e in edges] == [('r__r-1', 'r__r-2'), ('r__r-2', 'r__r-4')]
    assert edges[0]['shared_fail_to_pass'] == ['t::a'] and 'shared_patch_paths' not in edges[0]
    assert edges[1]['shared_patch_paths'] == ['y.py'] and edges[1]['same_base_commit'] == C2
    # r-3 shares x.py with r-1 but not the base commit, and nothing with r-2/r-4 under the same commit
    assert not any('r__r-3' in (e['a'], e['b']) for e in edges)


def test_same_base_commit_without_shared_path_is_not_an_edge():
    rows = [prow('r__r-1', 'o/r', ['t::a'], ['x.py'], C1), prow('r__r-2', 'o/r', ['t::b'], ['y.py'], C1)]
    assert M.build_edges(M.edge_fields(rows)) == []


@pytest.mark.parametrize('bad, message', [
    (dict(FAIL_TO_PASS='not json'), 'FAIL_TO_PASS missing or not JSON'),
    (dict(FAIL_TO_PASS='[]'), 'nonempty list'),
    (dict(FAIL_TO_PASS='["ok", 3]'), 'nonempty list'),
    (dict(base_commit='abc'), 'base_commit'),
    (dict(base_commit=None), 'base_commit'),
    (dict(patch='--- a/x\n+++ b/x\n'), 'no diff header path'),
    (dict(patch='diff --git a/has space.py b/has space.py\n'), 'unparseable diff header'),
    (dict(patch=None), 'patch missing'),
    (dict(repo=''), 'repo missing'),
])
def test_missing_or_malformed_field_stops_the_queue(bad, message):
    row = dict(prow('r__r-1', 'o/r', ['t::a'], ['x.py']), **bad)
    with pytest.raises(M.QueueStopped, match=message):
        M.edge_fields([row])
    frame = [dict(instance_id='r__r-1', repo='o/r')]
    with pytest.raises(M.QueueStopped):
        M.screen(frame, {'r__r-1': 'not_yet_assessed'}, set(), [row])


def toy():
    """Repo o/a: a-1 exposed; a-2 linked to a-1 via test; a-3 linked to a-2 via test (transitive); a-4, a-5 free.
    Repo o/b: b-1 qualification-only linked to b-2; b-3 empty P2P; b-4, b-5, b-6 free. Repo o/c: c-1 free."""
    frame = [dict(instance_id=i, repo=r) for i, r in (
        ('a__a-1', 'o/a'), ('a__a-2', 'o/a'), ('a__a-3', 'o/a'), ('a__a-4', 'o/a'), ('a__a-5', 'o/a'),
        ('b__b-1', 'o/b'), ('b__b-2', 'o/b'), ('b__b-3', 'o/b'), ('b__b-4', 'o/b'), ('b__b-5', 'o/b'),
        ('b__b-6', 'o/b'), ('c__c-1', 'o/c'))]
    pq = [prow('a__a-1', 'o/a', ['ta1'], ['a1.py']), prow('a__a-2', 'o/a', ['ta1', 'ta2'], ['a2.py']),
          prow('a__a-3', 'o/a', ['ta2'], ['a3.py']), prow('a__a-4', 'o/a', ['ta4'], ['a4.py']),
          prow('a__a-5', 'o/a', ['ta5'], ['a5.py']),
          prow('b__b-1', 'o/b', ['tb1'], ['b.py'], C2), prow('b__b-2', 'o/b', ['tb2'], ['b.py'], C2),
          prow('b__b-3', 'o/b', ['tb3'], ['b3.py']), prow('b__b-4', 'o/b', ['tb4'], ['b4.py']),
          prow('b__b-5', 'o/b', ['tb5'], ['b5.py']), prow('b__b-6', 'o/b', ['tb6'], ['b6.py']),
          prow('c__c-1', 'o/c', ['tc1'], ['c1.py'])]
    cat = {r['instance_id']: 'not_yet_assessed' for r in frame}
    cat['a__a-1'] = 'model_outcome_exposed'
    cat['b__b-1'] = 'qualification_or_inspection_only'
    return frame, cat, {'b__b-3'}, pq


def h(i):
    return hashlib.sha256(('DTR-REQ-009|c104f840|' + i).encode()).hexdigest()


def test_component_exclusion_is_transitive_and_reasons_are_exact():
    frame, cat, empty, pq = toy()
    rec = M.screen(frame, cat, empty, pq, cap=24)
    assert rec['exclusion_reason'] == {
        'a__a-1': 'model_outcome_exposed', 'a__a-2': 'component_touches_exposed_or_qualification_only',
        'a__a-3': 'component_touches_exposed_or_qualification_only', 'a__a-4': 'candidate', 'a__a-5': 'candidate',
        'b__b-1': 'qualification_or_inspection_only', 'b__b-2': 'component_touches_exposed_or_qualification_only',
        'b__b-3': 'empty_pass_to_pass', 'b__b-4': 'candidate', 'b__b-5': 'candidate', 'b__b-6': 'candidate',
        'c__c-1': 'candidate'}
    assert rec['counts']['by_reason'] == {'candidate': 6, 'component_touches_exposed_or_qualification_only': 3,
                                          'empty_pass_to_pass': 1, 'model_outcome_exposed': 1,
                                          'qualification_or_inspection_only': 1}
    assert rec['by_repository']['o/b']['component_excluded'] == 1 and rec['by_repository']['o/b']['candidates'] == 3
    sizes = sorted((m['repo'], m['size'], m['excluded']) for m in rec['multi_member_components'])
    assert sizes == [('o/a', 3, True), ('o/b', 2, True)]


def test_round_robin_queue_order_written_out_by_hand():
    frame, cat, empty, pq = toy()
    rec = M.screen(frame, cat, empty, pq, cap=4)
    a = sorted(['a__a-4', 'a__a-5'], key=h)
    b = sorted(['b__b-4', 'b__b-5', 'b__b-6'], key=h)
    # lexicographic repositories o/a, o/b, o/c; one from each per round
    assert rec['complete_ordered_list'] == [a[0], b[0], 'c__c-1', a[1], b[1], b[2]]
    assert rec['queue'] == [a[0], b[0], 'c__c-1', a[1]]
    assert rec['counts']['queue'] == 4 and rec['counts']['queue_is_full'] is True
    assert rec['queue_by_repository'] == {'o/a': 2, 'o/b': 1, 'o/c': 1}
    short = M.screen(frame, cat, empty, pq, cap=24)
    assert short['counts']['queue'] == 6 and short['counts']['queue_is_full'] is False


def test_empty_p2p_nodes_connect_components_but_do_not_taint_them():
    frame = [dict(instance_id=i, repo='o/a') for i in ('a__a-1', 'a__a-2', 'a__a-3', 'a__a-4', 'a__a-5', 'a__a-6')]
    pq = [prow('a__a-1', 'o/a', ['t1', 't2'], ['p1.py']),   # exposed AND empty P2P: links a-2 and a-3
          prow('a__a-2', 'o/a', ['t1'], ['p2.py']), prow('a__a-3', 'o/a', ['t2'], ['p3.py']),
          prow('a__a-4', 'o/a', ['t4', 't5'], ['p4.py']),   # not-yet-assessed, empty P2P: bridges a-5 and a-6
          prow('a__a-5', 'o/a', ['t4'], ['p5.py']), prow('a__a-6', 'o/a', ['t5'], ['p6.py'])]
    cat = {r['instance_id']: 'not_yet_assessed' for r in frame}
    cat['a__a-1'] = 'model_outcome_exposed'
    rec = M.screen(frame, cat, {'a__a-1', 'a__a-4'}, pq)
    assert rec['exclusion_reason'] == {
        'a__a-1': 'model_outcome_exposed', 'a__a-2': 'component_touches_exposed_or_qualification_only',
        'a__a-3': 'component_touches_exposed_or_qualification_only', 'a__a-4': 'empty_pass_to_pass',
        'a__a-5': 'candidate', 'a__a-6': 'candidate'}
    assert rec['candidate_component']['a__a-5'] == {'component': 'a__a-4', 'size': 3, 'candidate_mates': ['a__a-6']}


def test_repository_order_is_lexicographic_not_frame_order_and_renames_count_both_paths():
    frame = [dict(instance_id=i, repo=r) for i, r in (('c__c-1', 'o/c'), ('b__b-1', 'o/b'), ('a__a-1', 'o/a'))]
    pq = [prow('c__c-1', 'o/c', ['tc'], ['c.py']), prow('b__b-1', 'o/b', ['tb'], ['b.py']),
          prow('a__a-1', 'o/a', ['ta'], ['a.py'])]
    cat = {'c__c-1': 'not_yet_assessed', 'b__b-1': 'model_outcome_exposed', 'a__a-1': 'not_yet_assessed'}
    rec = M.screen(frame, cat, set(), pq)
    assert rec['complete_ordered_list'] == ['a__a-1', 'c__c-1']   # o/b has no candidate and is skipped
    rename = 'diff --git a/old.py b/new.py\n'
    rows = [dict(prow('r__r-1', 'o/r', ['t1'], ['x.py'], C1), patch=rename),
            prow('r__r-2', 'o/r', ['t2'], ['old.py'], C1)]
    edges = M.build_edges(M.edge_fields(rows))
    assert [(e['a'], e['b'], e['shared_patch_paths']) for e in edges] == [('r__r-1', 'r__r-2', ['old.py'])]


def test_missing_parquet_column_stops_and_names_the_field():
    cols = {'instance_id': [b'a__a-1'], 'repo': [b'o/a'], 'base_commit': [C1.encode()], 'patch': [b'x']}
    with pytest.raises(M.QueueStopped, match='FAIL_TO_PASS'):
        M.columns_to_rows(1, cols, ['instance_id', 'repo', 'base_commit', 'FAIL_TO_PASS', 'patch'])
    cols['FAIL_TO_PASS'] = []
    with pytest.raises(M.QueueStopped, match='FAIL_TO_PASS missing or incomplete'):
        M.columns_to_rows(1, cols, ['instance_id', 'repo', 'base_commit', 'FAIL_TO_PASS', 'patch'])
    rows = M.columns_to_rows(1, dict(cols, FAIL_TO_PASS=[b'["t"]']), ['instance_id', 'FAIL_TO_PASS'])
    assert rows == [{'instance_id': 'a__a-1', 'FAIL_TO_PASS': '["t"]'}]


def test_frame_and_parquet_must_reconcile():
    frame, cat, empty, pq = toy()
    with pytest.raises(M.QueueStopped, match='do not equal'):
        M.screen(frame, cat, empty, pq[:-1])
    pq2 = [dict(r) for r in pq]
    pq2[0]['repo'] = 'o/zz'
    with pytest.raises(M.QueueStopped, match='repo differs'):
        M.screen(frame, cat, empty, pq2)
    cat2 = dict(cat, **{'a__a-4': 'UNKNOWN'})
    with pytest.raises(M.QueueStopped, match='unexpected REQ-008 category'):
        M.screen(frame, cat2, empty, pq)


def test_committed_record_is_consistent():
    p = ROOT / 'results/v2_adapter/req009_component_queue.json'
    if not p.exists():
        pytest.skip('REQ-009 record not yet written')
    rec = json.loads(p.read_text())
    assert rec['counts']['frame'] == 500 and sum(rec['counts']['by_reason'].values()) == 500
    assert all(rec['checks'].values())
    assert rec['queue'] == rec['complete_ordered_list'][:24]
    assert sum(t['queued'] for t in rec['by_repository'].values()) == rec['counts']['queue']
    assert not {rec['exclusion_reason'][i] for i in rec['queue']} - {'candidate'}
