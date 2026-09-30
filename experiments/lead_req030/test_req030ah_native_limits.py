"""Inert native-budget and bootstrap regressions in clean Python processes.

Every child executes authored fixture code with a 10-second parent bound. No model
weights, CUDA, network access or generated commands are used. These checks establish
context classification and repeated bootstrap identity, not hard CUDA deadlines.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = '''
import json, sys, types
from pathlib import Path
from experiments.lead_req030.seaborn_runner_qualification import load_pinned_default_agent
DefaultAgent = load_pinned_default_agent()
from experiments.lead_req030.native_hf_text_adapter import NativeHFTextAdapter, ContextBudgetExceeded
from minisweagent.exceptions import LimitsExceeded

class Tensor:
    transfers = 0
    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]))
    def to(self, device):
        Tensor.transfers += 1
        return self
    def tolist(self):
        return self.rows
    def __getitem__(self, key):
        row, col = key
        return Slice(self.rows[row][col])
class Slice:
    def __init__(self, values): self.values = values
    def tolist(self): return self.values
class Tokenizer:
    eos_token_id = 2
    def __init__(self): self.input_ids = [11, 12, 13]
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False and add_generation_prompt is True
        return '|'.join(m['content'] for m in messages)
    def __call__(self, rendered, *, add_special_tokens, return_tensors):
        assert add_special_tokens is False and return_tensors == 'pt'
        return {'input_ids': Tensor([self.input_ids])}
    def decode(self, ids, *, skip_special_tokens):
        assert skip_special_tokens is False
        return '```mswea_bash_command\\nfixture_observation\\n```'
class Model:
    calls = 0
    def generate(self, *, input_ids, **kwargs):
        self.calls += 1
        return Tensor([input_ids.rows[0] + [42, 2]])
class Environment:
    def __init__(self): self.actions = []
    def get_template_vars(self): return {}
    def serialize(self): return {}
    def execute(self, action):
        assert action == {'command': 'fixture_observation'}
        self.actions.append(action)
        return {'returncode': 0, 'output': 'authored fixture observation'}
def make_adapter(context_limit=64):
    tokenizer, model, events = Tokenizer(), Model(), []
    adapter = NativeHFTextAdapter(
        tokenizer=tokenizer, model=model, model_id='fixture/model', revision='fixture-revision',
        context_limit=context_limit, max_new_tokens=8,
        action_regex=r'```mswea_bash_command\\s*\\n(.*?)\\n```',
        format_error_template='Expected exactly one action',
        observation_template='{{output.output}}', record_event=events.append, device='fixture',
    )
    return adapter, tokenizer, model, events
MESSAGES = [{'role': 'system', 'content': 'frozen'}, {'role': 'user', 'content': 'task'}]
def agent_for(adapter):
    env = Environment()
    agent = DefaultAgent(adapter, env, system_template='frozen', instance_template='{{task}}',
        step_limit=4, cost_limit=0.0, wall_time_limit_seconds=0, output_path=Path('trajectory.json'))
    return agent, env
'''


def run_inert(tmp_path, body, *, harness=HARNESS):
    result = subprocess.run(
        [sys.executable, '-c', harness + '\n' + textwrap.dedent(body)],
        cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(ROOT)},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_exact_context_boundary_permits_one_physical_call(tmp_path):
    run_inert(tmp_path, '''
        adapter, _, model, events = make_adapter(context_limit=11)
        result = adapter.query(MESSAGES)
        assert result['extra']['native_binding']['input_tokens'] == 3
        assert model.calls == adapter.n_calls == 1
        assert [e['event'] for e in events] == ['request', 'response']
    ''')


def test_overflow_is_typed_limit_before_device_transfer_or_generation(tmp_path):
    run_inert(tmp_path, '''
        adapter, _, model, events = make_adapter(context_limit=10)
        try:
            adapter.query(MESSAGES)
        except ContextBudgetExceeded as error:
            assert isinstance(error, LimitsExceeded)
            assert isinstance(error, ValueError)  # compatible direct-call API
            assert str(error) == 'context budget exceeded: 3+8>10'
            assert error.messages[0]['extra'] == {
                'exit_status': 'LimitsExceeded', 'submission': '', 'limit_kind': 'context_tokens',
                'input_tokens': 3, 'max_new_tokens': 8, 'context_limit': 10,
            }
        else:
            raise AssertionError('overflow accepted')
        assert Tensor.transfers == model.calls == adapter.n_calls == 0
        assert events == []
    ''')


def test_pinned_agent_saves_context_exit_without_submission_or_action(tmp_path):
    run_inert(tmp_path, '''
        adapter, _, model, events = make_adapter(context_limit=10)
        agent, env = agent_for(adapter)
        result = agent.run(task='public fixture task')
        assert result['exit_status'] == 'LimitsExceeded'
        assert result['limit_kind'] == 'context_tokens' and result['submission'] == ''
        assert model.calls == adapter.n_calls == 0 and env.actions == [] and events == []
        saved = json.loads(Path('trajectory.json').read_text())
        assert saved['info']['exit_status'] == 'LimitsExceeded'
        assert saved['messages'][-1]['extra'] == result
        # Upstream counts attempted queries; native receipts count physical calls.
        assert saved['info']['model_stats']['api_calls'] == 1
    ''')


def test_context_growth_preserves_previous_call_and_then_stops(tmp_path):
    run_inert(tmp_path, '''
        adapter, tokenizer, model, events = make_adapter(context_limit=12)
        template = tokenizer.apply_chat_template
        def growing_template(messages, **kwargs):
            tokenizer.input_ids = [11,12,13] if len(messages) == 2 else [11,12,13,14,15]
            return template(messages, **kwargs)
        tokenizer.apply_chat_template = growing_template
        agent, env = agent_for(adapter)
        result = agent.run(task='public fixture task')
        assert result['exit_status'] == 'LimitsExceeded' and result['input_tokens'] == 5
        assert result['submission'] == ''
        assert model.calls == adapter.n_calls == 1 and len(env.actions) == 1
        assert [e['event'] for e in events] == ['request', 'response']
        assert events[-1]['physical_calls'] == 1 and agent.n_calls == 2
    ''')


@pytest.mark.parametrize('failure_stage', ['tokenizer', 'generation'])
def test_other_value_errors_remain_infrastructure(tmp_path, failure_stage):
    run_inert(tmp_path, f'failure_stage = {failure_stage!r}\n' + textwrap.dedent('''
        adapter, tokenizer, model, events = make_adapter()
        failure = ValueError('fixture unrelated native defect')
        def fail(*args, **kwargs): raise failure
        if failure_stage == 'tokenizer': tokenizer.apply_chat_template = fail
        else: model.generate = fail
        agent, env = agent_for(adapter)
        try:
            agent.run(task='public fixture task')
        except ValueError as error:
            assert error is failure and not isinstance(error, ContextBudgetExceeded)
        else:
            raise AssertionError('generic native defect was swallowed as operational')
        saved = json.loads(Path('trajectory.json').read_text())
        assert saved['info']['exit_status'] == 'ValueError' and env.actions == []
        if failure_stage == 'tokenizer':
            assert adapter.n_calls == 0 and events == []
        else:
            assert adapter.n_calls == 1
            assert [e['event'] for e in events] == ['request', 'generation_error']
            assert events[-1]['error_type'] == 'ValueError'
    '''))


def test_repeated_bootstrap_preserves_operational_exception_identity(tmp_path):
    run_inert(tmp_path, '''
        exceptions = sys.modules['minisweagent.exceptions']
        parser = sys.modules['minisweagent.models.utils.actions_text']
        agent_module = sys.modules['minisweagent.agents.default']
        for _ in range(16):
            assert load_pinned_default_agent() is DefaultAgent
            assert sys.modules['minisweagent.exceptions'] is exceptions
            assert agent_module.InterruptAgentFlow is exceptions.InterruptAgentFlow
            assert parser.FormatError is exceptions.FormatError
            adapter, _, _, _ = make_adapter(context_limit=10)
            agent, _ = agent_for(adapter)
            assert agent.run(task='public fixture')['exit_status'] == 'LimitsExceeded'
    ''')


def test_bootstrap_rejects_split_exception_identity(tmp_path):
    run_inert(tmp_path, '''
        sys.modules['minisweagent.exceptions'].LimitsExceeded = type('ForeignLimits', (Exception,), {})
        try:
            load_pinned_default_agent()
        except RuntimeError as error:
            assert 'exception class identity mismatch' in str(error)
        else:
            raise AssertionError('split exception identity accepted')
    ''')


def test_bootstrap_preserves_existing_pydantic_module(tmp_path):
    run_inert(tmp_path, '''
        import sys, types
        sentinel = types.ModuleType('pydantic')
        sys.modules['pydantic'] = sentinel
        from experiments.lead_req030.seaborn_runner_qualification import load_pinned_default_agent
        first = load_pinned_default_agent()
        assert sys.modules['pydantic'] is sentinel
        assert load_pinned_default_agent() is first
        assert sys.modules['pydantic'] is sentinel
    ''', harness='')


def test_bootstrap_rejects_unqualified_partial_package(tmp_path):
    run_inert(tmp_path, '''
        import sys, types
        from experiments.lead_req030.seaborn_runner_qualification import load_pinned_default_agent
        sys.modules['minisweagent.exceptions'] = types.ModuleType('minisweagent.exceptions')
        try:
            load_pinned_default_agent()
        except RuntimeError as error:
            assert 'partial or foreign pinned-agent bootstrap' in str(error)
        else:
            raise AssertionError('partial bootstrap accepted')
    ''', harness='')
