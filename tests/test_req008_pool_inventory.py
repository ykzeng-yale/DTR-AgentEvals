"""DTR-REQ-008 pool inventory: hand-built toy repositories with hand-derived expectations (no re-implementation).

Toy frame (8 IDs, 4 families) and the category each ID must receive, decided by hand from the fixture design:
  aa__aa-1  DEV1 + DEV2 episodes, runtime qualified, pilot selected     -> exposed (both definitions)
  aa__aa-2  untouched (named only inside an episode trajectory)         -> not_yet_assessed
  bb__bb-1  runtime qualification fail (no_change), django-like provenance -> qualification_or_inspection_only
  bb__bb-2  third-party trajectory record only; empty PASS_TO_PASS      -> exposed (conservative) /
                                                                           third_party_recorded_only (project_only)
  cc__cc-1  smoke episodes + reused smoke qualification, pilot excluded -> exposed (both; also third-party)
  cc__cc-2  reset-check first-pass flag (short form 'cc-2')             -> qualification_or_inspection_only
  cc__cc-3  planned cue frame only                                      -> frame_selected_not_run
  dd__dd-1  untouched (named only in code_routing and a server log)     -> not_yet_assessed
Runtime gate by design: aa__aa-1 pass, bb__bb-1 fail (no_change_meets_rule), cc__cc-1 pass (smoke), the rest untested.
"""
import builtins
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import time
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('req008', ROOT / 'experiments/v2_adapter/req008_pool_inventory.py')
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

DSHA = 'd' * 64
ECOMMIT = 'e' * 40
REV = 'r' * 40
ACC_KEYS = ('pins_and_script_hashes_agree', 'stock_reference_required_test_maps_agree',
            'stock_reference_strict_outcomes_agree', 'reference_passes_required_tests', 'no_change_meets_rule')
IDS = [('aa__aa-1', 'aa/aa', '1.0'), ('aa__aa-2', 'aa/aa', '1.0'), ('bb__bb-1', 'bb/bb', '2.0'),
       ('bb__bb-2', 'bb/bb', '2.0'), ('cc__cc-1', 'cc/cc', '3.0'), ('cc__cc-2', 'cc/cc', '3.0'),
       ('cc__cc-3', 'cc/cc', '3.1'), ('dd__dd-1', 'dd/dd', '4.0')]
ALL_IDS = [i for i, _, _ in IDS]
QDIR = 'results/v2_adapter/qualification_20260922'
DEV1 = 'results/v2_agent/pilot_20260922'
DEV2 = 'results/v2_agent/pilot_20260922_yaml_v1'
SMOKE = 'results/v2_agent/smoke_episode_20260922'


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


# The toy's only unexplained narrative mention of an unexposed ID with a non-metadata touch: docs/notes.md names
# 'cc-2' (cc__cc-2); manifest = sorted '<path>\t<id>' lines (hand-derived from make_toy below).
M.NARRATIVE_REVIEW = OrderedDict(M.NARRATIVE_REVIEW, manifest_sha256=sha('docs/notes.md\tcc__cc-2'))


def put(root, rel, obj):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = obj if isinstance(obj, (str, bytes)) else json.dumps(obj, indent=1)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return sha(p.read_bytes())


def acc(**false):
    return {k: k not in false for k in ACC_KEYS}


def make_toy(tmp_path, extra_ran=(), drop_planned=None, tamper_record=False, no_replay=False, extra_files=None,
             dev1_extra=None, dev2_extra=None):
    root = tmp_path / 'repo'
    root.mkdir(parents=True)
    rows = []
    for iid, repo, ver in IDS:
        rows.append(dict(instance_id=iid, repo=repo, version=ver, qualification='eligible', reasons=[],
                         limitations=['PASS_TO_PASS empty: regression preservation is untested for this instance']
                         if iid == 'bb__bb-2' else [],
                         content_sha256=sha(iid), repo_version_in_constants=True, fail_only_repo=False,
                         eval_script_sha256=sha('eval ' + iid), construction='ok',
                         content_unchanged_by_construction=True, instance_image_key='sweb.eval.x86_64.%s:latest' % iid,
                         env_image_key='sweb.env.%s' % repo.split('/')[0], base_image_key='sweb.base',
                         n_fail_to_pass=1, n_pass_to_pass=0 if iid == 'bb__bb-2' else 3))
    src = put(root, M.P['m01_instances'], ''.join(json.dumps(r) + '\n' for r in rows))
    put(root, M.P['download_audit'], dict(dataset='toy/ds', revision=REV, file='data/toy.parquet', sha256=DSHA,
                                          upstream_lfs_sha256=DSHA))
    put(root, M.P['evaluator_selection'], dict(dataset=dict(repository='toy/ds', revision=REV, expected_instances=8),
                                               evaluator=dict(commit=ECOMMIT)))
    put(root, M.P['m01_summary'], dict(dataset=dict(path='x.parquet', sha256=DSHA, rows=8), evaluator=dict(commit=ECOMMIT),
                                       qualification=dict(eligible=8, refused=0), empty_pass_to_pass_limitation=1,
                                       construction_ok=8, replay_identical=8, not_done=['image digests not resolved']))
    put(root, M.P['m01_reset'], dict(checked=8, with_problems=0, new_file_only_test_patches=1,
                                     note='first pass flagged 1 script (cc-2): a false positive; nothing executed'))
    put(root, M.P['control_template'], dict(
        m01_instances_sha256=src, records=[dict(instance_id=i, control=c) for i, _, _ in IDS for c in ('no_change', 'reference')],
        controls=dict(no_change=dict(qualification='toy rule'), reference=dict(qualification='toy rule')),
        smoke_check=dict(acceptance=['toy acceptance text'])))
    for rel in ('m01_code', 'm02_code', 'qual_code', 'control_adapter_code', 'pilot_runner'):
        put(root, M.P[rel], '# toy source for %s\n' % rel)
    put(root, M.P['protocol'], 'toy protocol\n')
    put(root, M.P['runbook'], 'toy runbook\n')
    put(root, M.P['request_text'], 'toy handoff\n')
    manifest_sha = put(root, M.P['qual_manifest'], dict(
        source_sha256=src, selection_rule='toy', tasks=[dict(instance_id=i) for i in ('aa__aa-1', 'bb__bb-1', 'cc__cc-1')]))
    ident = dict(manifest_sha256=manifest_sha, source_sha256=src, dataset_sha256=DSHA, evaluator_commit=ECOMMIT)
    recs = {}
    for iid, a, q in (('aa__aa-1', acc(), True), ('bb__bb-1', acc(no_change_meets_rule=1), False)):
        recs[iid] = put(root, '%s/%s/summary.json' % (QDIR, iid), dict(
            instance_id=iid, qualified=q, acceptance=a, stage_failed=None, finished_utc='t',
            platform=dict(evaluator_commit=ECOMMIT), stock=dict(resolved='TRAP_OUTCOME')))
        put(root, '%s/%s/stock_gold_test_output.txt' % (QDIR, iid), 'gold log for %s\n' % iid)
    planned = ['aa__aa-1', 'bb__bb-1']
    if drop_planned:
        planned.remove(drop_planned)
    put(root, M.P['qual_status'], dict(planned_new=planned, reused=['cc__cc-1'], completed=[
        dict(instance_id='aa__aa-1', qualified=True, stage_failed=None, acceptance=acc()),
        dict(instance_id='bb__bb-1', qualified=False, stage_failed=None, acceptance=acc(no_change_meets_rule=1))]))
    legacy_sha = put(root, M.P['qual_legacy'], dict(expected_identity=ident, records=[
        dict(instance_id=i, summary='%s/summary.json' % i, sha256=recs[i]) for i in ('aa__aa-1', 'bb__bb-1')]))
    smoke_sha = put(root, M.P['smoke_flask'], dict(instance_id='cc__cc-1', acceptance=acc(), smoke_check_passed=True,
                                                   scope='toy smoke', stock=dict(resolved='TRAP_OUTCOME')))
    put(root, M.P['m03'], dict(instance_used=dict(instance_id='cc__cc-1'), not_done=['other parsers'], request='toy'))
    put(root, M.P['django_provenance'], dict(task='bb__bb-1', step='1', scope='no model', verdict='toy verdict'))
    put(root, M.DJANGO_PROVENANCE_DIR + 'isolated_runs.txt', 'diagnostic run of bb__bb-1\n')
    put(root, M.P['runtime'], dict(amd64_translation_check='x86_64', vm=dict(profile='toy')))
    spec_sha = put(root, M.P['pilot_spec'], dict(selection=dict(frame='toy')))
    dev2_spec = dict(cohort='yaml-v1', frame=M.P['pilot_frame'], base_spec=M.P['pilot_spec'], base_spec_sha256=spec_sha,
                     verdict='TRAP_OUTCOME')
    pf_sha = put(root, M.P['pilot_frame'], dict(
        expected_identity=ident, legacy_hash_manifest_sha256=legacy_sha, spec_sha256=spec_sha,
        frame=dict(tasks=[
            dict(instance_id='aa__aa-1', qualified=True, failed_acceptance=[], record='%s/aa__aa-1/summary.json' % QDIR,
                 record_sha256=recs['aa__aa-1']),
            dict(instance_id='bb__bb-1', qualified=False, failed_acceptance=['no_change_meets_rule'],
                 record='%s/bb__bb-1/summary.json' % QDIR, record_sha256=recs['bb__bb-1']),
            dict(instance_id='cc__cc-1', qualified=True, failed_acceptance=[], record=M.P['smoke_flask'],
                 record_sha256=smoke_sha)],
            diagnosed_unqualified=['bb__bb-1']),
        pilot=dict(ranked_eligible=[dict(instance_id='aa__aa-1', selected=True)], tasks=[dict(instance_id='aa__aa-1')],
                   excluded=['cc__cc-1'], excluded_reason='already used')))
    dev2_spec_sha = put(root, M.P['dev2_spec'], dict(dev2_spec, frame_sha256=pf_sha))
    for d, tag, cohort, extra in ((DEV1, 'pilot-x', None, dev1_extra), (DEV2, 'pilot-x-yaml-v1', 'yaml-v1', dev2_extra)):
        ran = [dict(instance_id='aa__aa-1', backend=b, run_id='aa__aa-1__%s__%s__T%d' % (b, tag, k), exit_status='TRAP_OUTCOME')
               for k, b in enumerate(('small', 'large'))]
        for r in ran:
            put(root, '%s/%s/episode.json' % (d, r['run_id']), '{"resolved": "TRAP_OUTCOME"}')
            put(root, '%s/%s/trajectory.json' % (d, r['run_id']), 'NOT JSON: the agent looked at aa__aa-2 and dd-1')
        if d == DEV1:
            ran += list(extra_ran)
        blk = dict(frame_sha256=pf_sha, ran=ran, retained_incomplete=[], unstarted=[], skipped_completed=[],
                   preflight=dict(resolved='TRAP_OUTCOME'))
        if cohort:
            blk.update(cohort=cohort, amendment_sha256=dev2_spec_sha)
            put(root, '%s/cohort_binding.json' % d, dict(cohort=cohort, amendment_sha256=dev2_spec_sha,
                                                         sources=['TRAP_OUTCOME']))
        blk.update(extra or {})
        put(root, '%s/block_1_start.json' % d, dict(block=1, note='toy start record'))
        put(root, '%s/block_1.json' % d, blk)
        put(root, '%s/report_final.json' % d, '{"aa__aa-1": {"resolved": ')      # deliberately not valid JSON
        put(root, '%s/server_small_T0.log' % d, 'prompt mentions dd__dd-1 and aa__aa-2\n')
    for b in ('small', 'large'):
        put(root, '%s/cc__cc-1__%s/episode.json' % (SMOKE, b), '{"resolved": "TRAP_OUTCOME"}')
        put(root, '%s/cc__cc-1__%s/trajectory.json' % (SMOKE, b), 'dd__dd-1 aa__aa-2')
    put(root, M.P['smoke_audit'], dict(episodes=[dict(directory='%s/cc__cc-1__%s' % (SMOKE, b), exit_status='TRAP_OUTCOME')
                                                 for b in ('small', 'large')]))
    if not no_replay:
        put(root, M.P['replay_gap'], dict(dataset='toy/release', revision='r0', unique_tasks_total=2, files=[
            dict(file='e.jsonl.gz', sha256='0' * 64, source_url='u', task_ids=['bb__bb-2', 'cc__cc-1'],
                 resolved={'False': 'TRAP_OUTCOME'})]))
    put(root, M.P['cue_registry'], "COHORT = 'cue-v1'\nCOHORTS = {COHORT: 'pilot_toy_cue'}\nTASKS = ('cc__cc-3',)\n")
    put(root, 'docs/notes.md', 'We discussed aa__aa-1 and the cc-2 reset flag.\n')
    put(root, 'results/code_routing/live/trap.json', '{"task": "dd__dd-1"}')
    put(root, 'results/code_routing/branch/trap.json', '{"task": "aa__aa-2"}')
    if tamper_record:
        with open(root / QDIR / 'aa__aa-1' / 'summary.json', 'ab') as fh:
            fh.write(b' ')
    for rel, content in (extra_files or {}).items():
        put(root, rel, content)
    return root


PINS = dict(dataset='toy/ds', dataset_revision=REV, dataset_file='data/toy.parquet', source_sha256=None,
            dataset_sha256=DSHA, evaluator_commit=ECOMMIT, n_rows=8)


def run(root, **pin_overrides):
    pins = dict(PINS, source_sha256=sha((root / M.P['m01_instances']).read_bytes()))
    pins.update(pin_overrides)
    return M.build(root, pins=pins)


def cats(rec, d):
    return {r['instance_id']: r['category'][d] for r in rec['rows']}


EXPECTED = {
    'conservative': {'aa__aa-1': 'model_outcome_exposed', 'aa__aa-2': 'not_yet_assessed',
                     'bb__bb-1': 'qualification_or_inspection_only', 'bb__bb-2': 'model_outcome_exposed',
                     'cc__cc-1': 'model_outcome_exposed', 'cc__cc-2': 'qualification_or_inspection_only',
                     'cc__cc-3': 'frame_selected_not_run', 'dd__dd-1': 'not_yet_assessed'},
    'project_only': {'aa__aa-1': 'model_outcome_exposed', 'aa__aa-2': 'not_yet_assessed',
                     'bb__bb-1': 'qualification_or_inspection_only', 'bb__bb-2': 'third_party_recorded_only',
                     'cc__cc-1': 'model_outcome_exposed', 'cc__cc-2': 'qualification_or_inspection_only',
                     'cc__cc-3': 'frame_selected_not_run', 'dd__dd-1': 'not_yet_assessed'},
}


def git(root, *args):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_AUTHOR_NAME='toy', GIT_AUTHOR_EMAIL='toy@example.invalid',
               GIT_COMMITTER_NAME='toy', GIT_COMMITTER_EMAIL='toy@example.invalid')
    subprocess.run(['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                    '-c', 'user.name=toy', '-c', 'user.email=toy@example.invalid'] + list(args),
                   check=True, capture_output=True, env=env)


def record_opens(monkeypatch):
    opened, listed = [], []
    real_open, real_listdir, real_scandir = builtins.open, os.listdir, os.scandir

    def rec_open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    def rec_listdir(path='.'):
        listed.append(str(path))
        return real_listdir(path)

    def rec_scandir(path='.'):
        listed.append(str(path))
        return real_scandir(path)
    monkeypatch.setattr(builtins, 'open', rec_open)
    monkeypatch.setattr(io, 'open', rec_open)
    monkeypatch.setattr(os, 'listdir', rec_listdir)
    monkeypatch.setattr(os, 'scandir', rec_scandir)
    return opened, listed


# ------------------------------------------------------------------ categories and counts
def test_category_priority_and_counts(tmp_path):
    rec = run(make_toy(tmp_path))
    assert rec['unknowns'] == []
    assert all(c['ok'] for c in rec['consistency_checks']), [c for c in rec['consistency_checks'] if not c['ok']]
    assert rec['pins']['pins_reconciled'] is True
    for d in ('conservative', 'project_only'):
        assert cats(rec, d) == EXPECTED[d]
    c, p = rec['counts']['conservative'], rec['counts']['project_only']
    assert M.CATEGORIES == ('model_outcome_exposed', 'qualification_or_inspection_only', 'third_party_recorded_only',
                            'frame_selected_not_run', 'not_yet_assessed')
    assert [c[k] for k in M.CATEGORIES] == [3, 2, 0, 1, 2]
    assert [p[k] for k in M.CATEGORIES] == [2, 2, 1, 1, 2]
    for blk in (c, p):
        assert blk['unknown_ids'] == 0 and blk['total_ids'] == 8 and blk['sum_check'] is True
        assert sum(blk[k] for k in M.CATEGORIES) == 8
        assert sum(f['total'] for f in blk['families'].values()) == 8
    assert c['n_families'] == 4
    assert (c['n_families_with_zero_exposed_ids'], p['n_families_with_zero_exposed_ids']) == (1, 2)
    assert (c['n_families_with_not_yet_assessed_ids'], p['n_families_with_not_yet_assessed_ids']) == (2, 2)
    assert (c['n_families_with_unexposed_ids'], p['n_families_with_unexposed_ids']) == (4, 4)
    assert (c['unexposed_ids'], p['unexposed_ids']) == (5, 6)
    assert (c['not_yet_assessed_with_empty_p2p_limitation'], p['not_yet_assessed_with_empty_p2p_limitation']) == (0, 0)
    assert c['families']['cc/cc'] == dict(total=3, model_outcome_exposed=1, qualification_or_inspection_only=1,
                                          third_party_recorded_only=0, frame_selected_not_run=1, not_yet_assessed=0,
                                          UNKNOWN=0, not_yet_assessed_with_empty_p2p=0)
    assert p['families']['bb/bb']['third_party_recorded_only'] == 1 and c['families']['bb/bb']['model_outcome_exposed'] == 1
    # qualification_or_inspection_only split: bb__bb-1 ran evaluator controls, cc__cc-2 was only source-inspected
    for blk in (c, p):
        sp = blk['qualification_or_inspection_only_split']
        assert (sp['evaluator_touched']['n'], sp['evaluator_touched']['ids']) == (1, ['bb__bb-1'])
        assert (sp['source_inspection_only']['n'], sp['source_inspection_only']['ids']) == (1, ['cc__cc-2'])
        assert sp['evaluator_touched']['id_list_sha256'] == sha('bb__bb-1\n')
        assert sp['source_inspection_only']['id_list_sha256'] == sha('cc__cc-2\n')


def test_category_priority_rule_by_hand():
    tp, qi, fs, md = 'third_party_recorded_episode', 'source_inspection', 'frame_selection', 'metadata_static'
    proj, cons = M.DEFINITIONS['project_only'], M.DEFINITIONS['conservative']
    assert M.categorize({tp, qi, md}, proj) == 'qualification_or_inspection_only'
    assert M.categorize({tp, fs, md}, proj) == 'third_party_recorded_only'
    assert M.categorize({tp, fs, md}, cons) == 'model_outcome_exposed'
    assert M.categorize({fs, md}, proj) == 'frame_selected_not_run'
    assert M.categorize({md}, cons) == 'not_yet_assessed'


def test_id_list_identities_use_the_stated_serialization(tmp_path):
    rec = run(make_toy(tmp_path))

    def h(ids):          # sorted IDs, each followed by a newline (hand-written from the stated serialization)
        return sha(''.join(i + '\n' for i in sorted(ids)))
    assert rec['pins']['id_set_sha256'] == h(ALL_IDS)
    c, p = rec['counts']['conservative'], rec['counts']['project_only']
    assert c['ids_by_category']['not_yet_assessed'] == ['aa__aa-2', 'dd__dd-1']
    assert p['ids_by_category']['not_yet_assessed'] == ['aa__aa-2', 'dd__dd-1']
    assert p['ids_by_category']['third_party_recorded_only'] == ['bb__bb-2']
    assert c['ids_by_category']['third_party_recorded_only'] == []
    assert c['id_list_sha256']['not_yet_assessed'] == sha('aa__aa-2\ndd__dd-1\n')
    assert p['id_list_sha256']['not_yet_assessed'] == sha('aa__aa-2\ndd__dd-1\n')
    assert p['id_list_sha256']['third_party_recorded_only'] == sha('bb__bb-2\n')
    assert c['id_list_sha256']['unexposed'] == sha('aa__aa-2\nbb__bb-1\ncc__cc-2\ncc__cc-3\ndd__dd-1\n')
    assert p['id_list_sha256']['unexposed'] == sha('aa__aa-2\nbb__bb-1\nbb__bb-2\ncc__cc-2\ncc__cc-3\ndd__dd-1\n')
    assert c['id_list_sha256']['UNKNOWN'] == sha('') and c['id_list_sha256']['all'] == h(ALL_IDS)


def test_gates_and_touch_evidence(tmp_path):
    rec = run(make_toy(tmp_path))
    rows = {r['instance_id']: r for r in rec['rows']}
    assert [r['runtime_gate']['status'] for r in rec['rows']] == [
        'pass', 'untested', 'fail', 'untested', 'pass', 'untested', 'untested', 'untested']
    assert rows['bb__bb-1']['runtime_gate']['failed_acceptance_keys'] == ['no_change_meets_rule']
    assert {r['metadata_gate']['status'] for r in rec['rows']} == {'pass'}
    assert rec['metadata_gate_summary']['empty_pass_to_pass_limitation'] == ['bb__bb-2']
    assert rows['aa__aa-1']['touches']['model_outcome_episode'] == sorted([
        DEV1 + '/aa__aa-1__small__pilot-x__T0/', DEV1 + '/aa__aa-1__large__pilot-x__T1/', DEV1 + '/block_1.json#ran',
        DEV2 + '/aa__aa-1__small__pilot-x-yaml-v1__T0/', DEV2 + '/aa__aa-1__large__pilot-x-yaml-v1__T1/',
        DEV2 + '/block_1.json#ran'])
    assert rows['cc__cc-2']['touches']['source_inspection'] == [M.P['m01_reset'] + '#note (first-pass flag; static)']
    # derivative mentions are listed only for IDs exposed under neither definition; exposed IDs carry a count only
    # (aa__aa-1: docs/notes.md and the two cohort report_final.json files)
    # exposed IDs carry neither per-ID mention paths nor a per-ID mention count (outcome side channel)
    assert rows['aa__aa-1']['derivative_mentions'] is None and rows['aa__aa-1']['n_derivative_mentions'] is None
    assert rows['cc__cc-2']['derivative_mentions'] == ['docs/notes.md']
    assert rows['aa__aa-2']['derivative_mentions'] == [] and rows['dd__dd-1']['derivative_mentions'] == []
    rv = rec['narrative_mention_review']
    assert rv['current_mentions'] == ['docs/notes.md\tcc__cc-2'] and rv['current_matches_review'] is True
    assert list(rows['aa__aa-2']['touches']) == ['metadata_static']


def test_no_eligibility_or_qualified_labels_outside_runtime_gate_and_frame_roles(tmp_path):
    rec = run(make_toy(tmp_path))

    def walk(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k != 'qualification', path + [k]
                yield from walk(v, path + [k])
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v, path)
        else:
            yield path, obj
    for row in rec['rows']:
        for path, v in walk({k: v for k, v in row.items() if k not in ('runtime_gate', 'frame_roles')}, []):
            assert v not in ('eligible', 'qualified'), (row['instance_id'], path)
        assert row['metadata_gate']['m02_test_list_status'] == 'test_lists_valid'


def test_outputs_are_write_once_and_carry_no_outcomes(tmp_path):
    rec = run(make_toy(tmp_path))
    out_j, out_m = tmp_path / 'inv.json', tmp_path / 'inv.md'
    M.write_outputs(rec, out_j, out_m)
    text = out_j.read_text() + out_m.read_text()
    assert 'TRAP_OUTCOME' not in text
    assert json.loads(out_j.read_text())['counts']['conservative']['not_yet_assessed'] == 2
    assert 'No eligibility claim' in out_m.read_text()
    assert 'byte-scanned for pinned-ID tokens only' in out_m.read_text()
    assert 'object_pairs_hook' in out_m.read_text() and 'lead decision pending' in out_m.read_text()
    assert 'default_definition' not in text and 'is the default' not in text
    assert rec['definitions']['exposure_definition'].startswith('lead decision pending')
    with pytest.raises(FileExistsError):
        M.write_outputs(rec, out_j, tmp_path / 'other.md')


def test_render_failure_leaves_no_output_file(tmp_path, monkeypatch):
    rec = run(make_toy(tmp_path))

    def boom(_):
        raise RuntimeError('render failed')
    monkeypatch.setattr(M, 'render_md', boom)
    with pytest.raises(RuntimeError):
        M.write_outputs(rec, tmp_path / 'a.json', tmp_path / 'a.md')
    assert not (tmp_path / 'a.json').exists() and not (tmp_path / 'a.md').exists()


def test_decoded_outcome_bearing_records_retain_only_allow_listed_keys(tmp_path, monkeypatch):
    parsed, real = {}, M.Ctx.load_json

    def spy(self, rel, *a, **k):
        parsed[rel] = real(self, rel, *a, **k)
        return parsed[rel]
    monkeypatch.setattr(M.Ctx, 'load_json', spy)
    run(make_toy(tmp_path))
    for rel in (DEV1 + '/block_1.json', DEV2 + '/block_1.json', DEV2 + '/cohort_binding.json', M.P['dev2_spec'],
                M.P['replay_gap']):
        text = json.dumps(parsed[rel])
        assert 'TRAP_OUTCOME' not in text and 'exit_status' not in text and 'resolved' not in text, rel
    assert parsed[DEV1 + '/block_1.json']['ran'][0] == dict(instance_id='aa__aa-1', backend='small',
                                                           run_id='aa__aa-1__small__pilot-x__T0')
    assert set(parsed[DEV1 + '/block_1.json']) == {'frame_sha256', 'ran', 'retained_incomplete', 'unstarted',
                                                    'skipped_completed'}
    assert parsed[M.P['replay_gap']] == dict(dataset='toy/release', revision='r0', unique_tasks_total=2, files=[
        dict(file='e.jsonl.gz', sha256='0' * 64, task_ids=['bb__bb-2', 'cc__cc-1'])])


def test_registered_cohort_inputs_and_roles(tmp_path):
    rec = run(make_toy(tmp_path))
    reg = {e['path']: e for e in rec['inputs']}
    for rel in (DEV1, DEV2, QDIR, SMOKE):
        assert reg[rel]['kind'] == 'directory' and len(reg[rel]['sha256']) == 64
    assert reg[DEV2]['sha256'] == sha('\n'.join(sorted(os.listdir(tmp_path / 'repo' / DEV2))))
    for rel in (DEV1 + '/block_1_start.json', DEV2 + '/block_1_start.json', M.P['dev2_spec']):
        assert reg[rel]['exists'] is True and reg[rel]['sha256'] == sha((tmp_path / 'repo' / rel).read_bytes())
    assert reg[M.P['protocol']]['role'] == 'v2 protocol (infrastructure gate, strict grading rule, grouping rule)'
    assert reg[M.P['request_text']]['role'] == 'lead request text (DTR-REQ-008) and committed host narrative'
    ok = {c['check']: c['ok'] for c in rec['consistency_checks']}
    assert ok['DEV2_spec_cites_pilot_frame_and_base_spec'] and ok['DEV2_amendment_sha256_matches_spec']
    rec2 = run(make_toy(tmp_path / 'b', dev2_extra=dict(amendment_sha256='0' * 64)))
    assert not {c['check']: c['ok'] for c in rec2['consistency_checks']}['DEV2_amendment_sha256_matches_spec']


def test_missing_qualification_status_makes_runtime_gate_unknown(tmp_path):
    root = make_toy(tmp_path)
    (root / M.P['qual_status']).unlink()
    rec = run(root)
    assert [r['runtime_gate']['status'] for r in rec['rows']] == [
        'UNKNOWN', 'untested', 'UNKNOWN', 'untested', 'UNKNOWN', 'untested', 'untested', 'untested']
    assert rec['counts']['project_only']['not_yet_assessed'] == 'UNKNOWN'
    (root / M.P['pilot_frame']).unlink()               # manifest/legacy/smoke IDs stay UNKNOWN without the frame
    assert [r['runtime_gate']['status'] for r in run(root)['rows']][:5] == ['UNKNOWN', 'untested', 'UNKNOWN',
                                                                          'untested', 'UNKNOWN']
    root2 = make_toy(tmp_path / 'b')                    # a frame task with no qualification record at all
    pf = json.loads((root2 / M.P['pilot_frame']).read_text())
    pf['frame']['tasks'].append(dict(instance_id='dd__dd-1', qualified=False, failed_acceptance=[], record='x',
                                     record_sha256='0' * 64))
    put(root2, M.P['pilot_frame'], pf)
    for k in ('qual_status', 'qual_manifest'):
        (root2 / M.P[k]).unlink()
    assert {r['instance_id']: r['runtime_gate']['status'] for r in run(root2)['rows']}['dd__dd-1'] == 'UNKNOWN'


def test_docs_json_is_record_like_and_self_paths_are_excluded(tmp_path):
    rec = run(make_toy(tmp_path, extra_files={'docs/summary_note.json': '{"note": "bb__bb-1 was discussed"}'}))
    for d in ('conservative', 'project_only'):
        assert cats(rec, d)['bb__bb-1'] == 'UNKNOWN'
    assert {u['artifact'] for u in rec['unknowns']} == {'docs/summary_note.json'}
    self_files = {M.OUT_MD_DEFAULT: 'dd__dd-1 and aa-2', M.OUT_JSON_DEFAULT: '{"x": "dd__dd-1"}',
                  M.TEST_REL: "'aa__aa-2'", M.SCRIPT_REL: '# dd-1'}
    rec2 = run(make_toy(tmp_path / 'b', extra_files=self_files))
    assert rec2['unknowns'] == [] and cats(rec2, 'project_only') == EXPECTED['project_only']
    assert rec2['mention_scan']['self_excluded_paths']['present_and_skipped'] == sorted(self_files)


# ------------------------------------------------------------------ never-open rules
def test_never_opens_code_routing_or_episode_contents(tmp_path, monkeypatch):
    root = make_toy(tmp_path)
    opened, listed = record_opens(monkeypatch)
    rec = run(root)
    monkeypatch.undo()
    assert any(p.endswith('block_1.json') for p in opened)
    forbidden = str(root / 'results' / 'code_routing')
    assert not [p for p in opened + listed if p.startswith(forbidden)]
    inside = [str(root / d) for d in (DEV1, DEV2, SMOKE)]
    assert not [p for p in opened if any(p.startswith(i + '/') and '/' in p[len(i) + 1:] for i in inside)]
    assert not [p for p in opened if 'server_small' in p]
    # the IDs planted only in never-opened places stay untouched
    assert cats(rec, 'conservative')['dd__dd-1'] == 'not_yet_assessed'
    assert cats(rec, 'conservative')['aa__aa-2'] == 'not_yet_assessed'


def test_is_never_open_rule():
    assert M.is_never_open('results/code_routing/live/x.json')
    assert M.is_never_open('results/code_routing/branch/decisions.jsonl')
    assert M.is_never_open(DEV1 + '/aa__aa-1__small__x/trajectory.json')
    assert M.is_never_open(DEV2 + '/server_large_2026.log')
    assert M.is_never_open(SMOKE + '/cc__cc-1__small/episode.json')
    assert not M.is_never_open(DEV1 + '/block_1.json')
    assert not M.is_never_open(QDIR + '/aa__aa-1/summary.json')


def test_git_mode_enumerates_tracked_and_historical_paths_without_code_routing(tmp_path, monkeypatch):
    root = make_toy(tmp_path, extra_files={
        '.gitignore': 'work/\n',
        'results/v2_agent/old_probe/bb__bb-1__small__probe/episode.json': '{}',
        'results/code_routing/live/aa__aa-2__small__x.json': '{"episode": "aa__aa-2"}'})
    git(root, 'init', '-q')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'toy 1')
    git(root, 'rm', '-q', 'results/v2_agent/old_probe/bb__bb-1__small__probe/episode.json',
        'results/code_routing/live/aa__aa-2__small__x.json')
    git(root, 'commit', '-q', '-m', 'toy 2')
    put(root, 'results/code_routing/live/untracked_new.json', '{"episode": "aa__aa-2"}')   # excluded from git status
    opened, listed = record_opens(monkeypatch)
    rec = run(root)
    monkeypatch.undo()
    assert rec['mention_scan']['mode'].startswith('git ls-files')
    assert rec['mention_scan']['history_scope'].startswith('git log HEAD')
    assert rec['mention_scan']['historical_paths_available'] is True
    pv = rec['provenance']
    assert len(pv['head_commit']) == 40 and pv['worktree_clean'] is True and pv['script_tracked_at_head'] is False
    assert pv['worktree_status_porcelain'] == []
    # the deleted episode-like path for bb__bb-1 is found in history; the code_routing history path is ignored
    for d in ('conservative', 'project_only'):
        assert cats(rec, d)['bb__bb-1'] == 'UNKNOWN'
        assert cats(rec, d)['aa__aa-2'] == 'not_yet_assessed'
        assert cats(rec, d)['dd__dd-1'] == 'not_yet_assessed'
    assert {u['artifact'] for u in rec['unknowns']} == {'results/v2_agent/old_probe/bb__bb-1__small__probe/episode.json'}
    forbidden = str(root / 'results' / 'code_routing')
    assert not [p for p in opened + listed if p.startswith(forbidden)]
    assert rec['inputs'][0]['tracked'] is True and rec['inputs'][0]['git_first_commit'] is not None


def test_id_named_after_the_source_checkpoint_becomes_unknown(tmp_path, monkeypatch):
    root = make_toy(tmp_path, extra_files={'.gitignore': 'work/\n'})
    git(root, 'init', '-q')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'checkpoint')
    checkpoint = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                                check=True).stdout.strip()
    # after the checkpoint: a narrative note names the untouched dd__dd-1; code_routing changes are ignored
    put(root, 'docs/later_note.md', 'dd__dd-1 looked interesting\n')
    put(root, 'results/code_routing/log/x.json', '{"task": "aa__aa-2"}')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'after checkpoint')
    monkeypatch.setattr(M, 'SOURCE_CHECKPOINT', checkpoint)
    rec = run(root)
    scan = rec['provenance']['source_checkpoint_diff_scan']
    assert scan['status'] == 'scanned' and scan['files_with_pinned_ids'] == {'docs/later_note.md': ['dd__dd-1']}
    assert {c['check']: c['ok'] for c in rec['consistency_checks']}['no_pinned_id_added_since_source_checkpoint'] is False
    for d in ('conservative', 'project_only'):
        assert cats(rec, d)['dd__dd-1'] == 'UNKNOWN'
        assert cats(rec, d)['aa__aa-2'] == 'not_yet_assessed'


def test_absent_source_checkpoint_is_a_visible_failed_check_not_silent(tmp_path):
    root = make_toy(tmp_path, extra_files={'.gitignore': 'work/\n'})
    git(root, 'init', '-q')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'toy')
    rec = run(root)
    assert rec['provenance']['source_checkpoint_diff_scan']['status'] == 'source_checkpoint_absent'
    assert {c['check']: c['ok'] for c in rec['consistency_checks']}['no_pinned_id_added_since_source_checkpoint'] is False


# ------------------------------------------------------------------ UNKNOWN propagation
def test_unknown_propagates_when_an_exposure_source_is_missing(tmp_path):
    rec = run(make_toy(tmp_path, no_replay=True))
    c, p = rec['counts']['conservative'], rec['counts']['project_only']
    assert [c[k] for k in M.CATEGORIES] == ['UNKNOWN'] * 5
    assert c['unknown_ids'] == 6 and c['known_lower_bounds']['model_outcome_exposed'] == 2 and c['sum_check'] is True
    assert cats(rec, 'conservative')['aa__aa-1'] == 'model_outcome_exposed'
    assert cats(rec, 'conservative')['dd__dd-1'] == 'UNKNOWN'
    assert [p[k] for k in M.CATEGORIES] == [2, 2, 0, 1, 3]          # without the record bb__bb-2 is not yet assessed
    missing = [u for u in rec['unknowns'] if u['artifact'] == M.P['replay_gap']]
    assert missing and missing[0]['scope'] == 'global' and missing[0]['definitions'] == ['conservative']


def test_unreconciled_mention_or_path_makes_the_id_unknown(tmp_path):
    rec = run(make_toy(tmp_path, extra_files={'docs/extra.md': 'see dd-1 for details\n'}))
    for d in ('conservative', 'project_only'):
        assert cats(rec, d)['dd__dd-1'] == 'UNKNOWN'
        assert rec['counts'][d]['not_yet_assessed'] == 'UNKNOWN'
        assert rec['counts'][d]['known_lower_bounds']['not_yet_assessed'] == 1
    assert [u['artifact'] for u in rec['unknowns']] == ['docs/extra.md']

    rec2 = run(make_toy(tmp_path / 'b', extra_files={DEV1 + '/aa__aa-2__small__pilot-x__T9/episode.json': '{}'}))
    assert cats(rec2, 'project_only')['aa__aa-2'] == 'UNKNOWN'
    assert cats(rec2, 'project_only')['aa__aa-1'] == 'model_outcome_exposed'
    assert any(c['check'] == 'DEV1_no_unlisted_episode_dirs' and not c['ok'] for c in rec2['consistency_checks'])


def test_unregistered_run_manifest_makes_non_exposed_ids_unknown_per_definition(tmp_path):
    new = 'results/v2_agent/pilot_20260930_new/block_1.json'
    rec = run(make_toy(tmp_path, extra_files={new: dict(ran=[dict(instance_id='bb__bb-2'),
                                                              dict(instance_id='bb__bb-1')])}))
    exp_c = dict(EXPECTED['conservative'], **{'bb__bb-1': 'UNKNOWN'})
    exp_p = dict(EXPECTED['project_only'], **{'bb__bb-1': 'UNKNOWN', 'bb__bb-2': 'UNKNOWN'})
    assert cats(rec, 'conservative') == exp_c and cats(rec, 'project_only') == exp_p
    assert (rec['counts']['conservative']['unknown_ids'], rec['counts']['project_only']['unknown_ids']) == (1, 2)
    assert {u['artifact'] for u in rec['unknowns']} == {new}
    # a narrative (non-record) mention of an ID that already has a qualification touch stays derivative; it changes
    # the manually reviewed narrative manifest, which adds a global note only (categories unchanged)
    rec2 = run(make_toy(tmp_path / 'b', extra_files={'docs/more_notes.md': 'bb__bb-1 failed its control\n'}))
    assert cats(rec2, 'project_only') == EXPECTED['project_only']
    assert [(u['scope'], u['affects'], u['artifact']) for u in rec2['unknowns']] == [
        ('global', 'note', 'narrative mentions')]
    assert rec2['narrative_mention_review']['current_matches_review'] is False
    assert rec2['narrative_mention_review']['current_mentions'] == ['docs/more_notes.md\tbb__bb-1',
                                                                    'docs/notes.md\tcc__cc-2']


def test_derivative_record_whitelist_is_sha_pinned(tmp_path, monkeypatch):
    audit = 'docs/audits/toy_audit.json'
    content = '{"records": ["bb__bb-1"]}'
    root = make_toy(tmp_path, extra_files={audit: content})
    rec = run(root)
    assert cats(rec, 'conservative')['bb__bb-1'] == 'UNKNOWN'
    monkeypatch.setattr(M, 'DERIVATIVE_RECORD_WHITELIST', {audit: dict(sha256=sha(content), reason='toy audit')})
    rec2 = run(root)
    assert rec2['unknowns'] == [] and cats(rec2, 'conservative') == EXPECTED['conservative']
    assert rec2['derivative_record_whitelist'][audit]['accepted'] is True
    monkeypatch.setattr(M, 'DERIVATIVE_RECORD_WHITELIST', {audit: dict(sha256='0' * 64, reason='toy audit')})
    rec3 = run(root)
    assert cats(rec3, 'project_only')['bb__bb-1'] == 'UNKNOWN'
    assert rec3['derivative_record_whitelist'][audit]['accepted'] is False


def test_record_hash_mismatch_is_marked_not_silent(tmp_path):
    rec = run(make_toy(tmp_path, tamper_record=True))
    rows = {r['instance_id']: r for r in rec['rows']}
    assert rows['aa__aa-1']['runtime_gate']['status'] == 'UNKNOWN'
    assert rows['bb__bb-1']['runtime_gate']['status'] == 'fail'
    assert cats(rec, 'conservative') == EXPECTED['conservative']        # exposure categories do not depend on it
    assert any(c['check'] == 'pilot_frame_record_sha256_match_disk' and not c['ok'] for c in rec['consistency_checks'])
    assert {u['affects'] for u in rec['unknowns']} == {'runtime_gate'}


def test_source_pin_mismatch_makes_counts_unknown(tmp_path):
    rec = run(make_toy(tmp_path), source_sha256='0' * 64)
    assert rec['pins']['pins_reconciled'] is False
    for d in ('conservative', 'project_only'):
        assert rec['counts'][d]['not_yet_assessed'] == 'UNKNOWN'
        assert cats(rec, d)['aa__aa-1'] == 'model_outcome_exposed'


@pytest.mark.parametrize('override, failing', [
    (dict(dataset_sha256='f' * 64), {'download_audit', 'm01_summary', 'qual_legacy', 'pilot_frame'}),
    (dict(evaluator_commit='f' * 40), {'evaluator_selection', 'm01_summary', 'qual_legacy', 'pilot_frame'}),
    (dict(dataset_revision='f' * 40), {'download_audit', 'evaluator_selection'}),
])
def test_dataset_or_evaluator_pin_mismatch_makes_counts_unknown(tmp_path, override, failing):
    rec = run(make_toy(tmp_path), **override)
    assert rec['pins']['pins_reconciled'] is False
    assert {x['artifact'] for x in rec['pins']['pin_chain'] if not x['ok']} == {M.P[k] for k in failing}
    for d in ('conservative', 'project_only'):
        assert [rec['counts'][d][k] for k in M.CATEGORIES] == ['UNKNOWN'] * 5
        assert cats(rec, d)['aa__aa-1'] == 'model_outcome_exposed' and cats(rec, d)['dd__dd-1'] == 'UNKNOWN'
    assert {u['artifact'] for u in rec['unknowns'] if u['scope'] == 'global'} == {M.P[k] for k in failing}


def test_missing_pin_artifact_makes_counts_unknown(tmp_path):
    root = make_toy(tmp_path)
    (root / M.P['download_audit']).unlink()
    rec = run(root)
    assert rec['pins']['pins_reconciled'] is False
    assert [x['artifact'] for x in rec['pins']['pin_chain'] if not x['ok']] == [M.P['download_audit']]
    assert rec['counts']['project_only']['not_yet_assessed'] == 'UNKNOWN'


def test_local_parquet_that_does_not_match_the_pin_makes_counts_unknown(tmp_path):
    rec = run(make_toy(tmp_path, extra_files={M.DATASET_PARQUET: b'PAR1 not a real parquet PAR1'}))
    assert rec['local_dataset_parquet']['present'] is True
    assert rec['local_dataset_parquet']['id_reconciliation']['status'] == 'not_verified'
    assert [x['artifact'] for x in rec['pins']['pin_chain'] if not x['ok']] == [M.DATASET_PARQUET]
    assert rec['counts']['conservative']['not_yet_assessed'] == 'UNKNOWN'


# ------------------------------------------------------------------ cohort manifest entries (R5)
def test_skipped_completed_retained_incomplete_and_unconfirmed_runs_count_as_exposure(tmp_path):
    skip_dir, part_dir, unconf = 'aa__aa-2__small__pilot-x__T7', 'dd__dd-1__large__pilot-x__T8', 'cc__cc-3__small__pilot-x__T9'
    root = make_toy(tmp_path, dev1_extra=dict(
        skipped_completed=[dict(instance_id='aa__aa-2', backend='small', run_id=skip_dir, episode_sha256='0' * 64)],
        retained_incomplete=[dict(instance_id='dd__dd-1', backend='large', run_dirs=[part_dir])],
        unconfirmed_container_runs=[unconf]),
        extra_files={DEV1 + '/%s/episode.json' % skip_dir: '{}', DEV1 + '/%s/partial.log' % part_dir: 'x',
                     DEV1 + '/%s/partial.log' % unconf: 'x'})
    rec = run(root)
    assert [u for u in rec['unknowns'] if u['affects'] == 'category'] == []
    for d in ('conservative', 'project_only'):
        for iid in ('aa__aa-2', 'dd__dd-1', 'cc__cc-3'):
            assert cats(rec, d)[iid] == 'model_outcome_exposed'
    rows = {r['instance_id']: r for r in rec['rows']}
    assert DEV1 + '/block_1.json#skipped_completed' in rows['aa__aa-2']['touches']['model_outcome_episode']
    assert DEV1 + '/%s/' % part_dir in rows['dd__dd-1']['touches']['model_outcome_episode']
    assert rec['counts']['project_only']['model_outcome_exposed'] == 5


def test_unattributable_unconfirmed_episode_pids_make_counts_unknown(tmp_path):
    rec = run(make_toy(tmp_path, dev2_extra=dict(unconfirmed_episode_pids=[4242])))
    assert rec['counts']['project_only']['not_yet_assessed'] == 'UNKNOWN'
    assert any(u['scope'] == 'global' and u['artifact'] == DEV2 + '/block_1.json' for u in rec['unknowns'])


# ------------------------------------------------------------------ required checks (R008-05, R3, R8)
def test_required_checks_are_scoped_for_both_definitions(tmp_path):
    rec = run(make_toy(tmp_path))
    req = rec['required_before_eligibility']
    assert '(5 IDs)' in req['status_rule']      # aa__aa-2, bb__bb-2, cc__cc-2, cc__cc-3, dd__dd-1 are runtime-untested
    sc = req['scope']
    assert sc['conservative']['not_yet_assessed']['empty_pass_to_pass_ids'] == []
    assert sc['project_only']['not_yet_assessed']['empty_pass_to_pass_ids'] == []
    assert sc['project_only']['unexposed_runtime_untested']['empty_pass_to_pass_ids'] == ['bb__bb-2']
    assert (sc['conservative']['not_yet_assessed']['n_env_images'], sc['project_only']['not_yet_assessed']['n_env_images']) == (2, 2)
    assert sc['conservative']['unexposed_runtime_untested']['n_ids'] == 4
    assert sc['project_only']['unexposed_runtime_untested']['n_ids'] == 5
    assert sc['all_runtime_untested']['n_ids'] == 5
    keys = [c['key'] for c in req['checks']]
    for k in ('image_build_and_digest_pin', 'host_verification_record', 'isolated_workers_network_and_credentials',
              'control_rules', 'acceptance_record_schema', 'empty_pass_to_pass_limitation_declaration',
              'near_duplicate_family_variant_screen') + ACC_KEYS:
        assert k in keys
    img = [c for c in req['checks'] if c['key'] == 'image_build_and_digest_pin'][0]
    assert img['scope_counts']['project_only']['not_yet_assessed']['n_instance_images'] == 2
    assert img['scope_counts']['project_only']['unexposed_runtime_untested']['n_instance_images'] == 5
    assert any(M.P['runbook'] in s for s in img['sources'])
    assert not any(r['metadata_gate'].get('qualified') for r in rec['rows'])


# ------------------------------------------------------------------ uncommitted evidence (R7)
def test_uncommitted_smoke_logs_are_reconciled_by_metadata(tmp_path):
    root = make_toy(tmp_path, extra_files={'work/runs/agent_smoke_small.stdout': 'x', 'work/runs/agent_smoke_large.stdout': 'x',
                                           'work/llama_small.log': 'x'})
    rec = run(root)
    sr = rec['uncommitted_local_evidence']['smoke_stdout_reconciliation']
    assert (sr['n_stdout_logs'], sr['n_committed_smoke_episode_dirs'], sr['consistent_with_committed_smoke_episodes']) == (2, 2, True)
    assert any('attributed by metadata only' in x for x in rec['headline_caveats'])
    sl = rec['uncommitted_local_evidence']['server_logs']
    assert sl['paths'] == ['work/llama_small.log'] and sl['smoke_episode_ids'] == ['cc__cc-1']
    assert sl['attribution']['attribution'].startswith('The server logs were not opened')
    root2 = make_toy(tmp_path / 'b', extra_files={'work/runs/agent_smoke_%d.stdout' % k: 'x' for k in range(3)})
    rec2 = run(root2)
    assert rec2['uncommitted_local_evidence']['smoke_stdout_reconciliation']['consistent_with_committed_smoke_episodes'] is False
    assert any(x.startswith('CAVEAT') for x in rec2['headline_caveats'])


def test_uncommitted_logs_after_the_smoke_commit_are_not_reconciled(tmp_path):
    root = make_toy(tmp_path, extra_files={'.gitignore': 'work/\n'})
    git(root, 'init', '-q')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'toy')
    future = time.time() + 86400
    for b in ('small', 'large'):
        put(root, 'work/runs/agent_smoke_%s.stdout' % b, 'x')
        os.utime(root / ('work/runs/agent_smoke_%s.stdout' % b), (future, future))
    sr = run(root)['uncommitted_local_evidence']['smoke_stdout_reconciliation']
    assert sr['count_match'] is True and sr['all_stdout_mtimes_at_or_before_that_commit'] is False
    assert sr['consistent_with_committed_smoke_episodes'] is False


def test_uncommitted_id_paths_raise_unknown_only_outside_mapped_roots(tmp_path):
    rec = run(make_toy(tmp_path, extra_files={
        'work/runs/pilot_20260922/raw/aa__aa-1__small__pilot-x__T0/x.log': 'x',
        'work/runs/qualification_20260922/logs/bb__bb-1/run.log': 'x',
        'work/runs/elsewhere/bb__bb-2__small/x.log': 'x'}))
    assert cats(rec, 'conservative') == EXPECTED['conservative']       # bb__bb-2 is exposed under conservative
    assert cats(rec, 'project_only') == dict(EXPECTED['project_only'], **{'bb__bb-2': 'UNKNOWN'})
    assert [u['definitions'] for u in rec['unknowns']] == [['project_only']]


# ------------------------------------------------------------------ aborts
def test_abort_on_evidence_id_outside_the_frame(tmp_path):
    root = make_toy(tmp_path, extra_ran=[dict(instance_id='zz__zz-9', backend='small', run_id='zz__zz-9__small__x')])
    with pytest.raises(M.InventoryAbort, match='zz__zz-9'):
        run(root)
    root2 = make_toy(tmp_path / 'b', extra_files={M.P['cue_registry']: "COHORT = 'c'\nCOHORTS = {COHORT: 'x'}\n"
                                                                        "TASKS = ('ee__ee-5',)\n"})
    with pytest.raises(M.InventoryAbort, match='ee__ee-5'):
        run(root2)
    root3 = make_toy(tmp_path / 'c', dev1_extra=dict(skipped_completed=[dict(instance_id='ff__ff-1', run_id='ff__ff-1__s')]))
    with pytest.raises(M.InventoryAbort, match='ff__ff-1'):
        run(root3)


def test_abort_when_qualification_ids_do_not_reconcile(tmp_path):
    with pytest.raises(M.InventoryAbort, match='planned_new'):
        run(make_toy(tmp_path, drop_planned='bb__bb-1'))


def test_abort_on_duplicate_or_missing_rows(tmp_path):
    root = make_toy(tmp_path)
    p = root / M.P['m01_instances']
    lines = p.read_text().splitlines(keepends=True)
    p.write_text(''.join(lines + lines[:1]))
    with pytest.raises(M.InventoryAbort):
        run(root)


# ------------------------------------------------------------------ stdlib parquet reader
def test_snappy_and_rle_hand_vectors():
    # length 11; literal 'abc' (tag (3-1)<<2); copy-1 of length 8 at offset 3 (tag ((8-4)<<2)|1, offset byte 3)
    assert M.snappy_decompress(bytes([11, 0x08]) + b'abc' + bytes([0x11, 0x03])) == b'abcabcabcab'
    # RLE run of three 0s (header 3<<1), then one bit-packed group (header 1<<1|1) of byte 0b10110101, LSB first
    vals, _ = M.rle_bitpacked_hybrid(bytes([0x06, 0x00, 0x03, 0b10110101]), 0, 1, 10)
    assert vals == [0, 0, 0, 1, 0, 1, 0, 1, 1, 0]


PARQUET = ROOT / M.DATASET_PARQUET
# Constants from an independent pyarrow 25.0.1 read of the pinned parquet (work/venvs/swebench_f7bbbb2), each list
# serialized as values joined by "\n" with a trailing "\n" in file order.
PYARROW_ORDERED = dict(instance_id='a6b0fd7c8c2969a0eef892e032250adcfa6d32362d395c246930e61b575ac9b9',
                       repo='e6490579ccd1ec9f990aff81b732fecb144a106585cd5412b0e4679e92e9de3c',
                       version='c493dda5bc0791d4490415ba637548e740765ea78630ab650ef8f624db779f45')


@pytest.mark.skipif(not PARQUET.exists(), reason='pinned local parquet (git-ignored) not present')
def test_stdlib_parquet_reader_matches_independent_pyarrow_read():
    n, cols = M.read_parquet_columns(PARQUET.read_bytes(), ('instance_id', 'repo', 'version'))
    assert n == 500
    for k, want in PYARROW_ORDERED.items():
        assert sha(''.join(v + '\n' for v in cols[k])) == want, k
