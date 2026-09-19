"""Small exact algebra checks for the paper review; no sampled experiments.

These tests cover boundary cases and newly proposed extension formulae. They
are checks of finite examples, not substitutes for the accompanying proofs.
"""
from itertools import product
import numpy as np


def bern(z, p):
    return p if z else 1-p


def test_known_randomization_efficiency_differs_from_behavior_adaptive_mean():
    """At delta=1 the same numerical policy denotes two different functionals."""
    b = .5
    mu = np.array([.1, .9])
    value = .5
    fixed_var = adaptive_var = fixed_action_cov = 0.
    for a, y in product((0, 1), repeat=2):
        p = bern(a, b)*bern(y, mu[a])
        fixed = y-mu[a]  # pi=b held fixed under submodel perturbations
        adaptive = fixed + (mu[1]-mu[0])*(a-b)
        assert np.isclose(adaptive, y-value)
        fixed_var += p*fixed**2
        adaptive_var += p*adaptive**2
        fixed_action_cov += p*fixed*(a-b)
    assert np.isclose(fixed_var, .09)
    assert np.isclose(adaptive_var, .25)
    assert np.isclose(fixed_action_cov, 0.)


def test_selected_branches_do_not_inherit_the_root_task_population():
    """Clustering cannot repair a branch-selection estimand mismatch."""
    # Root H is Bernoulli(.5), branch contrast is D=H, selection favors H=1.
    prob_h = np.array([.5, .5])
    e = np.array([.2, .8])
    mu = np.array([0., 1.])
    selected_mean = np.sum(prob_h*e*mu)/np.sum(prob_h*e)
    root_mean = np.sum(prob_h*mu)
    inverse_selection_mean = np.sum(prob_h*e/e*mu)
    assert np.isclose(selected_mean, .8)
    assert np.isclose(root_mean, .5)
    assert np.isclose(inverse_selection_mean, root_mean)


def test_transported_branch_augmented_variance_by_full_enumeration():
    """Check the proposed branch score's mean and misspecified-m variance."""
    p_h = np.array([.3, .7])
    q_h = np.array([.6, .4])
    w = q_h/p_h
    e = np.array([.4, .7])
    p_positive = np.array([.3, .8])
    mu = 2*p_positive-1
    var_d = 1-mu**2
    m = np.array([.2, -.1])
    mean = second = 0.
    for h, s, is_positive in product((0, 1), repeat=3):
        d = 2*is_positive-1
        probability = p_h[h]*bern(s, e[h])*bern(is_positive, p_positive[h])
        score = w[h]*(m[h]+s/e[h]*(d-m[h]))
        mean += probability*score
        second += probability*score**2
    target = np.sum(q_h*mu)
    base_mean = np.sum(p_h*w*mu)
    between = np.sum(p_h*(w*mu-base_mean)**2)
    within = np.sum(p_h*w**2*(var_d/e+(1/e-1)*(mu-m)**2))
    assert np.isclose(mean, target)
    assert np.isclose(second-mean**2, between+within)


def test_oracle_branch_allocation_satisfies_interior_stationarity():
    """The allocation objective depends on residual second moments, not v alone."""
    p_h = np.array([.4, .6])
    w = np.array([1.5, 2/3])
    cost = np.array([1., 2.])
    variance = np.array([.2, .3])
    squared_bias = np.array([.09, .01])
    residual_second_moment = variance+squared_bias
    budget = .6
    scale = budget/np.sum(p_h*abs(w)*np.sqrt(residual_second_moment*cost))
    e = scale*abs(w)*np.sqrt(residual_second_moment/cost)
    assert np.all((e>0)&(e<1))
    assert np.isclose(np.sum(p_h*cost*e), budget)
    # KKT derivative: w^2 E[(D-m)^2|H] / e^2 = lambda * c.
    ratio = w**2*residual_second_moment/(e**2*cost)
    assert np.isclose(ratio[0], ratio[1])
    # A tangent perturbation preserving expected cost has vanishing derivative.
    tangent = np.array([1., -p_h[0]*cost[0]/(p_h[1]*cost[1])])
    derivative = np.sum(-p_h*w**2*residual_second_moment/e**2*tangent)
    assert abs(derivative)<1e-12


def test_sequential_kernel_tv_bound_is_sharp_for_absorbing_perturbations():
    """Common payoff range=1; each altered kernel flips with probability eps."""
    eps = np.array([.1, .2, .3])
    reference = []
    perturbed = []
    rewards = []
    for states in product((0, 1), repeat=3):
        previous = 0
        p_path = q_path = 1.
        for t, current in enumerate(states):
            p_path *= float(current == previous)
            q_next_one = 1. if previous else eps[t]
            q_path *= bern(current, q_next_one)
            previous = current
        reference.append(p_path)
        perturbed.append(q_path)
        rewards.append(states[-1])
    reference = np.array(reference)
    perturbed = np.array(perturbed)
    assert np.isclose(reference.sum(), 1.)
    assert np.isclose(perturbed.sum(), 1.)
    trace_tv = .5*np.sum(abs(reference-perturbed))
    target_value_difference = np.dot(perturbed-reference, rewards)
    bound = 1-np.prod(1-eps)
    assert np.isclose(target_value_difference, .496)
    assert np.isclose(target_value_difference, trace_tv)
    assert np.isclose(trace_tv, bound)
    assert bound <= np.sum(eps)


def test_two_sample_branch_variance_by_independent_joint_enumeration():
    p_h = np.array([.3, .7])
    q_h = np.array([.6, .4])
    w = q_h/p_h
    e = np.array([.4, .7])
    p_positive = np.array([.3, .8])
    mu = 2*p_positive-1
    var_d = 1-mu**2
    m = np.array([.2, -.1])
    mean = second = 0.
    # One independent observation from each population; n=N=1.
    for hq, hb, s, positive in product((0, 1), repeat=4):
        probability = q_h[hq]*p_h[hb]*bern(s, e[hb])*bern(positive, p_positive[hb])
        d_observed = 2*positive-1
        score = m[hq]+w[hb]*s/e[hb]*(d_observed-m[hb])
        mean += probability*score
        second += probability*score**2
    residual_mean = mu-m
    target_m_mean = np.dot(q_h, m)
    correction_mean = np.dot(p_h, w*residual_mean)
    variance = np.dot(q_h, (m-target_m_mean)**2)
    variance += np.dot(p_h, (w*residual_mean-correction_mean)**2)
    variance += np.dot(p_h, w**2*(var_d/e+(1/e-1)*residual_mean**2))
    assert np.isclose(mean, np.dot(q_h, mu))
    assert np.isclose(second-mean**2, variance)


def test_opportunity_ratio_second_moment_bound_can_be_sharp_without_switches():
    k = 4
    mean_weight = second_moment = 0.
    for actions in product((0, 1), repeat=k):
        behavior_probability = .5**k
        target_probability = float(not any(actions))
        weight = target_probability/behavior_probability
        mean_weight += behavior_probability*weight
        second_moment += behavior_probability*weight**2
        if weight:
            actual_switches = sum(actions[t]!=actions[t-1] for t in range(1, k))
            assert actual_switches == 0
            assert weight == 2**k
    assert np.isclose(mean_weight, 1.)
    assert np.isclose(second_moment, 2**k)
