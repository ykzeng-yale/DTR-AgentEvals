# Adapted from ykzeng-yale/ICLR-WinRatioAgentEval experiments/local_stream/verify.py
# (same author; audited Seatbelt sandbox + sentinel verifier). Changes: sandbox
# base dir renamed to dtr_sbx; sentinel prefix renamed; nothing else.
"""Hidden-test verification of a candidate program.

MBPP: test_imports + candidate code + EVERY assert in test_list (+ challenge
tests when present; none of the 427 sanitized tasks has any). HumanEval:
candidate code (which must define the entry point) + the benchmark's test
string + ``check(entry_point)``. After the tests a per-run nonce sentinel
``print('__DTR_VERIFY_OK__<16 hex>', flush=True)`` is appended. Success iff the
sandbox run passed (returncode 0, no timeout) AND the raw stdout ends with the
sentinel, so a candidate that exits early with status 0 (sys.exit, SystemExit,
os._exit) before the tests is a failure. The nonce is drawn fresh per call and
never shown to the model. Hidden tests are consumed only here; agent.py never
sees them. ``hack_flags`` are static heuristics on the candidate code (never
affecting success) for post-hoc review: SystemExit, os._exit, sys.exit,
def __eq__, builtins, sys.modules, __file__, atexit. The universal-__eq__
hack cannot be prevented by execution alone (shared with every MBPP/HumanEval
harness); flagged successes are counted in the analysis.
"""
from __future__ import annotations
import re, secrets

from sandbox import run_program

SENTINEL_PREFIX = '__DTR_VERIFY_OK__'
HACK_RULES = [
    ('SystemExit', re.compile(r'\bSystemExit\b')),
    ('_exit', re.compile(r'\b_exit\s*\(')),
    ('sys.exit', re.compile(r'\b(?:sys\s*\.\s*)?exit\s*\(')),
    ('def __eq__', re.compile(r'\bdef\s+__eq__\b')),
    ('builtins', re.compile(r'\bbuiltins\b')),
    ('sys.modules', re.compile(r'\bsys\s*\.\s*modules\b')),
    ('__file__', re.compile(r'\b__file__\b')),
    ('atexit', re.compile(r'\batexit\b')),
]


def hack_flags(code: str) -> list:
    return [name for name, rx in HACK_RULES if rx.search(code or '')]


def build_program(task: dict, code: str, sentinel: str | None = None) -> str:
    """Candidate + hidden tests (+ sentinel print when given)."""
    if task['benchmark'] == 'mbpp':
        parts = list(task.get('test_imports') or []) + [code, '']
        parts += list(task['test_list']) + list(task.get('challenge_test_list') or [])
        prog = '\n'.join(parts) + '\n'
    elif task['benchmark'] == 'humaneval':
        prog = code.rstrip() + '\n\n' + task['test'].rstrip() + '\n\ncheck(%s)\n' % task['entry_point']
    else:
        raise ValueError(task['benchmark'])
    if sentinel:
        prog += 'print(%r, flush=True)\n' % sentinel
    return prog


def defines_entry_point(task: dict, code: str) -> bool:
    ep = task.get('entry_point')
    if not ep:
        return True  # unknown entry point: rely on the asserts
    return re.search(r'^\s*(?:async\s+)?def\s+%s\s*\(' % re.escape(ep), code, re.M) is not None or \
        re.search(r'^\s*%s\s*=' % re.escape(ep), code, re.M) is not None


def verify(task: dict, code: str, timeout_s: float = 10.0, mem_bytes: int = 2 << 30, cpu_seconds: int = 10,
           output_cap: int = 65536) -> dict:
    """Run hidden tests.

    Returns dict(success, sandbox_flag, timed_out, entry_point_defined, sentinel_seen,
    hack_flags, verify_seconds, run=<sandbox dict>). success = run passed AND
    sentinel seen. sandbox_flag = heuristic static match (recorded only).
    """
    flags = hack_flags(code)
    if not code or not code.strip():
        return dict(success=False, sandbox_flag=False, timed_out=False, entry_point_defined=False, sentinel_seen=False,
                    hack_flags=flags, verify_seconds=0.0,
                    run=dict(passed=False, returncode=None, stdout='', stderr='empty candidate', stdout_tail='', timed_out=False,
                             seconds=0.0, executed=False, flags=[], limits_applied='', sandbox_kind=None, profile_sha256=None))
    ep_ok = defines_entry_point(task, code)
    sentinel = SENTINEL_PREFIX + secrets.token_hex(8)
    program = build_program(task, code, sentinel)
    run = run_program(program, timeout_s=timeout_s, mem_bytes=mem_bytes, cpu_seconds=cpu_seconds, output_cap=output_cap)
    seen = run.get('stdout_tail', '').rstrip().endswith(sentinel)
    return dict(success=bool(run['passed'] and seen), sandbox_flag=bool(run['flags']), timed_out=bool(run['timed_out']),
                entry_point_defined=ep_ok, sentinel_seen=bool(seen), hack_flags=flags, verify_seconds=float(run['seconds']), run=run)
