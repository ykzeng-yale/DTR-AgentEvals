"""Frozen finite class of target routing policies. Each maps a PRE-ACTION state to P(large).

state = dict(t, x_humaneval, fail_class in {'start','assertion','exception'}, prev_actions tuple, frac_fail)
Under absorbing success a decision at t>=1 exists only after a failed validation, so
"switch at fixed turn 1" and "escalate after the first failure" are the same policy here.
"""
from __future__ import annotations

P_BEHAVIOR = 0.5


def _odds_shift(b: float, delta: float) -> float:
    return delta * b / (delta * b + 1 - b)


def always_small(s): return 0.0
def always_large(s): return 1.0
def escalate_after_first_failure(s): return 0.0 if s['t'] == 0 else 1.0
def escalate_after_second_failure(s): return 1.0 if s['t'] >= 2 else 0.0
def large_then_small(s): return 1.0 if s['t'] == 0 else 0.0
def class_tailored(s): return 0.0 if s['t'] == 0 else (1.0 if s['fail_class'] == 'assertion' else 0.0)
def soft_escalation_d2(s): return P_BEHAVIOR if s['t'] == 0 else _odds_shift(P_BEHAVIOR, 2.0)
def soft_escalation_d4(s): return P_BEHAVIOR if s['t'] == 0 else _odds_shift(P_BEHAVIOR, 4.0)


PRESPECIFIED = dict(always_small=always_small, always_large=always_large,
                    escalate_after_first_failure=escalate_after_first_failure,
                    escalate_after_second_failure=escalate_after_second_failure,
                    large_then_small=large_then_small, class_tailored=class_tailored,
                    soft_escalation_d2=soft_escalation_d2, soft_escalation_d4=soft_escalation_d4)
BASELINE = 'always_small'


def state_key(s) -> tuple:
    """Tabular pre-action state used by the Q tables and the learned policy."""
    prev = tuple(s['prev_actions'])
    return (int(s['t']), int(s['x_humaneval']), str(s['fail_class']), prev[-1] if prev else -1)


def table_policy(table: dict, default: float = 0.0):
    def pol(s):
        return float(table.get(state_key(s), default))
    return pol
