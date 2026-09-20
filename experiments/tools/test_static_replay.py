"""Exact controls for the implemented replay mechanism, with known truth and no simulation sweep.

Required by docs/theory_feedback_20260920_replay.md: the A5 summaries must be backed by controls that actually
exercise donor ordering, stopping, fallback and thresholding. Each fixture is a hand-built task log whose correct
stitched outcome can be read off by eye, so a change in `rule_b` that breaks the specification fails here.

Run: .venv/bin/python -m pytest -q experiments/tools/test_static_replay.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ('tools', 'code_routing', 'common', 'dtr'):
    sys.path.insert(0, str(ROOT / 'experiments' / sub))
import static_replay as SR  # noqa: E402


def dec(a, passed, fail_class='assertion', frac=0.5):
    return dict(a=a, completed=True, validation=dict(passed=passed, fail_class=fail_class, frac_fail=frac))


def ep(run, actions_passed, success, benchmark='mbpp'):
    """actions_passed: list of (action, validator_passed) for the stages this episode actually recorded."""
    return dict(episode_id='e%d' % run, run=run, task_uid='t', benchmark=benchmark, success=success,
                decisions=[dec(a, p) for a, p in actions_passed])


ALWAYS_LARGE = lambda s: 1.0
ALWAYS_SMALL = lambda s: 0.0
STOCHASTIC = lambda s: 0.667          # thresholded to "large" by the rule


def test_positive_control_stops_at_first_validated_donor():
    """Smallest run index wins, and a donor that validates at stage 0 ends the replay with ITS success."""
    eps = [ep(0, [(1, True)], success=1.0), ep(1, [(1, True)], success=0.0)]
    assert SR.rule_b(eps, ALWAYS_LARGE) == 1.0          # run 0 wins on index, not on outcome


def test_donor_ordering_is_by_run_index_not_outcome():
    eps = [ep(0, [(1, True)], success=0.0), ep(1, [(1, True)], success=1.0)]
    assert SR.rule_b(eps, ALWAYS_LARGE) == 0.0


def test_stitching_changes_donor_across_stages():
    """Stage 0 donor fails; the stage-1 donor must be the episode whose PREFIX is (1,1), not the original episode."""
    eps = [ep(0, [(1, False), (0, True)], success=0.0),      # prefix (1,0)
           ep(1, [(1, False), (1, True)], success=1.0)]      # prefix (1,1)  <- required for always-large
    assert SR.rule_b(eps, ALWAYS_LARGE) == 1.0


def test_fallback_when_extended_prefix_has_no_donor():
    """No episode continues with (0,0), so the rule falls back to the previous donor's eventual outcome."""
    eps = [ep(0, [(0, False), (1, True)], success=1.0)]      # only (0,1) exists
    assert SR.rule_b(eps, ALWAYS_SMALL) == 1.0              # falls back to run 0's recorded success


def test_no_initial_donor_returns_none():
    eps = [ep(0, [(0, True)], success=1.0)]
    assert SR.rule_b(eps, ALWAYS_LARGE) is None             # nothing starts with a=1


def test_donor_that_stopped_at_horizon_ends_the_replay():
    """A donor that recorded no further stage ends the replay with its own success, even though it never validated."""
    eps = [ep(0, [(1, False)], success=0.0)]
    assert SR.rule_b(eps, ALWAYS_LARGE) == 0.0


def test_stochastic_target_is_thresholded_to_large():
    """Documented limitation: a stochastic policy is read deterministically and collapses to its modal action."""
    eps = [ep(0, [(1, True)], success=1.0), ep(1, [(0, True)], success=0.0)]
    assert SR.rule_b(eps, STOCHASTIC) == SR.rule_b(eps, ALWAYS_LARGE) == 1.0


def test_adaptive_negative_control_state_is_taken_from_the_donor():
    """The failure CLASS driving a state-dependent policy comes from the donor, not from any single real episode -
    this is the substitution the rule makes, and the control pins it down."""
    seen = []

    def policy(s):
        seen.append(s['fail_class'])
        return 1.0 if s['t'] == 0 else (1.0 if s['fail_class'] == 'exception' else 0.0)
    eps = [ep(0, [(1, False), (0, True)], success=1.0)]
    eps[0]['decisions'][0]['validation']['fail_class'] = 'exception'
    out = SR.rule_b(eps, policy)
    assert seen[0] == 'start' and seen[1] == 'exception'    # stage-1 state copied from the donor's record
    # the policy then asks for (1,1); only (1,0) was recorded, so the documented fallback returns the previous
    # donor's eventual outcome - i.e. the reported value is that of a trajectory the policy would NOT have produced
    assert out == 1.0
