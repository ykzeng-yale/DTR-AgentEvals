"""Publication-only provenance fixtures; no runtime, model, or archive writes."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import pilot_cohort as PC
import pilot_report as RP
from publication_manifest import canonical_sha256, sha256

SOURCE = 'a' * 64
FRAME = dict(pilot=dict(tasks=[dict(position=1, instance_id='fixture__1', backend_order=['small', 'large'])]))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=1) + '\n')


@pytest.fixture
def published(tmp_path):
    directory = tmp_path / 'fixture__1__small__pilot-cp2-wc2-yaml-v1__fixture'
    directory.mkdir()
    args = {section: dict(fixture=section) for section in ('agent', 'model', 'environment')}
    args['environment']['executable'] = '/Users/fixture/bin/docker'
    receipt = dict(configuration_binding='yaml-v1', episode_source_sha256=SOURCE,
                   mini_swe_agent='mini-pin', default_yaml_sha256='yaml-pin',
                   constructor_arguments=args, resolved=args)
    recorded = canonical_sha256(receipt)
    receipt['effective_config_sha256'] = recorded
    write_json(directory / 'effective_config.json', receipt)
    episode = dict(instance_id='fixture__1', backend='small', run_id=directory.name, exit_status='LimitsExceeded',
                   submission_sha256=sha256(b''), n_model_calls=1, configuration_binding='yaml-v1',
                   episode_source_sha256=SOURCE, effective_config_file='effective_config.json',
                   effective_config_sha256=recorded, pins=dict(mini_swe_agent='mini-pin', default_yaml_sha256='yaml-pin'))
    write_json(directory / 'episode.json', episode)
    (directory / 'submission.diff').write_bytes(b'')
    # The original execution receipt validates before the publication-only substitution.
    PC.validate_effective_receipt(directory, episode, 'yaml-v1', SOURCE)
    raw = (directory / 'effective_config.json').read_bytes()
    (directory / 'effective_config.json').write_bytes(raw.replace(b'/Users/fixture', b'~'))
    published_receipt = RP.read_json(directory / 'effective_config.json')
    manifest = dict(files=[dict(file=directory.name + '/effective_config.json', raw_sha256=sha256(raw),
                               published_sha256=sha256((directory / 'effective_config.json').read_bytes()),
                               recorded_effective_config_sha256=recorded,
                               published_payload_canonical_sha256=canonical_sha256(
                                   {k: v for k, v in published_receipt.items() if k != 'effective_config_sha256'}))])
    path = tmp_path / 'publication.json'
    write_json(path, manifest)
    return tmp_path, directory, path


def report(fixture, **kwargs):
    archive, _, manifest = fixture
    return RP.report(FRAME, archive, expected_binding='yaml-v1', expected_source=SOURCE,
                     publication_manifest=manifest, **kwargs)


def refresh_published_hashes(manifest_path, receipt_path):
    manifest = RP.read_json(manifest_path)
    receipt = RP.read_json(receipt_path)
    entry = manifest['files'][0]
    entry['published_sha256'] = sha256(receipt_path.read_bytes())
    entry['published_payload_canonical_sha256'] = canonical_sha256(
        {k: v for k, v in receipt.items() if k != 'effective_config_sha256'})
    write_json(manifest_path, manifest)


def test_projection_status_never_becomes_execution_validation_and_preserves_archives(published):
    archive, directory, manifest = published
    before = {p: p.read_bytes() for p in archive.rglob('*') if p.is_file()}
    strict = RP.report(FRAME, archive, expected_binding='yaml-v1', expected_source=SOURCE)
    assert strict['configuration_provenance']['terminal_status_counts'] == {'invalid': 1}
    assert 'publication_provenance' not in strict
    with pytest.raises(ValueError, match='digest/provenance'):
        PC.validate_effective_receipt(directory, RP.read_json(directory / 'episode.json'), 'yaml-v1', SOURCE)
    projected = report(published)
    row = projected['episodes'][0]
    assert projected['assigned'] == 2 and projected['terminal'] == 1
    assert row['configuration_provenance_status'] == 'published_projection_verified'
    assert projected['configuration_provenance']['terminal_status_counts'] == {'published_projection_verified': 1}
    for evidence in (row['configuration_provenance'], projected['publication_provenance']):
        assert evidence['raw_execution_binding'] == 'reported_unverified'
        assert evidence['raw_bytes_independently_verified'] is False
        assert evidence['sanitization_transform_independently_verified'] is False
    assert projected['publication_provenance']['manifest_sha256'] == sha256(manifest.read_bytes())
    assert projected['backends'] == strict['backends'] and projected['paired'] == strict['paired']
    assert before == {p: p.read_bytes() for p in archive.rglob('*') if p.is_file()}


@pytest.mark.parametrize('damage', ['missing', 'invalid_json', 'not_object', 'empty', 'duplicate', 'byte_hash',
                                 'canonical_hash', 'recorded_hash', 'missing_raw_hash', 'missing_published_file'])
def test_bad_manifest_or_published_file_refuses_report(published, damage):
    _, directory, path = published
    manifest = RP.read_json(path)
    if damage == 'missing':
        path.unlink()
    elif damage == 'invalid_json':
        path.write_text('{')
    elif damage == 'not_object':
        write_json(path, [])
    elif damage == 'missing_published_file':
        (directory / 'effective_config.json').unlink()
    else:
        if damage == 'empty':
            manifest['files'] = []
        elif damage == 'duplicate':
            manifest['files'] *= 2
        elif damage == 'missing_raw_hash':
            manifest['files'][0].pop('raw_sha256')
        else:
            field = dict(byte_hash='published_sha256', canonical_hash='published_payload_canonical_sha256',
                         recorded_hash='recorded_effective_config_sha256')[damage]
            manifest['files'][0][field] = 'b' * 64
        write_json(path, manifest)
    with pytest.raises(RP.ReportIntegrityError, match='publication manifest refused'):
        report(published)


@pytest.mark.parametrize('path', ['../effective_config.json', '/effective_config.json', './effective_config.json',
                                'x/../effective_config.json', 'x//effective_config.json', 'x\\effective_config.json'])
def test_manifest_paths_must_be_canonical_and_relative(published, path):
    manifest = RP.read_json(published[2])
    manifest['files'][0]['file'] = path
    write_json(published[2], manifest)
    with pytest.raises(RP.ReportIntegrityError, match='manifest-relative path'):
        report(published)


def test_manifest_symlink_escape_and_resolved_duplicate_are_refused(published, tmp_path):
    archive, directory, path = published
    manifest = RP.read_json(path)
    original = json.loads(json.dumps(manifest))
    # An escape is rejected before reading the target; no external file is needed.
    (archive / 'escape').symlink_to(archive.parent / 'outside.json')
    manifest['files'][0]['file'] = 'escape'
    write_json(path, manifest)
    with pytest.raises(RP.ReportIntegrityError, match='escapes archive'):
        report(published)
    (archive / 'alias').symlink_to(directory / 'effective_config.json')
    original['files'].append(dict(original['files'][0], file='alias'))
    write_json(path, original)
    with pytest.raises(RP.ReportIntegrityError, match='duplicate publication'):
        report(published)


@pytest.mark.parametrize('target,field,value', [
    ('episode', 'effective_config_sha256', 'b' * 64), ('episode', 'episode_source_sha256', 'b' * 64),
    ('episode', 'configuration_binding', 'legacy'), ('episode', 'effective_config_file', 'other.json'),
    ('receipt', 'episode_source_sha256', 'b' * 64), ('receipt', 'configuration_binding', 'legacy'),
    ('receipt', 'mini_swe_agent', 'wrong-pin'), ('receipt', 'default_yaml_sha256', 'wrong-pin'),
])
def test_projection_links_are_required_even_when_manifest_hashes_match(published, target, field, value):
    _, directory, manifest = published
    path = directory / ('episode.json' if target == 'episode' else 'effective_config.json')
    record = RP.read_json(path)
    record[field] = value
    write_json(path, record)
    if target == 'receipt':
        refresh_published_hashes(manifest, path)
    result = report(published)
    assert result['assigned'] == 2 and result['terminal'] == 1
    row = result['episodes'][0]
    assert row['configuration_provenance_status'] == 'invalid'
    assert 'link mismatch' in row['configuration_provenance']['reason']


def test_manifest_omission_does_not_validate_unlisted_configuration(published):
    archive, directory, path = published
    (archive / 'other.txt').write_text('fixture')
    write_json(path, dict(files=[dict(file='other.txt', published_sha256=sha256(b'fixture'), raw_sha256=sha256(b'fixture'))]))
    result = report(published)
    assert result['episodes'][0]['configuration_provenance_status'] == 'invalid'
    assert 'missing from publication manifest' in result['episodes'][0]['configuration_provenance']['reason']


@pytest.mark.parametrize('binding,source', [(None, SOURCE), ('yaml-v1', None)])
def test_projection_mode_requires_frozen_cohort_identity(published, binding, source):
    with pytest.raises(RP.ReportIntegrityError, match='requires expected cohort'):
        RP.report(FRAME, published[0], expected_binding=binding, expected_source=source, publication_manifest=published[2])


def test_publication_cli_is_explicit_write_once_and_does_not_change_default(published, monkeypatch):
    archive, _, manifest = published
    monkeypatch.setattr(PC, 'cohort_output', lambda name: archive)
    monkeypatch.setattr(RP, 'FRAME', archive / 'frame.json')
    write_json(RP.FRAME, FRAME)
    monkeypatch.setattr(RP, 'cohort_metadata', lambda *a: dict(expected_episode_source_sha256=SOURCE))
    RP.main(['strict', '--cohort', 'yaml-v1'])
    RP.main(['projection', '--cohort', 'yaml-v1', '--publication-manifest', str(manifest)])
    assert RP.read_json(archive / 'report_strict.json')['episodes'][0]['configuration_provenance_status'] == 'invalid'
    projected = archive / 'report_projection.json'
    before = projected.read_bytes()
    assert RP.read_json(projected)['episodes'][0]['configuration_provenance_status'] == 'published_projection_verified'
    with pytest.raises(FileExistsError):
        RP.main(['projection', '--cohort', 'yaml-v1', '--publication-manifest', str(manifest)])
    assert projected.read_bytes() == before
