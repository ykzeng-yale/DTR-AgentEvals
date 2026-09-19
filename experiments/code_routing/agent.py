"""Coding agent with up to K=3 model-routing decisions and absorbing success.

Timeline of one episode (docs/theory.md section 1; docs/experiment_protocol.md 4.2)
  t=0  eligible always.           chosen model writes a solution.
  tool run the task's FROZEN visible tests on it (sandbox). pass -> submit (absorb).
  t=1  eligible iff first validation failed.   chosen model repairs, seeing the full
       transcript (task, earlier attempts by whichever model, tool feedback).
  tool pass -> submit.
  t=2  eligible iff second validation failed.  chosen model repairs again.
  end  the latest candidate is submitted and scored ONCE on the hidden tests.

The action is only "which model"; prompts, decoding, tools and the continuation
rule are one fixed kernel. The assignment for every decision comes from the
caller (pre-drawn design, or a target policy for live runs); this module never
draws randomness of its own and never sees hidden tests outside verify().

Pre-action state handed to a policy at decision t:
  dict(t, x_humaneval, fail_class in {'start','assertion','exception'},
       prev_actions tuple, frac_fail of the last validation)
"""
from __future__ import annotations
import ast, hashlib, json, re, secrets, time, warnings

import requests

from sandbox import run_program
from verify import verify

SYS_CODE = ('You are an expert Python programmer. Reply with one complete, self-contained Python solution in a single '
            '```python code block. Include every import you need. Do not include tests, prints, or example usage.')
SYS_TEST = 'You are an expert Python tester.'
ASK_TESTS = ('Write 3 to 5 `assert` statements that test a correct implementation of `{ep}` for the task above. Reply with a '
             'single ```python code block containing only assert statements (plus imports if needed). Do not implement the '
             'function. Cover typical inputs and at least one edge case.')
ASK_REPAIR = ('Running the latest solution together with the tests below failed. Fix the implementation. Reply with the '
              'complete corrected solution in a single ```python code block (imports included, no tests).\n\nTests:\n```python\n'
              '{tests}\n```\n\nFailure output:\n```\n{trace}\n```')
_CODE_BLOCK = re.compile(r'```(?:python|py|python3)?[ \t]*\n(.*?)```', re.S)
_SPECIAL = re.compile(r'<\|(?:im_end|im_start|endoftext|end_of_text|eot_id)\|>')
ACTIONS = ('small', 'large')


def signature_line(task: dict) -> str:
    ep = task.get('entry_point') or ''
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(task['reference'])
        defs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        tgt = next((d for d in defs if d.name == ep), None) or (defs[0] if defs else None)
        if tgt is not None:
            return 'def %s(%s):' % (tgt.name, ast.unparse(tgt.args))
    except SyntaxError:
        pass
    return 'def %s(...):' % (ep or 'solution')


def task_prompt(task: dict) -> str:
    """Only the task text and the signature. Never test_list / test (hidden)."""
    if task['benchmark'] == 'mbpp':
        return task['prompt'].rstrip() + '\n\nUse exactly this function signature:\n```python\n%s\n```' % signature_line(task)
    return 'Complete the following Python function.\n\n```python\n%s\n```' % task['prompt']


def tests_prompt(task: dict) -> list:
    return [dict(role='system', content=SYS_TEST),
            dict(role='user', content=task_prompt(task) + '\n\n' + ASK_TESTS.format(ep=task.get('entry_point') or 'the function'))]


def extract_code(text: str) -> str:
    if not text:
        return ''
    blocks = _CODE_BLOCK.findall(text)
    if blocks:
        pick = next((b for b in blocks if re.search(r'^\s*(?:async\s+)?def\s', b, re.M)), blocks[0])
        return pick.strip('\n') + '\n'
    return _SPECIAL.sub('', text).strip() + '\n'


# ------------------------------------------------------------------ models
class LlamaServerModel:
    def __init__(self, role: str, alias: str, port: int, cfg: dict):
        self.role, self.alias, self.cfg = role, alias, cfg
        self.url = 'http://127.0.0.1:%d/v1' % port

    def served_ids(self) -> list:
        r = requests.get(self.url + '/models', timeout=15)
        r.raise_for_status()
        return [m.get('id') for m in r.json().get('data', [])]

    def chat(self, messages, seed, temperature=None, max_tokens=None, **_):
        body = dict(model=self.alias, messages=messages, top_p=self.cfg['top_p'], seed=int(seed), stream=False,
                    temperature=self.cfg['temperature'] if temperature is None else temperature,
                    max_tokens=max_tokens or self.cfg['max_tokens'])
        t0 = time.perf_counter()
        r = requests.post(self.url + '/chat/completions', json=body, timeout=self.cfg['request_timeout_s'])
        r.raise_for_status()
        d = r.json(); u = d.get('usage') or {}; tm = d.get('timings') or {}
        return dict(text=d['choices'][0]['message'].get('content') or '', finish=d['choices'][0].get('finish_reason'),
                    prompt_tokens=int(u.get('prompt_tokens') or 0), completion_tokens=int(u.get('completion_tokens') or 0),
                    wall_seconds=time.perf_counter() - t0, server_prompt_ms=tm.get('prompt_ms'), server_gen_ms=tm.get('predicted_ms'),
                    response_model=d.get('model'))


class MockModel:
    """Deterministic stand-in for pipeline dry runs ONLY. It peeks at the reference solution, so its numbers
    are meaningless; every record it produces carries mock=true and is written under work/."""

    def __init__(self, role: str, tasks: dict, skill: float):
        self.role, self.alias, self.tasks, self.skill = role, 'mock-' + role, tasks, skill

    def served_ids(self):
        return [self.alias]

    def chat(self, messages, seed, task_uid=None, kind='code', **_):
        t = self.tasks[task_uid]; ep = t.get('entry_point') or 'solution'
        h = int(hashlib.sha256(('%s|%s|%s|%d' % (self.alias, task_uid, kind, seed)).encode()).hexdigest(), 16)
        u, v = (h % 1000) / 1000.0, (h // 1000 % 1000) / 1000.0
        if kind == 'tests':
            body = 'assert callable(%s)\nassert %s.__doc__ is None or isinstance(%s.__doc__, str)\n' % (ep, ep, ep)
            if u < 0.25:
                body += "assert %s.__name__ == '__wrong__'\n" % ep          # an invalid visible test -> false alarms
            text = '```python\n%s```' % body
        elif u < self.skill:
            text = '```python\n%s\n```' % t['reference']
        elif v < 0.5:
            text = '```python\ndef %s(*args, **kwargs):\n    return None\n```' % ep   # silently wrong: passes weak visible tests
        else:
            text = '```python\nraise RuntimeError("mock crash")\n```'                 # exception-class failure
        return dict(text=text, finish='stop', prompt_tokens=50, completion_tokens=max(1, len(text) // 4), wall_seconds=0.0,
                    server_prompt_ms=None, server_gen_ms=None, response_model=self.alias)


# ------------------------------------------------------------------ visible-test tool
def validation_program(code: str, tests: str, nonce: str):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(tests or '')
    except SyntaxError:
        tree = ast.parse('')
    setup = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    asserts = [n for n in tree.body if isinstance(n, ast.Assert)]
    lines = [code.rstrip(), '', 'import json as __json', '__res = []'] + [ast.unparse(s) for s in setup]
    for a in asserts:
        src = ast.unparse(a)
        lines += ['try:', '    ' + src, "    __res.append(['ok', ''])", 'except BaseException as __e:',
                  '    __res.append([type(__e).__name__, (%r + " -> " + repr(__e))[:300]])' % src[:200]]
    lines.append('print(%r + __json.dumps(__res), flush=True)' % ('__VALID_%s__' % nonce))
    return '\n'.join(lines) + '\n', len(asserts)


def validate(code: str, tests: str, cfg: dict) -> dict:
    """Tool result. passed iff the candidate loads and no visible assert fails (zero asserts = load check only)."""
    if not code.strip():
        return dict(passed=False, fail_class='exception', err='EmptyReply', n_asserts=0, n_fail=0, frac_fail=1.0,
                    trace='The reply contained no code.', seconds=0.0)
    nonce = secrets.token_hex(6)
    prog, n = validation_program(code, tests, nonce)
    run = run_program(prog, timeout_s=cfg['sandbox_timeout_s'], cpu_seconds=cfg['sandbox_cpu_s'])
    marker = '__VALID_%s__' % nonce
    line = next((l for l in reversed(run['stdout'].splitlines()) if l.startswith(marker)), None)
    if line is None:
        tail = (run['stderr'] or '').strip().splitlines()
        err = 'Timeout' if run['timed_out'] else (tail[-1].split(':')[0].strip()[:40] if tail else 'Crash')
        return dict(passed=False, fail_class='exception', err=err, n_asserts=n, n_fail=n, frac_fail=1.0,
                    trace='\n'.join(tail[-8:])[:1500], seconds=run['seconds'])
    res = json.loads(line[len(marker):])
    bad = [r for r in res if r[0] != 'ok']
    only_assert = all(b[0] == 'AssertionError' for b in bad)
    return dict(passed=not bad, fail_class=('none' if not bad else ('assertion' if only_assert else 'exception')),
                err=('none' if not bad else bad[0][0][:40]), n_asserts=n, n_fail=len(bad), frac_fail=len(bad) / max(n, 1),
                trace='\n'.join(b[1] for b in bad[:3])[:1500], seconds=run['seconds'])


# ------------------------------------------------------------------ branch restoration
def restore_first_failure_prefix(task: dict, tests: str, parent: dict, cfg: dict) -> dict:
    """Rebuild the exact transcript that preceded the parent's t=1 decision and re-run the tool on the parent's
    first candidate. Fidelity checks: transcript hash equals the hash logged BEFORE the parent's t=1 call, and the
    re-validated candidate reproduces the logged tool result."""
    d0, d1 = parent['decisions'][0], parent['decisions'][1]
    convo = [dict(role='system', content=SYS_CODE), dict(role='user', content=task_prompt(task)),
             dict(role='assistant', content=d0['reply']),
             dict(role='user', content=ASK_REPAIR.format(tests=(tests or '# (no visible tests)').strip(), trace=d0['trace']))]
    h = hashlib.sha256(json.dumps(convo, sort_keys=True).encode()).hexdigest()
    val = validate(d0['code'], tests, cfg)
    same_tool = all(val[k] == d0['validation'][k] for k in ('passed', 'fail_class', 'n_asserts', 'n_fail'))
    return dict(convo=convo, code=d0['code'], val=val, prev=[d0['a']], t=1,
                restoration=dict(transcript_hash_matches=(h == d1['transcript_sha256']), tool_result_reproduced=bool(same_tool)))


# ------------------------------------------------------------------ episode
def run_episode(task: dict, tests: str, ep: dict, choose, models: dict, cfg: dict, stamp: dict, on_decision=None, resume=None) -> dict:
    """choose(state) -> (action_index, prob_of_large, source). Decisions are handed to ``on_decision`` (durably
    logged by the caller) BEFORE the model is invoked."""
    K = cfg['horizon']; mock = isinstance(models['small'], MockModel)
    rec = dict(episode_id=ep['episode_id'], task_uid=task['uid'], benchmark=task['benchmark'], split=ep.get('split'), run=ep.get('run'),
               policy=ep.get('policy', 'randomized_log'), seed=ep['seed'], start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               error=None, decisions=[], **stamp)
    convo = [dict(role='system', content=SYS_CODE), dict(role='user', content=task_prompt(task))]
    code, val, prev, t_start = '', None, [], 0
    if resume is not None:      # branch audit: continue from a restored prefix; only the NEW decisions are recorded here
        convo, code, val, prev, t_start = list(resume['convo']), resume['code'], resume['val'], list(resume['prev']), resume['t']
        rec.update(parent_episode_id=resume['parent_episode_id'], fork_t=t_start, fork_arm=resume['arm'], restoration=resume['restoration'])
    t0 = time.perf_counter()
    try:
        for t in range(t_start, K):
            state = dict(t=t, x_humaneval=int(task['benchmark'] == 'humaneval'), fail_class='start' if val is None else val['fail_class'],
                         prev_actions=tuple(prev), frac_fail=0.0 if val is None else val['frac_fail'])
            a, p_large, source = choose(state)
            dec = dict(t=t, eligible=True, state=dict(state, prev_actions=list(prev)), action=ACTIONS[a], a=a, p_large=p_large,
                       b_obs=p_large if a == 1 else 1 - p_large, source=source,
                       transcript_sha256=hashlib.sha256(json.dumps(convo, sort_keys=True).encode()).hexdigest())
            if on_decision:
                on_decision(rec['episode_id'], dec)                       # persisted before invocation
            m = models[ACTIONS[a]]
            kw = dict(task_uid=task['uid'], kind='code') if mock else {}
            out = m.chat(convo, ep['seed'] + 101 * t, **kw)
            code = extract_code(out['text'])
            val = validate(code, tests, cfg)
            dec.update(model_alias=m.alias, response_model=out['response_model'], finish=out['finish'], prompt_tokens=out['prompt_tokens'],
                       completion_tokens=out['completion_tokens'], wall_seconds=out['wall_seconds'], server_gen_ms=out['server_gen_ms'],
                       server_prompt_ms=out['server_prompt_ms'], reply=out['text'], code=code, validation={k: val[k] for k in val if k != 'trace'},
                       trace=val['trace'], penalty=cfg['call_penalty'][ACTIONS[a]])
            rec['decisions'].append(dec); prev.append(a)
            if val['passed']:
                break
            convo = convo + [dict(role='assistant', content=out['text']),
                             dict(role='user', content=ASK_REPAIR.format(tests=(tests or '# (no visible tests)').strip(), trace=val['trace']))]
        rec['agent_seconds'] = time.perf_counter() - t0
        v = verify(task, code, timeout_s=cfg['sandbox_timeout_s'], cpu_seconds=cfg['sandbox_cpu_s'])
        rec.update(final_code=code, n_decisions=len(prev), n_new_decisions=len(rec['decisions']), actions=[ACTIONS[a] for a in prev], stop_reason='validated' if val['passed'] else 'horizon',
                   success=int(v['success']), verify_timed_out=v['timed_out'], hack_flags=v['hack_flags'], sentinel_seen=v['sentinel_seen'],
                   penalty=sum(d['penalty'] for d in rec['decisions']), completion_tokens=sum(d['completion_tokens'] for d in rec['decisions']),
                   llm_wall_seconds=sum(d['wall_seconds'] for d in rec['decisions']))
        rec['utility'] = rec['success'] - rec['penalty']
        if resume is None and len(rec['decisions']) > 1:
            # mechanism only, computed AFTER the episode has ended and never shown to any model: was the first candidate
            # already correct on the hidden tests although the visible tests rejected it (a false alarm)?
            v0 = verify(task, rec['decisions'][0]['code'], timeout_s=cfg['sandbox_timeout_s'], cpu_seconds=cfg['sandbox_cpu_s'])
            rec['success_first_candidate'] = int(v0['success'])
        elif resume is None:
            rec['success_first_candidate'] = rec['success']
    except Exception as e:                                                # infrastructure failure: recorded, never dropped
        rec['error'] = repr(e)[:500]
        rec['n_decisions_before_error'] = len(prev)
    return rec
