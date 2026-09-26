"""DTR-REQ-022 focused pre-run tests (lead cd90c56): null-control cell binding, policy truth against the exact kernel,
exact-SD agreement with the accepted artifacts, deterministic replay, manifest-hash refusal and the blocked-gate path.
Expected values are the committed accepted artifacts' literal numbers, never recomputed with the code under test."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_sim'))
import null_control_batch as N  # noqa: E402


def test_cell_binding_is_the_exact_null():
    kc = N.kernel_cell()
    assert (kc['K'], kc['action_effect'], kc['feedback']) == (2, 'no_crossing', 'informative')
    assert kc['best_fixed']['policy'] == 'fixed_LL' and kc['best_fixed']['utility']['exact'] == '2891/4000'
    assert kc['best_prompt_only_utility']['exact'] == kc['best_observed_history_utility']['exact'] == '2891/4000'
    assert kc['history_advantage_over_best_fixed']['exact'] == kc['history_advantage_over_best_prompt_only']['exact'] == '0'
    assert N.CELL['logger'] == 'feedback_dependent_floor_0.2' and N.ROOT_SEED not in N.PREVIOUS_SEEDS


def test_policy_truths_and_exact_sds_match_the_accepted_artifacts():
    ex = N.exact_references()
    truths = {'fixed_SS': '1473609/2500000', 'fixed_SL': '817701/1250000', 'fixed_LS': '343903/500000',
              'fixed_LL': '2891/4000', 'prompt_only_large_if_hard': '1721033/2500000',
              'history_large_after_exception': '870416349/1250000000', 'history_S_or_exception': '890352733/1250000000'}
    assert {k: v['truth_exact'] for k, v in ex.items()} == truths          # repair_generator_v1.json literals
    # fixed_task_blocks_v1.json / fresh_reference_v1.json (n = 250, r = 4) literals for the three accepted policies
    assert ex['fixed_LL']['exact_sd_ipw'] == pytest.approx(0.04074915549232278, abs=1e-15)
    assert ex['prompt_only_large_if_hard']['exact_sd_ipw'] == pytest.approx(0.033399244466874096, abs=1e-15)
    assert ex['history_large_after_exception']['exact_sd_ipw'] == pytest.approx(0.017112068538279908, abs=1e-15)
    assert ex['fixed_LL']['exact_sd_fresh'] == pytest.approx(0.013201374678418911, abs=1e-15)
    assert ex['history_large_after_exception']['exact_sd_fresh'] == pytest.approx(0.013722451505754688, abs=1e-15)


def test_deterministic_replay_and_distinct_repetitions():
    a, b, c = N.job(3), N.job(3), N.job(4)
    assert a['policies'] == b['policies'] and a['namespace'] == b['namespace']
    assert a['policies'] != c['policies']
    assert a['log_episodes'] == 250 * 4 and all(p['fresh_episodes'] == 250 * 4 for p in a['policies'].values())


def test_manifest_hash_refusal_and_no_overwrite(tmp_path):
    out = tmp_path / 'run'
    N.freeze(out)
    with pytest.raises(SystemExit, match='already frozen'):
        N.freeze(out)
    m = json.loads((out / 'manifest.json').read_text())
    m['source_sha256']['experiments/v2_sim/sampler.py'] = '0' * 64
    (out / 'manifest.json').write_text(json.dumps(m))
    with pytest.raises(SystemExit, match='files changed since the manifest was frozen'):
        N.run(out, gates=dict(passed=True, checks={}, measured_utc='x'))
    assert not (out / 'reps.jsonl').exists()


def test_failed_gate_blocks_without_sampling(tmp_path):
    out = tmp_path / 'run'
    N.freeze(out)
    with pytest.raises(SystemExit, match='BLOCKED'):
        N.run(out, gates=dict(passed=False, checks=dict(memory=False), measured_utc='x'))
    assert json.loads((out / 'run_status.json').read_text())['status'] == 'BLOCKED'
    assert not (out / 'reps.jsonl').exists()
