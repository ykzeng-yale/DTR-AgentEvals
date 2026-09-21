"""DTR-REQ-003, slice 1: the exact analytic control of experiment_protocol_v2.md section 2. No Monte Carlo.

Model (protocol text): after a common first call, latent repair type U ~ Bernoulli(1/2); observed feedback
F = U xor E with E ~ Bernoulli(q) independent of U. At the repair decision A in {0,1} a fresh terminal success has
probability 1/2 + eta(2A-1)(2U-1); action 1 costs c. Grid: eta in {0, .2}, q in {0, .25, .5}, c = .1.

Every quantity is an exact Fraction. Policy truth is derived twice:
  path 1  full-history enumeration over (U, E, A, Y);
  path 2  Bellman evaluation on the observed state F with belief b(F) = P(U=1 | F).
Both must agree EXACTLY and must equal the protocol's closed forms (checked, not assumed).

Logger-only changes: the target is a function of the kernels and the frozen policy alone. For each supported logger
the exact expectation of the IPW estimator equals the target. Two negative controls must fail: a zero-support logger
and the unweighted mean of logged episodes whose action matches the policy.

Output: experiments/v2_sim/exact_control_truth.json. Analytic diagnostic only; not an agent-performance model.
"""
from __future__ import annotations
import itertools, json
from fractions import Fraction as Fr
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'exact_control_truth.json'
HALF = Fr(1, 2)
ETAS, QS, C = (Fr('0'), Fr('0.2')), (Fr('0'), Fr('0.25'), Fr('0.5')), Fr('0.1')

# frozen policies: observed F -> action. oracle_U sees the latent type; it is a reference, not learnable.
POLICIES = {
    'const_0': lambda f, u: 0,
    'const_1': lambda f, u: 1,
    'observe_F': lambda f, u: f,
    'observe_not_F': lambda f, u: 1 - f,
    'oracle_U': lambda f, u: u,
}
LEARNABLE = ('const_0', 'const_1', 'observe_F', 'observe_not_F')
# loggers: P(A=1 | F=f). floor = min over f, a of P(A=a | F=f)
LOGGERS = {
    'uniform_floor_0.5': {0: HALF, 1: HALF},
    'state_dependent_floor_0.2': {0: Fr('0.2'), 1: Fr('0.8')},
    'zero_support_negative_control': {0: HALF, 1: Fr(1)},
}


def p_success(a, u, eta):
    return HALF + eta * (2 * a - 1) * (2 * u - 1)


def histories(q):
    """(probability, u, e, f) over the latent/noise draws."""
    for u, e in itertools.product((0, 1), repeat=2):
        yield HALF * (q if e else 1 - q), u, e, u ^ e


def truth_enumeration(pol, eta, q):
    succ = cost = Fr(0)
    for pr, u, e, f in histories(q):
        a = pol(f, u)
        for y in (0, 1):
            py = p_success(a, u, eta) if y else 1 - p_success(a, u, eta)
            succ += pr * py * y
        cost += pr * C * a
    return succ, cost


def truth_bellman(pol_name, eta, q):
    """Observed-state recursion. Valid for policies of F only; oracle_U needs the latent state and is excluded."""
    succ = cost = Fr(0)
    for f in (0, 1):
        pf = HALF                                    # P(F=1) = 1/2 for every q
        b = (1 - q) if f else q                      # P(U=1 | F=f)
        a = POLICIES[pol_name](f, None)
        q_succ = b * p_success(a, 1, eta) + (1 - b) * p_success(a, 0, eta)
        succ += pf * q_succ; cost += pf * C * a
    return succ, cost


def closed_form(pol_name, eta, q):
    """The protocol's stated formulas plus the two symmetric ones they imply."""
    return {'const_0': (HALF, Fr(0)), 'const_1': (HALF, C),
            'observe_F': (HALF + eta * (1 - 2 * q), C / 2), 'observe_not_F': (HALF - eta * (1 - 2 * q), C / 2),
            'oracle_U': (HALF + eta, C / 2)}[pol_name]


def logged_expectations(pol, eta, q, logger):
    """Exact E[IPW] and the exact unweighted mean of matching logged episodes, both for success."""
    ipw = match_mass = match_succ = Fr(0)
    for pr, u, e, f in histories(q):
        target_a = pol(f, u)
        for a in (0, 1):
            pa = logger[f] if a else 1 - logger[f]
            if pa == 0:
                continue
            ps = p_success(a, u, eta)
            if a == target_a:
                ipw += pr * pa * ps / pa
                match_mass += pr * pa; match_succ += pr * pa * ps
    return ipw, (match_succ / match_mass if match_mass else None)


def s(x):
    return None if x is None else dict(exact=str(x), decimal=float(x))


def build():
    cells = []
    for eta, q in itertools.product(ETAS, QS):
        rows = {}
        for name, pol in POLICIES.items():
            se, ce = truth_enumeration(pol, eta, q)
            cf = closed_form(name, eta, q)
            row = dict(success=s(se), cost=s(ce), utility=s(se - ce),
                       enumeration_equals_closed_form=(se, ce) == cf, learnable=name in LEARNABLE)
            if name in LEARNABLE:
                sb, cb = truth_bellman(name, eta, q)
                row['bellman_equals_enumeration'] = (sb, cb) == (se, ce)
                row['loggers'] = {}
                for lname, lg in LOGGERS.items():
                    ipw, naive = logged_expectations(pol, eta, q, lg)
                    row['loggers'][lname] = dict(ipw_expectation=s(ipw), ipw_equals_truth=ipw == se,
                                                 unweighted_matched_mean=s(naive), unweighted_equals_truth=naive == se)
            rows[name] = row
        u0 = Fr(rows['const_0']['utility']['exact'])
        gain = Fr(rows['observe_F']['utility']['exact']) - u0
        if gain != eta * (1 - 2 * q) - C / 2:
            raise AssertionError('utility gain formula fails at eta=%s q=%s' % (eta, q))
        best_fixed = max((Fr(rows[p]['utility']['exact']), p) for p in ('const_0', 'const_1'))
        best_obs = max((Fr(rows[p]['utility']['exact']), p) for p in LEARNABLE)
        cells.append(dict(
            eta=str(eta), q=str(q), c=str(C), policies=rows,
            observe_F_utility_gain_over_const_0=s(gain),
            best_fixed=dict(policy=best_fixed[1], utility=s(best_fixed[0])),
            best_observed_history=dict(policy=best_obs[1], utility=s(best_obs[0])),
            exact_adaptive_advantage=s(best_obs[0] - best_fixed[0]),
            action_effect_present=eta > 0, feedback_informative=q < HALF,
            utility_gain_sign=(gain > 0) - (gain < 0)))
    checks = dict(
        all_bellman_equal_enumeration=all(r['bellman_equals_enumeration'] for c in cells for r in c['policies'].values() if 'loggers' in r),
        all_closed_forms_match=all(r['enumeration_equals_closed_form'] for c in cells for r in c['policies'].values()),
        supported_loggers_ipw_exact=all(r['loggers'][l]['ipw_equals_truth'] for c in cells for r in c['policies'].values()
                                        if 'loggers' in r for l in LOGGERS if not l.startswith('zero_support')),
        zero_support_fails_somewhere=any(not r['loggers']['zero_support_negative_control']['ipw_equals_truth']
                                         for c in cells for r in c['policies'].values() if 'loggers' in r),
        unweighted_fails_somewhere=any(not r['loggers']['state_dependent_floor_0.2']['unweighted_equals_truth']
                                       for c in cells for r in c['policies'].values() if 'loggers' in r),
        truth_independent_of_logger='by construction: truth_enumeration and truth_bellman take no logger argument')
    return dict(
        request='DTR-REQ-003 slice 1: exact analytic control (experiment_protocol_v2.md section 2)',
        status='EXACT rational enumeration; no Monte Carlo, no model; analytic diagnostic, not an agent model or a new theorem',
        model='U~Bern(1/2); F=U xor E, E~Bern(q); P(Y=1|A,U)=1/2+eta(2A-1)(2U-1); cost c*A; one repair decision',
        policies={k: ('F-measurable' if k in LEARNABLE else 'uses latent U: reference only, unavailable to learner') for k in POLICIES},
        loggers={k: {'P(A=1|F=0)': str(v[0]), 'P(A=1|F=1)': str(v[1])} for k, v in LOGGERS.items()},
        checks=checks, cells=cells,
        unresolved=['finite repair generator tables (multi-opportunity, false-pass stopping) not yet specified',
                    'fixed-benchmark block generator and archive-matching branch module not yet specified',
                    'no estimator variance, interval or coverage is addressed by this slice'])


# ---- supplemental development output (lead decision 54e1621); build() and its six-cell artifact stay unchanged ----
OUT_SUPP = Path(__file__).resolve().parent / 'exact_control_supplemental_v1.json'
SUPPLEMENTAL = [(Fr('0.2'), Fr('0.4'))]          # cost-dominated informative cell; c stays .1


def supported(pol, logger):
    """A deterministic F-measurable policy is supported iff the logger gives its action positive probability at every F."""
    return all((logger[f] if pol(f, None) else 1 - logger[f]) > 0 for f in (0, 1))


def ipw_expectations(pol, eta, q, logger):
    """Exact E[IPW] of success, cost and utility (success - cost) over the logger's episode law."""
    out = dict(success=Fr(0), cost=Fr(0), utility=Fr(0))
    for pr, u, e, f in histories(q):
        a = pol(f, u)
        pa = logger[f] if a else 1 - logger[f]
        if pa == 0:
            continue                                   # the matching action is never logged here
        ps = p_success(a, u, eta)
        out['success'] += pr * pa * ps / pa
        out['cost'] += pr * pa * C * a / pa
        out['utility'] += pr * pa * (ps - C * a) / pa
    return out


def build_supplemental():
    cells = []
    for role, grid in (('original', list(itertools.product(ETAS, QS))), ('supplemental_cost_dominated', SUPPLEMENTAL)):
        for eta, q in grid:
            rows = {}
            for name, pol in POLICIES.items():
                se, ce = truth_enumeration(pol, eta, q)
                row = dict(success=s(se), cost=s(ce), utility=s(se - ce), learnable=name in LEARNABLE,
                           enumeration_equals_closed_form=(se, ce) == closed_form(name, eta, q))
                if name in LEARNABLE:
                    sb, cb = truth_bellman(name, eta, q)
                    row['bellman_equals_enumeration'] = (sb, cb) == (se, ce)
                    row['ipw'] = {}
                    for lname, lg in LOGGERS.items():
                        ex = ipw_expectations(pol, eta, q, lg)
                        truth = dict(success=se, cost=ce, utility=se - ce)
                        sup = supported(pol, lg)
                        row['ipw'][lname] = dict(
                            status='supported' if sup else 'UNSUPPORTED: target not identified by IPW under this logger',
                            **{k: dict(expectation=s(ex[k]), equals_truth=ex[k] == truth[k]) for k in truth})
                rows[name] = row
            u = {p: Fr(rows[p]['utility']['exact']) for p in LEARNABLE}
            best_fixed = max((u[p], p) for p in ('const_0', 'const_1'))
            best_class = max((u[p], p) for p in LEARNABLE)
            cells.append(dict(
                role=role, eta=str(eta), q=str(q), c=str(C), policies=rows,
                observe_F_gain_over_const_0=s(u['observe_F'] - u['const_0']),
                best_fixed=dict(policy=best_fixed[1], utility=s(best_fixed[0])),
                best_F_measurable=dict(policy=best_class[1], utility=s(best_class[0])),
                best_class_advantage_over_best_fixed=s(best_class[0] - best_fixed[0])))
    learn_rows = [r for c in cells for r in c['policies'].values() if r['learnable']]
    checks = dict(
        all_bellman_equal_enumeration=all(r['bellman_equals_enumeration'] for r in learn_rows),
        all_closed_forms_match=all(r['enumeration_equals_closed_form'] for c in cells for r in c['policies'].values()),
        supported_ipw_exact_for_success_cost_utility=all(
            r['ipw'][l][k]['equals_truth'] for r in learn_rows for l in LOGGERS
            if r['ipw'][l]['status'] == 'supported' for k in ('success', 'cost', 'utility')),
        unsupported_rows_flagged=sum(r['ipw'][l]['status'] != 'supported' for r in learn_rows for l in LOGGERS),
        best_class_advantage_never_negative=all(Fr(c['best_class_advantage_over_best_fixed']['exact']) >= 0 for c in cells))
    return dict(
        request='DTR-REQ-003: supplemental development output v1 (lead decision 54e1621, theory_feedback_20260921_exact_control.md)',
        status='EXACT rational enumeration; no Monte Carlo, no model. The six-cell artifact exact_control_truth.json is unchanged; '
               'this file adds the supplemental cell and cost/utility IPW expectation checks for all seven cells',
        supplemental_cell='eta=1/5, q=2/5, c=1/10: informative feedback and a real action effect, but benefit below cost',
        loggers={k: {'P(A=1|F=0)': str(v[0]), 'P(A=1|F=1)': str(v[1])} for k, v in LOGGERS.items()},
        checks=checks, cells=cells,
        not_claimed=['no agent-performance model', 'no estimator variance, interval or coverage',
                     'not a change to the real-study utility or the 32-cell core grid'])


def main():
    rep = build()
    if not all(v for k, v in rep['checks'].items() if isinstance(v, bool)):
        raise SystemExit('exact control checks failed: %s' % rep['checks'])
    supp = build_supplemental()
    if not all(v for k, v in supp['checks'].items() if isinstance(v, bool)):
        raise SystemExit('supplemental checks failed: %s' % supp['checks'])
    OUT_SUPP.write_text(json.dumps(supp, indent=1) + '\n')
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    for c in rep['cells']:
        print('eta=%-3s q=%-4s effect=%-5s informative=%-5s gain=%-6s adaptive_adv=%-5s best_obs=%s' % (
            c['eta'], c['q'], c['action_effect_present'], c['feedback_informative'],
            c['observe_F_utility_gain_over_const_0']['exact'], c['exact_adaptive_advantage']['exact'], c['best_observed_history']['policy']))
    print('checks:', {k: v for k, v in rep['checks'].items() if isinstance(v, bool)})


if __name__ == '__main__':
    main()
