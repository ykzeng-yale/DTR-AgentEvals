"""No-runtime regressions for keeping legacy and repaired evidence separate."""
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import pilot_cohort as PC
import pilot_episode as PE
import pilot_runner as PR


def receipt_fixture(directory):
    args = {k: {'fixture': k} for k in ('agent', 'model', 'environment')}
    receipt = PE.effective_config_receipt(args, args)
    (directory / 'effective_config.json').write_text(json.dumps(receipt))
    return dict(configuration_binding='yaml-v1', effective_config_file='effective_config.json',
                effective_config_sha256=receipt['effective_config_sha256'],
                episode_source_sha256=receipt['episode_source_sha256'],
                pins=dict(mini_swe_agent=PE.MINI_SWE_AGENT_PIN, default_yaml_sha256=PE.DEFAULT_YAML_SHA))


def test_legacy_results_cannot_complete_corrected_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, 'ROOT', tmp_path)
    item = dict(instance_id='task', backend='small', image='sha256:test')
    old = PC.cohort_output('legacy') / 'task__small__original'
    old.mkdir(parents=True)
    (old / 'episode.json').write_text(json.dumps(dict(instance_id='task', backend='small', run_id=old.name,
                                                       exit_status='Submitted', physical_requests=1)))
    assert PR.episode_state(PC.cohort_output('legacy'), item)[0] == 'completed'
    assert PR.episode_state(PC.cohort_output('yaml-v1'), item)[0] == 'new'


@pytest.mark.parametrize('damage', ['binding', 'missing', 'digest', 'source', 'resolved', 'frozen_source'])
def test_resume_rejects_missing_corrupted_or_different_effective_config(tmp_path, damage):
    rec = receipt_fixture(tmp_path)
    assert PC.validate_effective_receipt(tmp_path, rec, 'yaml-v1')['configuration_binding'] == 'yaml-v1'
    expected = None
    if damage == 'binding':
        rec['configuration_binding'] = 'legacy'
    elif damage == 'missing':
        (tmp_path / 'effective_config.json').unlink()
    elif damage == 'digest':
        rec['effective_config_sha256'] = '0' * 64
    elif damage == 'source':
        rec['episode_source_sha256'] = '0' * 64
    elif damage == 'frozen_source':
        expected = '0' * 64
    else:
        receipt = json.loads((tmp_path / 'effective_config.json').read_text())
        receipt['resolved']['model']['fixture'] = 'silently ignored constructor'
        (tmp_path / 'effective_config.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        PC.validate_effective_receipt(tmp_path, rec, 'yaml-v1', expected)


def test_runtime_legacy_refused_before_any_dispatch(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['pilot_runner.py', '--cohort', 'legacy', '--block', '2'])
    monkeypatch.setattr(PR, 'Servers', lambda *args: pytest.fail('runtime attempted'))
    with pytest.raises(SystemExit) as err:
        PR.main()
    assert err.value.code == 2


def test_source_freeze_is_write_once_and_rejects_amendment_change(tmp_path, monkeypatch):
    amendment = tmp_path / 'amendment.json'
    amendment.write_text('{}')
    monkeypatch.setattr(PC, 'AMENDMENT', amendment)
    out = tmp_path / 'out'
    out.mkdir()
    first = PC.freeze_source_binding(out)
    assert PC.freeze_source_binding(out) == first
    saved = (out / 'cohort_binding.json').read_bytes()
    amendment.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='changed'):
        PC.freeze_source_binding(out)
    assert (out / 'cohort_binding.json').read_bytes() == saved


def test_existing_corrected_records_without_source_freeze_refuse(tmp_path):
    (tmp_path / 'old_record.json').write_text('{}')
    with pytest.raises(ValueError, match='nonempty'):
        PC.freeze_source_binding(tmp_path)


def test_unstarted_report_does_not_block_first_source_freeze(tmp_path):
    path = tmp_path / 'report_before_start.json'
    path.write_text(json.dumps(dict(cohort='yaml-v1', terminal=0, episodes=[dict(state='unstarted')])))
    saved = path.read_bytes()
    PC.freeze_source_binding(tmp_path)
    assert path.read_bytes() == saved
