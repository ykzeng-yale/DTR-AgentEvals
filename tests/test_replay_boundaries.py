"""Exact toy checks distinguishing outcome copying from adaptive donor replay."""
from fractions import Fraction
from itertools import product


def test_outcome_copying_is_not_frozen_state_reward_recomputation():
    logged_first, logged_second = 0, 0
    logged_state = logged_first
    recorded_y = int(logged_second == logged_state)
    target_first, target_second = 1, 1
    live_y = int(target_second == target_first)
    frozen_state_y = int(target_second == logged_state)
    assert recorded_y == live_y == 1
    assert frozen_state_y == 0


def test_adaptive_donor_replay_loses_state_even_without_missing_donors():
    # U' is the first later matching donor's state. Independent, constant action
    # randomization makes it fair, as proved in docs/theory_replay_boundaries.md.
    replay = Fraction(0)
    for state, logged_action, replacement_state in product((0, 1), repeat=3):
        outcome = 1 if logged_action == state else int(replacement_state == state)
        replay += Fraction(outcome, 8)
    assert replay == Fraction(3, 4)
    assert replay - 1 == Fraction(-1, 4)  # true adaptive policy always succeeds


def test_constant_action_replay_is_valid_in_the_same_toy():
    for target_action in (0, 1):
        replay = Fraction(0)
        for state, logged_action, replacement_state in product((0, 1), repeat=3):
            chosen_state = state if logged_action == target_action else replacement_state
            replay += Fraction(int(chosen_state == target_action), 8)
        assert replay == Fraction(1, 2)
