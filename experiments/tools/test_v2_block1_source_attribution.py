"""Read-only retrospective attribution fixtures; no process or filesystem-birthtime probes."""
import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import block1_source_attribution as BA


def fixture(archive):
    name = 'task__1__small__pilot-cp2-wc2__20260922T053355Z-abcdef'
    directory = archive / name
    directory.mkdir(parents=True)
    patch = b'fixture diff\n'
    sha = hashlib.sha256(patch).hexdigest()
    ep = dict(instance_id='task__1', backend='small', run_id=name, submission_sha256=sha)
    (directory / 'episode.json').write_text(json.dumps(ep))
    (directory / 'attempts.jsonl').write_text(json.dumps(dict(call=1, attempt=1, ok=True)) + '\n')
    (directory / 'submission.diff').write_bytes(patch)
    (directory / 'grade.json').write_text(json.dumps(dict(instance_id='task__1', backend='small', episode_run_id=name,
                                                          submission_sha256=sha)))
    return dict(replacement_interval_utc=['2026-09-22T05:33:50Z', '2026-09-22T05:34:13Z'],
                episodes=[dict(run_id=name, instance_id='task__1', backend='small', ledger_records=1, ledger_has_event_key=False,
                               spawn_utc_runner_stdout_birth='2026-09-22T05:33:49Z', run_id_timestamp='pilot-cp2-wc2')],
                identity_binding=dict(published_equals_raw=[name + '/episode.json', 'later_derived_report.json'],
                                      published_differs_from_raw={}))


def test_timestamp_parser_uses_final_segment_and_checks_calendar():
    assert BA.run_id_timestamp('sympy__sympy-11618__large__pilot-cp2-wc2__20260922T053340Z-fa1672') == (
        '20260922T053340Z', '2026-09-22T05:33:40Z')
    for value in ('task__pilot-cp2-wc2', 'task__20261322T053340Z-fa1672', 'task__20260922T053340Z-nothex'):
        with pytest.raises(ValueError):
            BA.run_id_timestamp(value)


def test_correction_separates_recorded_time_worker_claim_and_raw_comparison(tmp_path):
    original = fixture(tmp_path)
    before = copy.deepcopy(original)
    corrected = BA.correct_saved_attribution(original, tmp_path, 'fixture-source-hash')
    row = corrected['episodes'][0]
    assert row['run_id_timestamp'] == '20260922T053355Z'
    assert row['run_id_timestamp_inside_reported_replacement_interval'] is True
    assert row['worker_reported_stdout_file_birth_inside_interval'] is False
    assert 'spawned_inside_replacement_interval' not in row and 'spawn_utc_runner_stdout_birth' not in row
    identity = corrected['identity_binding']
    assert 'later_derived_report.json' in identity['files_not_listed_for_sanitization']
    assert 'later_derived_report.json' not in identity['worker_reported_unchanged_episode_artifact_paths']
    assert identity['raw_bytes_independently_compared'] is False
    assert identity['sanitization_transform_independently_verified'] is False
    assert 'Conditional on' in corrected['evidence_boundary']['source_inference']
    assert 'not exact executed-byte attribution' in corrected['evidence_boundary']['source_inference']
    assert original == before


def test_new_schema_and_tampered_grade_are_visible_not_silently_attributed(tmp_path):
    original = fixture(tmp_path)
    directory = tmp_path / original['episodes'][0]['run_id']
    (directory / 'container_ownership.json').write_text('{}')
    grade = json.loads((directory / 'grade.json').read_text())
    grade['submission_sha256'] = 'wrong'
    (directory / 'grade.json').write_text(json.dumps(grade))
    row = BA.correct_saved_attribution(original, tmp_path, 'fixture')['episodes'][0]
    assert row['consistent_with_11a7344_child_schema'] is False
    assert row['a64d81e_only_files_present'] == ['container_ownership.json']
    assert row['submission_hash_matches'] is True and row['grade_identity_matches'] is False


def test_correction_refuses_missing_or_duplicate_archive_assignments(tmp_path):
    original = fixture(tmp_path)
    original['episodes'].append(copy.deepcopy(original['episodes'][0]))
    with pytest.raises(ValueError, match='episode IDs'):
        BA.correct_saved_attribution(original, tmp_path, 'fixture')
    original['episodes'] = []
    with pytest.raises(ValueError, match='episode IDs'):
        BA.correct_saved_attribution(original, tmp_path, 'fixture')


def test_correction_cli_is_additive_write_once_and_preserves_source(tmp_path):
    archive = tmp_path / 'archive'
    original = fixture(archive)
    source = tmp_path / 'source.json'
    source.write_text(json.dumps(original))
    before = source.read_bytes()
    out = tmp_path / 'correction.json'
    args = ['--archive', str(archive), '--source-attribution', str(source), '--out', str(out)]
    BA.main(args)
    assert json.loads(out.read_text())['original_attribution_sha256'] == hashlib.sha256(before).hexdigest()
    assert source.read_bytes() == before
    with pytest.raises(FileExistsError):
        BA.main(args)
    with pytest.raises(ValueError, match='must not overwrite'):
        BA.main(['--archive', str(archive), '--source-attribution', str(source), '--out', str(source)])
    assert source.read_bytes() == before


def test_published_16_episode_archive_reproduces_schema_and_identity_checks():
    before = BA.SOURCE.read_bytes()
    corrected = BA.correct_saved_attribution(json.loads(before), BA.OUT, hashlib.sha256(before).hexdigest())
    assert corrected['all_16_consistent_with_11a7344_child_schema'] is True
    assert len(corrected['episodes']) == 16
    assert corrected['run_ids_timestamped_inside_reported_interval'] == []
    assert corrected['worker_reported_stdout_births_inside_interval'] == []
    assert all(row['episode_run_id_matches'] and row['submission_hash_matches'] and row['grade_identity_matches']
               for row in corrected['episodes'])
    assert len(corrected['identity_binding']['worker_reported_unchanged_episode_artifact_paths']) == 64
    assert BA.SOURCE.read_bytes() == before
