"""DTR-REQ-003 item 2: complete fixed-task block specification for the accepted repair kernels. Exact; no Monte Carlo.

Task lists (frozen): n in {250, 1000}; task g = 't%04d' % g has stratum S_g = g mod 2, so exactly n/2 easy and n/2
hard. Tasks within a stratum share the accepted kernel, so each task-specific expectation depends on S_g alone.
Target for a frozen policy pi: theta_n(pi) = (1/n) sum_g V_pi(S_g), the mean of task-specific expectations over the
FIXED list; with exact 50/50 strata this equals the accepted 1/2 : 1/2 mixture (checked, not assumed).

Blocks (specification): in each independent complete study repetition, every task g gets one block of r logged
episodes drawn under the logger with its own randomization and execution stream; task identities never change,
blocks are redrawn. Fresh policy-reference blocks are separate and independent. Estimator used here for the
exact variance calculation: V_hat = (1/n) sum_g mean of the r per-episode trajectory-IPW utilities in block g.

Exact variance (conditional on the fixed list, independent blocks, independent episodes within a block):
    Var(V_hat) = n^-2 sum_g sigma^2(S_g) / r,     sigma^2(S) = E_log[(W Z)^2] - V_pi(S)^2,  Z = utility.
Two variance estimators, by exact expectation:
    within-block replicate  n^-2 sum_g s_g^2 / r       -> unbiased for Var(V_hat) when r >= 2;
    iid-task formula        sample var of task means / n -> Var(V_hat) + sum_g (mu_g - mu_bar)^2 / (n (n-1)),
the second term being between-task spread of EXPECTED values, which is not sampling variability for a fixed list.
Output: experiments/v2_sim/fixed_task_blocks_v1.json
"""
from __future__ import annotations
import hashlib, itertools, json
from fractions import Fraction as Fr
from pathlib import Path

import repair_generator as G
import repair_logger as L

OUT = Path(__file__).resolve().parent / 'fixed_task_blocks_v1.json'
NS = (250, 1000)
R_PROPOSED = 4                                     # logged episodes per task block: a proposal for the lead
CORE_LOGGERS = ('uniform_floor_0.5', 'feedback_dependent_floor_0.2')
POLICIES = ('history_large_after_exception', 'prompt_only_large_if_hard')   # plus the best fixed schedule per cell


def task_list(n):
    tasks = [('t%04d' % g, g % 2) for g in range(n)]
    return tasks, hashlib.sha256('\n'.join('%s,%d' % t for t in tasks).encode()).hexdigest()


def ipw_moments(pol, cell, s, logger):
    """Exact E[W Z] and E[(W Z)^2] for the per-episode trajectory-IPW utility Z = success - total cost."""
    m1, m2 = [Fr(0)], [Fr(0)]

    def term(pr, w, cost, y):
        z = w * (y - cost)
        m1[0] += pr * z; m2[0] += pr * z * z

    term(G.P0[s], Fr(1), G.C[0], 1)

    def rec(t, u, key, last_o, pr, w, cost):
        a = pol.act(s, t, key)
        p1 = logger(s, t, last_o); pa = p1 if a else 1 - p1
        if pa == 0:
            raise ValueError('core loggers must support every catalog policy')
        pr, w, cost = pr * pa, w / pa, cost + G.C[a]
        term(pr * cell.repair[u, a], w, cost, 1)
        for u2 in (0, 1):
            pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
            for o in G.OBS:
                p = pr * (1 - cell.repair[u, a]) * pu * cell.p_obs(o, u2, s)
                if not p:
                    continue
                if o == 'pass' or t == cell.K:
                    term(p, w, cost, 0)
                else:
                    rec(t + 1, u2, pol.update(key, a, o, None), o, p, w, cost)

    for u0 in (0, 1):
        pu0 = (1 - G.P0[s]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s])
        for o0 in G.OBS:
            p = pu0 * cell.p_obs(o0, u0, s)
            if o0 == 'pass':
                term(p, Fr(1), G.C[0], 0)
            elif p:
                rec(1, u0, pol.init_key(s, o0, None), o0, p, Fr(1), G.C[0])
    return m1[0], m2[0]


def s_(x):
    return dict(exact=str(x), decimal=float(x))


def build(r=R_PROPOSED):
    lists = {n: task_list(n) for n in NS}
    kernel = json.loads(G.OUT.read_text())
    cells = []
    for K, crossing, feedback in itertools.product((2, 4), ('no_crossing', 'crossing'), tuple(G.KAPPA)):
        cell = G.Cell(K, crossing, feedback)
        kc = next(c for c in kernel['cells'] if (c['K'], c['action_effect'], c['feedback']) == (K, crossing, feedback))
        names = POLICIES + (kc['best_fixed']['policy'],)
        pols = {p.name: p for p in G.catalog(K) if p.name in names}
        for lname in CORE_LOGGERS:
            lg = L.LOGGERS[lname]
            for pname, pol in pols.items():
                V, sig2 = {}, {}
                for s in (0, 1):
                    truth = G.enumerate_value(pol, cell, s)[0]
                    V[s] = truth['success'] - truth['cost']
                    m1, m2 = ipw_moments(pol, cell, s, lg)
                    if m1 != V[s]:
                        raise AssertionError('IPW first moment differs from truth: %s %s %s' % (cell.K, pname, lname))
                    sig2[s] = m2 - m1 * m1
                for n, (tasks, digest) in lists.items():
                    mus = [V[sg] for _, sg in tasks]
                    theta = sum(mus) / n
                    mix = G.mix(lambda s: V[s])
                    var = sum(sig2[sg] for _, sg in tasks) / (r * n * n)
                    mbar = theta
                    between = sum((m - mbar) ** 2 for m in mus) / (n * (n - 1))
                    cells.append(dict(
                        K=K, action_effect=crossing, feedback=feedback, logger=lname, n=n, r=r, policy=pname,
                        task_list_sha256=digest, target_theta=s_(theta), theta_equals_kernel_mixture=theta == mix,
                        per_episode_ipw_variance={('easy', 'hard')[s]: s_(sig2[s]) for s in (0, 1)},
                        exact_var_V_hat=s_(var), exact_se_V_hat=float(var) ** .5,
                        expected_within_block_estimator=s_(var),
                        expected_iid_task_formula=s_(var + between),
                        iid_formula_excess_between_task=s_(between),
                        iid_formula_se_ratio=float((var + between) / var) ** .5))
    return dict(
        request='DTR-REQ-003 item 2: complete fixed-task block specification (accepted kernels, repair_generator_v1)',
        status='SPECIFICATION with exact moments; no Monte Carlo, no model. r=4 logged episodes per block is a proposal',
        task_lists={n: dict(n=n, easy=n // 2, hard=n // 2, rule="task g = 't%04d' % g, stratum = g mod 2", sha256=lists[n][1])
                    for n in NS},
        target='theta_n(pi) = (1/n) sum_g V_pi(S_g) over the frozen list: the mean of task-specific expectations',
        block='one independent complete block per task per repetition: r logged episodes, own randomization/execution '
              'stream; task identities fixed across repetitions; fresh policy-reference blocks separate and independent',
        estimator='V_hat = (1/n) sum_g (1/r) sum_j W_gj Z_gj, trajectory IPW of utility',
        covariance_assumptions=['blocks independent across tasks within a repetition (no shared execution-period shocks)',
                                'episodes independent within a block given the task',
                                'logging probabilities known and recorded; core loggers support every catalog policy'],
        unresolved=['real execution may share period/server effects across tasks: cross-task covariance terms or a '
                    'justified block model would then be needed; not identifiable from within-block replicates alone',
                    'tasks are identical in law within a stratum here; task-level heterogeneity is a design extension',
                    'normal-approximation coverage for V_hat is not validated by these exact moments',
                    'archive-matching branch module (item 3) not yet specified'],
        rows=cells)


def main():
    rep = build()
    bad = [c for c in rep['rows'] if not c['theta_equals_kernel_mixture']]
    if bad:
        raise SystemExit('target mismatch in %d rows' % len(bad))
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    for c in rep['rows']:
        if c['policy'] == 'history_large_after_exception' and c['K'] == 2:
            print('%-12s %-11s %-29s n=%-5d se=%.5f iid/true se=%.3f' % (
                c['action_effect'], c['feedback'], c['logger'], c['n'], c['exact_se_V_hat'], c['iid_formula_se_ratio']))


if __name__ == '__main__':
    main()
