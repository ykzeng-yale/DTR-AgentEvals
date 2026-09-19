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
import ast, hashlib, json, os, re, secrets, time, warnings

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
_SPECIAL = re.compile(r'<\|(?:im_end|im_start|endoftext|end_of_text|eot_id)\|>')
_DEF = re.compile(r'^\s*(?:async\s+)?(?:def|class)\s', re.M)
_PY_TAGS = ('', 'python', 'python3', 'py')
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


def fenced_blocks(text: str) -> list:
    """(language_tag, body) for every fenced block, by scanning fence LINES (so a ```bash block cannot mis-pair with the
    python block after it). A block left open by a truncated reply is closed at the end of the text."""
    out, tag, buf = [], None, []
    for line in _SPECIAL.sub('', text or '').splitlines():
        st = line.strip()
        if st.startswith('```'):
            if tag is None:
                tag, buf = st[3:].strip().lower(), []
            else:
                out.append((tag, '\n'.join(buf))); tag = None
                rest = st[3:].strip()
                if rest:                       # "```python" used as a closing+opening fence on one line is not valid markdown; ignore
                    pass
        elif tag is not None:
            buf.append(line)
    if tag is not None:
        out.append((tag, '\n'.join(buf)))
    return [(t, b) for t, b in out if b.strip()]


def extract_code(text: str, entry_point: str | None = None) -> str:
    """The solution in a reply. Among python (or untagged) fenced blocks: the LAST one that defines the entry point (a
    repair reply often quotes the old code first and gives the fix last; a trailing usage/test block that merely defines
    helpers must not win); else the last block that defines anything; else the last block; else the raw text."""
    if not text:
        return ''
    blocks = [b for t, b in fenced_blocks(text) if t in _PY_TAGS]
    if blocks:
        if entry_point:
            ep = re.compile(r'^\s*(?:async\s+)?def\s+%s\s*\(' % re.escape(entry_point), re.M)
            hit = [b for b in blocks if ep.search(b)]
            if hit:
                return hit[-1].strip('\n') + '\n'
        defs = [b for b in blocks if _DEF.search(b)]
        return (defs[-1] if defs else blocks[-1]).strip('\n') + '\n'
    return _SPECIAL.sub('', text).strip() + '\n'


def extract_tests_text(text: str) -> str:
    """For the test writer: every python/untagged fenced block concatenated (asserts may be split across blocks)."""
    blocks = [b for t, b in fenced_blocks(text) if t in _PY_TAGS]
    return ('\n'.join(b.strip('\n') for b in blocks) if blocks else _SPECIAL.sub('', text or '').strip()) + '\n'


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
        if os.environ.get('MOCK_INJECT_ERRORS') and kind == 'code' and (h // 7) % 40 == 0:
            raise ConnectionError('mock injected infrastructure failure')     # exercises retry and intention-to-treat paths
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
MAX_CHECKS = 10


def canonical_tests(raw: str, entry_point: str) -> dict:
    """Deterministic canonical form of the writer's reply: guarded imports + independent checks.

    Top-level asserts are checks. A top-level ``def test*`` whose body is only asserts is flattened into checks;
    otherwise it becomes one check that defines and calls it (if it takes no arguments). Everything else is dropped
    - in particular any definition of the entry point itself, which would otherwise shadow the candidate. A reply
    truncated mid-line is salvaged by dropping trailing lines until it parses. The SAME text is executed by the tool
    and shown to the model in repair prompts."""
    lines = (raw or '').splitlines(); tree = None; dropped = 0
    for dropped in range(0, min(len(lines), 40) + 1):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree = ast.parse('\n'.join(lines[:len(lines) - dropped]))
            break
        except SyntaxError:
            tree = None
    setup, checks = [], []
    for n in (tree.body if tree is not None else []):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            setup.append(ast.unparse(n))
        elif isinstance(n, ast.Assert):
            checks.append(ast.unparse(n))
        elif isinstance(n, ast.FunctionDef) and n.name.lower().startswith('test') and n.name != entry_point:
            body = [b for b in n.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b, 'value', None), ast.Constant))]
            if body and all(isinstance(b, ast.Assert) for b in body):
                checks += [ast.unparse(b) for b in body]
            elif not (n.args.args or n.args.posonlyargs or n.args.kwonlyargs):
                checks.append(ast.unparse(n) + '\n' + n.name + '()')
    if not checks:      # last resort: any single line that is by itself a complete assert (e.g. after a bogus `import assert`)
        for l in lines:
            l = l.strip()
            if l.startswith('assert ') or l.startswith('assert('):
                try:
                    checks.append(ast.unparse(ast.parse(l).body[0]))
                except (SyntaxError, IndexError):
                    pass
        setup = [x for x in setup if x not in ('import assert',)]
    checks = checks[:MAX_CHECKS]
    text = '\n'.join(setup + checks)
    return dict(setup=setup, checks=checks, text=text, n_checks=len(checks), parsed=tree is not None, salvage_lines_dropped=dropped if tree is not None else None)


def _call_keys(src: str, names: set) -> set:
    """ast.dump of (args, keywords) for every call to one of ``names`` inside ``src`` (quote style / spacing insensitive)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(src)
    except SyntaxError:
        return set()
    return {ast.dump(ast.Tuple(elts=list(n.args), ctx=ast.Load())) + '|' + ','.join(sorted(ast.dump(k) for k in n.keywords))
            for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names}


def hidden_input_keys(task: dict) -> set:
    ep = task.get('entry_point') or ''
    src = '\n'.join(list(task.get('test_list') or []) + list(task.get('challenge_test_list') or [])) if task['benchmark'] == 'mbpp' else (task.get('test') or '')
    return _call_keys(src, {ep, 'candidate'})


def certified_tests(task: dict, canon: dict, cfg: dict) -> dict:
    """Environment construction only; no model is involved. From the writer's canonical checks keep those that
      1. actually call the entry point (a check that never calls it is vacuous),
      2. do NOT use an input that a hidden test uses - after certification such a check would BE a hidden assert with
         its answer, and it is pasted into repair prompts (the writer has evidently memorised benchmark examples).
         Hidden tests are consulted here once, only to REMOVE coinciding checks; no hidden text reaches any prompt,
      3. the reference implementation passes (wrong expected values, wrong call conventions are dropped).
    Result: no false alarms on reference-equivalent code, real false passes (incomplete coverage), no hidden answers."""
    ep = task.get('entry_point') or ''
    hidden = hidden_input_keys(task)
    calls = [_call_keys(c, {ep}) for c in canon['checks']]
    step1 = [(c, k) for c, k in zip(canon['checks'], calls) if k]
    step2 = [c for c, k in step1 if not (k & hidden)]

    def run(checks):
        return validate(task, task['reference'], dict(setup=canon['setup'], checks=checks, n_checks=len(checks)), cfg).get('per_check')
    res = run(step2) if step2 else []
    if res is None:                      # one check crashed / hung the reference: certify each check on its own
        res = [(run([c]) or ['fail'])[0] for c in step2]
    keep = [c for c, r in zip(step2, res) if r == 'ok']
    setup = canon['setup'] if keep else []
    return dict(setup=setup, checks=keep, text='\n'.join(setup + keep), n_checks=len(keep), n_written=canon['n_checks'],
                n_dropped_vacuous=canon['n_checks'] - len(step1), n_dropped_hidden_overlap=len(step1) - len(step2),
                n_dropped_by_reference=len(step2) - len(keep))


def _hoist_future(code: str):
    fut = [l for l in code.splitlines() if re.match(r'\s*from\s+__future__\s+import\s', l)]
    rest = '\n'.join(l for l in code.splitlines() if l not in fut)
    return fut, rest


def prelude(task: dict) -> str:
    """Names a correct solution may rely on without defining them: HumanEval helpers/imports that exist only in the
    prompt (the prompt plus a stub body, later shadowed by the candidate) and MBPP's harness imports. Used identically
    by the visible-test tool and the hidden-test verifier so the two never disagree about what is in scope."""
    if task['benchmark'] == 'humaneval':
        return task['prompt'].rstrip() + '\n    pass\n'
    return '\n'.join(task.get('test_imports') or [])


def validation_program(task: dict, code: str, tests: dict, nonce: str) -> str:
    fut, body = _hoist_future(code)
    lines = fut + ['import sys as __vs, os as __vo, json as __vj', '__vreal = __vs.stdout', "__vs.stdout = open(__vo.devnull, 'w')",
                   '__vres = []', prelude(task), body.rstrip(), '']
    for imp in tests['setup']:
        lines += ['try:', '    ' + imp, 'except Exception:', '    pass']
    for src in tests['checks']:
        lines += ['try:'] + ['    ' + l for l in src.splitlines()] + ["    __vres.append(['ok', ''])", 'except BaseException as __ve:',
                  '    __vres.append([type(__ve).__name__, (%r + " -> " + repr(__ve))[:300]])' % src.splitlines()[0][:200]]
    lines += ['__vs.stdout = __vreal', "print(%r + __vj.dumps(__vres), flush=True)" % ('\n__VALID_%s__' % nonce)]
    return '\n'.join(lines) + '\n'


def validate(task: dict, code: str, tests: dict, cfg: dict) -> dict:
    """Tool result. passed iff the candidate loads and no visible check fails (zero checks = load check only).
    Candidate stdout is silenced while it runs, so the result line cannot be lost in or spoofed by its output."""
    n = tests['n_checks']
    if not code.strip():
        return dict(passed=False, fail_class='exception', err='EmptyReply', n_asserts=n, n_fail=n, frac_fail=1.0,
                    trace='The reply contained no code.', seconds=0.0, timed_out=False)
    nonce = secrets.token_hex(6); marker = '__VALID_%s__' % nonce
    run = run_program(validation_program(task, code, tests, nonce), timeout_s=cfg['sandbox_timeout_s'], cpu_seconds=cfg['sandbox_cpu_s'])
    line = next((l for l in reversed(run['stdout'].splitlines()) if l.startswith(marker)), None)
    res = None
    if line is not None:
        try:
            res = json.loads(line[len(marker):])
        except ValueError:
            res = None
    if res is None:
        tail = (run['stderr'] or '').strip().splitlines()
        err = 'Timeout' if run['timed_out'] else (tail[-1].split(':')[0].strip()[:40] if tail else 'Crash')
        return dict(passed=False, fail_class='exception', err=err, n_asserts=n, n_fail=n, frac_fail=1.0,
                    trace='\n'.join(tail[-8:])[:1500], seconds=run['seconds'], timed_out=bool(run['timed_out']))
    bad = [r for r in res if r[0] != 'ok']
    only_assert = all(b[0] == 'AssertionError' for b in bad)
    return dict(passed=not bad, fail_class=('none' if not bad else ('assertion' if only_assert else 'exception')),
                err=('none' if not bad else bad[0][0][:40]), n_asserts=n, n_fail=len(bad), frac_fail=len(bad) / max(n, 1),
                trace='\n'.join(b[1] for b in bad[:3])[:1500], seconds=run['seconds'], timed_out=False, per_check=[r[0] for r in res])


def verify_hidden(task: dict, code: str, cfg: dict) -> dict:
    fut, body = _hoist_future(code)
    return verify(task, '\n'.join(fut + [prelude(task), body]) if code.strip() else code, timeout_s=cfg['sandbox_timeout_s'], cpu_seconds=cfg['sandbox_cpu_s'])


def repair_message(tests: dict, trace: str) -> str:
    return ASK_REPAIR.format(tests=tests['text'] or '# (no visible tests; the solution failed to load)', trace=trace)


# ------------------------------------------------------------------ branch restoration
def restore_first_failure_prefix(task: dict, tests: dict, parent: dict, cfg: dict) -> dict:
    """Rebuild the exact transcript that preceded the parent's t=1 decision and re-run the tool on the parent's
    first candidate. Fidelity checks: transcript hash equals the hash logged BEFORE the parent's t=1 call, and the
    re-validated candidate reproduces the logged tool result."""
    d0, d1 = parent['decisions'][0], parent['decisions'][1]
    convo = [dict(role='system', content=SYS_CODE), dict(role='user', content=task_prompt(task)),
             dict(role='assistant', content=d0['reply']), dict(role='user', content=repair_message(tests, d0['trace']))]
    h = hashlib.sha256(json.dumps(convo, sort_keys=True).encode()).hexdigest()
    val = validate(task, d0['code'], tests, cfg)
    same_tool = all(val[k] == d0['validation'][k] for k in ('passed', 'fail_class', 'n_asserts', 'n_fail'))
    return dict(convo=convo, code=d0['code'], val=val, prev=[d0['a']], t=1,
                restoration=dict(transcript_hash_matches=(h == d1['transcript_sha256']), tool_result_reproduced=bool(same_tool)))


# ------------------------------------------------------------------ episode
def run_episode(task: dict, tests: dict, ep: dict, choose, models: dict, cfg: dict, stamp: dict, on_decision=None, resume=None) -> dict:
    """choose(state) -> (action_index, prob_of_large, source, draw). Every decision is appended to the record AND handed to
    ``on_decision`` (durably logged by the caller) BEFORE the model is invoked, so an episode that dies mid-call still
    carries the action that was assigned (needed for intention-to-treat scoring of unresolved episodes)."""
    K = cfg['horizon']; mock = isinstance(models['small'], MockModel)
    rec = dict(episode_id=ep['episode_id'], task_uid=task['uid'], benchmark=task['benchmark'], split=ep.get('split'), run=ep.get('run'),
               policy=ep.get('policy', 'randomized_log'), seed=ep['seed'], start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               error=None, decisions=[], n_visible_checks=tests['n_checks'], **stamp)
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
            a, p_large, source, draw = choose(state)
            dec = dict(t=t, eligible=True, available_actions=list(ACTIONS), state=dict(state, prev_actions=list(prev)), action=ACTIONS[a], a=a,
                       p_large=p_large, b_obs=p_large if a == 1 else 1 - p_large, source=source, draw=draw, penalty=cfg['call_penalty'][ACTIONS[a]],
                       completed=False, transcript_sha256=hashlib.sha256(json.dumps(convo, sort_keys=True).encode()).hexdigest())
            rec['decisions'].append(dec); prev.append(a)
            if on_decision:
                on_decision(rec['episode_id'], dec)                       # persisted before invocation
            m = models[ACTIONS[a]]
            kw = dict(task_uid=task['uid'], kind='code') if mock else {}
            out = m.chat(convo, ep['seed'] + 101 * t, **kw)
            code = extract_code(out['text'], task.get('entry_point'))
            val = validate(task, code, tests, cfg)
            dec.update(completed=True, model_alias=m.alias, response_model=out['response_model'], finish=out['finish'], prompt_tokens=out['prompt_tokens'],
                       completion_tokens=out['completion_tokens'], wall_seconds=out['wall_seconds'], server_gen_ms=out['server_gen_ms'],
                       server_prompt_ms=out['server_prompt_ms'], reply=out['text'], code=code, validation={k: val[k] for k in val if k not in ('trace', 'per_check')},
                       trace=val['trace'])
            if val['passed']:
                break
            convo = convo + [dict(role='assistant', content=out['text']), dict(role='user', content=repair_message(tests, val['trace']))]
        rec['agent_seconds'] = time.perf_counter() - t0
        v = verify_hidden(task, code, cfg)
        rec.update(final_code=code, n_decisions=len(prev), n_new_decisions=len(rec['decisions']), actions=[ACTIONS[a] for a in prev], stop_reason='validated' if val['passed'] else 'horizon',
                   success=int(v['success']), verify_timed_out=v['timed_out'], hack_flags=v['hack_flags'], sentinel_seen=v['sentinel_seen'],
                   validation_timeouts=sum(bool(d['validation'].get('timed_out')) for d in rec['decisions']),
                   penalty=sum(d['penalty'] for d in rec['decisions']), completion_tokens=sum(d['completion_tokens'] for d in rec['decisions']),
                   llm_wall_seconds=sum(d['wall_seconds'] for d in rec['decisions']))
        rec['utility'] = rec['success'] - rec['penalty']
        if resume is None and len(rec['decisions']) > 1:
            # mechanism only, computed AFTER the episode has ended and never shown to any model: was the first candidate
            # already correct on the hidden tests although the visible tests rejected it (a false alarm)?
            rec['success_first_candidate'] = int(verify_hidden(task, rec['decisions'][0]['code'], cfg)['success'])
        elif resume is None:
            rec['success_first_candidate'] = rec['success']
    except Exception as e:                                                # infrastructure failure: recorded, never dropped
        rec['error'] = repr(e)[:500]
        rec['n_decisions_before_error'] = sum(bool(d.get('completed')) for d in rec['decisions'])
    return rec
