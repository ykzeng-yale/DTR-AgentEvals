"""Binding v3 fixture (block-1 finding 98895fe): the episode must apply the pinned default.yaml `model` and
`environment` sections, not only `agent`. Expected values are the pinned yaml's own values (parsed by the pinned
mini-swe-agent venv when present) plus hand-written serving kwargs; nothing is recomputed with the helper's logic."""
import json, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))
import pilot_episode as PE  # noqa: E402

YAML = ROOT / 'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent/config/default.yaml'
MSWEA_PY = ROOT / 'work/venvs/minisweagent_04d809c/bin/python'


def test_model_and_environment_sections_are_applied_with_serving_kwargs_layered_on_top():
    cfg = dict(agent=dict(step_limit=0), environment=dict(env=dict(PAGER='cat', MANPAGER='cat', LESS='-R', PIP_PROGRESS_BAR='off', TQDM_DISABLE='1')),
               model=dict(observation_template='OBS {{output.output[:10]}}', format_error_template='FMT', model_kwargs=dict(drop_params=True)))
    model_cfg, kwargs, env = PE.yaml_bindings(cfg, 8293, 900)
    assert model_cfg == dict(observation_template='OBS {{output.output[:10]}}', format_error_template='FMT')
    assert kwargs == dict(drop_params=True, api_base='http://127.0.0.1:8293/v1', api_key='none', temperature=0.0, max_tokens=1536,
                          timeout=900, num_retries=0)
    assert env == dict(PAGER='cat', MANPAGER='cat', LESS='-R', PIP_PROGRESS_BAR='off', TQDM_DISABLE='1')
    assert cfg['model']['model_kwargs'] == dict(drop_params=True)          # the parsed config is not mutated


@pytest.mark.skipif(not (YAML.exists() and MSWEA_PY.exists()), reason='pinned mini-swe-agent checkout/venv not present')
def test_pinned_yaml_yields_truncating_observation_template_and_full_env():
    cfg = json.loads(subprocess.run([str(MSWEA_PY), '-c', 'import yaml,json,sys; print(json.dumps(yaml.safe_load(open(sys.argv[1]))))', str(YAML)],
                                    capture_output=True, text=True, check=True).stdout)
    model_cfg, kwargs, env = PE.yaml_bindings(cfg, 8291, 900)
    assert 'output.output | length < 10000' in model_cfg['observation_template'] and '<output_head>' in model_cfg['observation_template']
    assert model_cfg['format_error_template'] == cfg['model']['format_error_template']
    assert kwargs['drop_params'] is True and kwargs['temperature'] == 0.0 and kwargs['max_tokens'] == 1536
    assert env == {'PAGER': 'cat', 'MANPAGER': 'cat', 'LESS': '-R', 'PIP_PROGRESS_BAR': 'off', 'TQDM_DISABLE': '1'}
