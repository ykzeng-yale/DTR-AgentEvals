"""DTR-REQ-003 P0: honest sample-split DR inference wiring and exact checks (lead f4db0f7, 18:18 cycle).

An ADDITIONAL honest-split baseline; it does not rebrand or replace the earlier three-fold cross-fitted DR estimator
(dev_batch_dr.py, 8a34f6f) or its results. Reuses experiments/code_routing/estimators_absorbing.py unchanged (fit_q,
dr_scores, weights) through dr_bridge's documented observation map; no latent-U feature is used.

Design (per cell and policy; four K=2 crossing cells, three frozen policies):
  training cohort    250 balanced tasks t0000..t0249 x 4 logged replicates   namespace <ns>|cohort=train
  evaluation cohort  250 DISTINCT balanced tasks t0250..t0499 x 4 logged     namespace <ns>|cohort=eval
  fresh reference    the evaluation tasks x 4 on-policy replicates           namespace <ns>|cohort=fresh
  1. fit ONE observed-history Q per policy on the training cohort only (EA.fit_q), then FREEZE Q, the per-stage fallback
     and the feature map (dr_bridge.state_key) into an immutable FrozenNuisance with a content hash, BEFORE any
     evaluation record is scored;
  2. score every evaluation episode with the frozen nuisance: per-episode DR score = z_pre (common first call, weight 1)
     + EA.dr_scores(...) with separate target and behaviour probabilities exposed; no refit, no fallback reselection;
  3. estimate = task-equal mean of the per-episode scores over the full fixed evaluation manifest;
  4. candidate variance (to be VALIDATED, not asserted): sampler.within_block_variance on those per-episode scores,
     CONDITIONAL on the frozen training fit; the independent fresh variance adds for D = DR - fresh. It must not be
     applied to cross-fitted scores whose training sets overlap the scored tasks.
  Training resource use (episodes, model calls, cost) is reported separately: this is not equal-budget evidence
  against IPW, which uses no training cohort.
Assumptions behind each identity (stated separately):
  - KNOWN, CORRECT logging probabilities: the conditional mean of the DR score equals the policy value for an ARBITRARY
    frozen Q (this centres the estimate on the target);
  - replicates i.i.d. within a task GIVEN the frozen fit (and independent of the training cohort): the within-task
    estimator is unbiased for the conditional variance of the task-equal average of ANY per-episode score; it does not
    use the logging probabilities, and it measures spread about the conditional mean, not about the policy value;
  - CORRECT Q: the OR plug-in mean equals the policy value (known-kernel oracle only).
Arbitrary nuisance or propensity misspecification is NOT covered. Known-kernel Q is an oracle control, labelled
separately, never a fitted nuisance.
  python honest_split_dr.py exact    write the exact-check artifact (no Monte Carlo study, no model)
"""
from __future__ import annotations
import hashlib, json, math, sys
from dataclasses import dataclass
from fractions import Fraction as Fr
from types import MappingProxyType

import numpy as np

import dev_batch as D
import dr_bridge as DB
import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L
import sampler as S

EA = DB.EA
N_TASKS, R_LOG, R_FRESH = 250, 4, 4
OUT = D.ROOT / 'results' / 'v2_sim' / 'honest_split_dr_20260921'
FEATURE_MAP = 'dr_bridge.state_key(observed_state) = (stratum S, stage t, observations so far, earlier actions); no latent U'


def cohorts(n=N_TASKS):
    """Training = the frozen balanced list t0000..t{n-1}; evaluation = n DISTINCT balanced ids t{n}..t{2n-1}."""
    both, _ = B.task_list(2 * n)
    train, evalu = both[:n], both[n:]
    digest = lambda ts: hashlib.sha256('\n'.join('%s,%d' % t for t in ts).encode()).hexdigest()
    return train, evalu, digest(train), digest(evalu)


def cohort_namespace(config, repetition, cohort):
    if cohort not in ('train', 'eval', 'fresh'):
        raise ValueError('cohort must be train, eval or fresh')
    return '%s|cohort=%s' % (S.stream_namespace(config, repetition), cohort)


class LeakageError(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenNuisance:
    """Immutable fitted nuisance: per-stage Q tables {key: {a: value}}, per-stage fallback {a: value}, the feature map
    description, the policy name, the training task ids and a content hash. Built only from training episodes."""
    policy: str
    Q: tuple
    fallback: tuple
    feature_map: str
    training_tasks: frozenset
    training_episodes: int
    missing_q_cells_in_training: int
    sha256: str

    def tables(self):
        return [dict(q) for q in self.Q], [dict(f) for f in self.fallback]


def _canonical(Q, fallback):
    rows = []
    for t, q in enumerate(Q):
        for k in sorted(q, key=repr):
            rows.append([t, repr(k), sorted((int(a), float(v)) for a, v in q[k].items())])
    return json.dumps(dict(Q=rows, fallback=[sorted((int(a), float(v)) for a, v in f.items()) for f in fallback]))


def freeze(Q, fallback, policy_name, training_tasks, n_eps, empty, feature_map=FEATURE_MAP):
    Qp = tuple(MappingProxyType({k: MappingProxyType(dict(v)) for k, v in q.items()}) for q in Q)
    fp = tuple(MappingProxyType(dict(f)) for f in fallback)
    return FrozenNuisance(policy_name, Qp, fp, feature_map, frozenset(training_tasks), n_eps, empty,
                          hashlib.sha256(_canonical(Q, fallback).encode()).hexdigest())


def fit_frozen_q(train_episodes, pol, K, train_tasks, r):
    """Fit on the TRAINING cohort only (manifest-checked), then freeze. Evaluation records cannot be passed here."""
    S.validate_manifest(train_episodes, train_tasks, r)
    L_ = DB.to_logs(train_episodes, K)
    Q, fb, empty = EA.fit_q(L_, DB.prob_policy(pol))
    return freeze([dict(q) for q in Q], fb, pol.name, [t for t, _ in train_tasks], len(train_episodes), empty)


def episode_scores(eval_episodes, pol, K, nuisance, eval_tasks, r):
    """Per-episode DR scores for the evaluation cohort with a FROZEN nuisance (no fitting). Refuses overlap between
    evaluation and training task ids. Returns scores (z_pre + DR part), the OR plug-in V_0 (+ z_pre), and the separate
    per-stage target and behaviour probabilities."""
    if not isinstance(nuisance, FrozenNuisance):
        raise TypeError('scores need a FrozenNuisance fitted on the training cohort')
    if nuisance.policy != pol.name:
        raise ValueError('nuisance was fitted for %s, not %s' % (nuisance.policy, pol.name))
    S.validate_manifest(eval_episodes, eval_tasks, r)
    overlap = {e['task_id'] for e in eval_episodes} & nuisance.training_tasks
    if overlap:
        raise LeakageError('evaluation tasks overlap the training cohort: %s' % sorted(overlap)[:5])
    L_ = DB.to_logs(eval_episodes, K)
    Q, fb = nuisance.tables()
    pp = DB.prob_policy(pol)
    dr, v0 = EA.dr_scores(L_, pp, Q, fb)
    pre = np.array([float(DB.z_pre(e)) for e in eval_episodes])
    return dict(score=pre + dr, or_plugin=pre + v0, pre=pre, target_prob=EA.target_prob_observed(L_, pp), behaviour_prob=L_.b.copy(),
                eligible=L_.elig.copy(), stream=[e['stream'] for e in eval_episodes])


def dr_estimate_and_variance(eval_episodes, pol, K, nuisance, eval_tasks, r):
    """Task-equal DR estimate and the CANDIDATE conditional within-task variance on the per-episode scores."""
    sc = episode_scores(eval_episodes, pol, K, nuisance, eval_tasks, r)
    by_stream = dict(zip(sc['stream'], sc['score']))
    if len(by_stream) != len(eval_episodes):
        raise S.ManifestError('duplicate stream ids in the evaluation cohort')
    dr_by, or_by = {}, {}
    for e, s_, o_ in zip(eval_episodes, sc['score'], sc['or_plugin']):
        dr_by.setdefault(e['task_id'], []).append(s_); or_by.setdefault(e['task_id'], []).append(o_)
    est = float(np.mean([np.mean(v) for v in dr_by.values()]))
    var = float(S.within_block_variance(eval_episodes, lambda e: by_stream[e['stream']], eval_tasks, r))
    return dict(estimate=est, variance=var, or_plugin=float(np.mean([np.mean(v) for v in or_by.values()])))


def training_cost(train_episodes):
    """Training resource use, reported separately (not equal-budget evidence against IPW)."""
    return dict(episodes=len(train_episodes), model_calls=sum(1 + len(e['decisions']) for e in train_episodes),
                total_cost=float(sum(e['cost'] for e in train_episodes)))


def job(cell_spec, b, root_seed, n=N_TASKS):
    """One honest-split repetition for a cell (wiring for a LATER, separately authorized coverage batch; not run here)."""
    cell = G.Cell(2, 'crossing', cell_spec['feedback'])
    train_t, eval_t, _, _ = cohorts(n)
    cat = {p.name: p for p in G.catalog(2)}
    draws = S.SeededDraws(root_seed)
    lg = dict(logger=L.LOGGERS[cell_spec['logger']], logger_name=cell_spec['logger'])
    train = S.run_blocks(train_t, cell, R_LOG, draws, cohort_namespace(cell_spec['config'], b, 'train'), 'log', **lg)
    evalu = S.run_blocks(eval_t, cell, R_LOG, draws, cohort_namespace(cell_spec['config'], b, 'eval'), 'log', **lg)
    rec = dict(config=cell_spec['config'], repetition=b, training=training_cost(train), policies={})
    for name in cell_spec['policies']:
        pol = cat[name]
        nu = fit_frozen_q(train, pol, cell.K, train_t, R_LOG)
        dr = dr_estimate_and_variance(evalu, pol, cell.K, nu, eval_t, R_LOG)
        fresh = S.run_blocks(eval_t, cell, R_FRESH, draws, cohort_namespace(cell_spec['config'], b, 'fresh'), 'fresh', policy=pol)
        fv = float(S.within_block_variance(fresh, lambda e: e['utility'], eval_t, R_FRESH))
        fe = float(S.fresh_estimate(fresh, eval_t, R_FRESH))
        rec['policies'][name] = dict(dr=dr['estimate'], dr_var=dr['variance'], or_plugin=dr['or_plugin'], fresh=fe, fresh_var=fv,
                                     d=dr['estimate'] - fe, d_var=dr['variance'] + fv, nuisance_sha256=nu.sha256,
                                     missing_q_cells_in_training=nu.missing_q_cells_in_training)
    return rec


# ----------------------------------------------------------------------------------------------------------------------
# Exact checks (exhaustive enumeration under the known logging kernels; no Monte Carlo)

def branches(cell, s, logger=None, policy=None):
    return [(p, dict(rec, task_id='x%d' % s, replicate=0)) for p, rec in
            S.exhaustive(lambda d: S.run_episode(cell, s, d, 'x', logger=logger, policy=policy))]


def wrong_q_fixture(K, Qk):
    """SPECIFIED bounded wrong Q: known-kernel Q shifted by -0.25 for the small action and +0.25 for the large action at
    every observed history, and the stage-2 (t=1) entries whose latest observation is 'asr' REMOVED, so those histories
    are scored from the constant fallback {0: -0.2, 1: +0.3}. The fallback-hit probability mass is reported."""
    Qw = [{k: {0: v[0] - 0.25, 1: v[1] + 0.25} for k, v in q.items()} for q in Qk]
    Qw[1] = {k: v for k, v in Qw[1].items() if k[2][-1] != 'asr'}
    return Qw, [{0: -0.2, 1: 0.3} for _ in range(K)]


def fallback_hits(recs, pol, K, nuisance):
    """Per record: True if any value USED by the DR score (Q at the policy action for V, Q at the logged action) is
    missing from the frozen table and therefore comes from the fallback."""
    Q, _ = nuisance.tables()
    pp = DB.prob_policy(pol)
    L_ = DB.to_logs(recs, K)
    hit = np.zeros(len(recs), bool)
    for i, t in zip(*np.nonzero(L_.elig)):
        used = {int(pp(L_.state[i, t])), int(L_.a[i, t])}
        cell_ = Q[t].get(L_.key[i, t], {})
        hit[i] |= any(a not in cell_ for a in used)
    return hit


def conditional_moments(cell, pol, logger, nuisance, eval_tasks=None, r=R_LOG):
    """Exact per-stratum moments of ONE evaluation episode's score given the frozen nuisance, computed THROUGH the
    published interface episode_scores: the enumerated branches of stratum s are one task ('x<s>', s) with one
    replicate per branch. Also: E[OR plug-in], fallback-hit mass, the exact expected within-task sample variance by
    enumeration over independent PAIRS, and, over the evaluation manifest's own strata,
      Var(task-equal average)            = n^-2 sum_g Var_{s_g} / r                 (exact conditional variance)
      E[within_block_variance estimator] = n^-2 sum_g E_pairs[(x - y)^2 / 2] / r    (pair enumeration)."""
    eval_tasks = eval_tasks if eval_tasks is not None else cohorts()[1]
    out = {}
    for s in (0, 1):
        br = branches(cell, s, logger=logger)
        p = np.array([float(q) for q, _ in br])
        recs = [dict(rec, task_id='x%d' % s, replicate=i, stream='x%d|%d' % (s, i)) for i, (_, rec) in enumerate(br)]
        sc = episode_scores(recs, pol, cell.K, nuisance, [('x%d' % s, s)], len(recs))
        x = sc['score']
        m1, m2 = float(p @ x), float(p @ x ** 2)
        pair = float(p @ ((x[:, None] - x[None, :]) ** 2 / 2) @ p)
        out[s] = dict(branches=len(br), prob_sum=float(p.sum()), mean=m1, second_moment=m2, variance=m2 - m1 * m1,
                      expected_pair_sample_variance=pair, or_plugin_mean=float(p @ sc['or_plugin']),
                      fallback_hit_mass=float(p @ fallback_hits(recs, pol, cell.K, nuisance)))
    n = len(eval_tasks)
    var_avg = sum(out[s]['variance'] for _, s in eval_tasks) / (r * n * n)
    e_est = sum(out[s]['expected_pair_sample_variance'] for _, s in eval_tasks) / (r * n * n)
    return out, var_avg, e_est


def exact_checks():
    kernel = json.loads(G.OUT.read_text())
    train_t, eval_t, dt, de = cohorts()
    cat = {p.name: p for p in G.catalog(2)}
    rows = []
    for c in D.cells():
        cell = G.Cell(2, 'crossing', c['feedback'])
        logger = L.LOGGERS[c['logger']]
        kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', c['feedback']))
        # fitted-Q fixture: the EXISTING dev_batch repetition-0 training-list logs (seed 2026092101, unchanged namespace);
        # no new seed. It is frozen once and then treated as a fixed nuisance for the exact conditional checks.
        fixture_log = S.run_blocks(train_t, cell, R_LOG, S.SeededDraws(D.ROOT_SEED), S.stream_namespace(c['config'], 0), 'log',
                                   logger=logger, logger_name=c['logger'])
        for name in c['policies']:
            pol = cat[name]
            truth = float(Fr(kc['policies'][name]['utility']['exact']))
            Qk, fbk = DB.known_kernel_q(cell, pol)
            Qw, fbw = wrong_q_fixture(cell.K, Qk)
            fixtures = dict(
                known_q_ORACLE=freeze(Qk, fbk, name, [], 0, 0),
                zero_q=freeze([dict() for _ in range(cell.K)], [{0: 0.0, 1: 0.0} for _ in range(cell.K)], name, [], 0, 0),
                bounded_wrong_q=freeze(Qw, fbw, name, [], 0, 0),
                fitted_frozen_q_devbatch_rep0=fit_frozen_q(fixture_log, pol, cell.K, train_t, R_LOG))
            res = {}
            for fx, nu in fixtures.items():
                mom, var_avg, e_est = conditional_moments(cell, pol, logger, nu, eval_t, R_LOG)
                mean = (mom[0]['mean'] + mom[1]['mean']) / 2
                res[fx] = dict(conditional_dr_mean=mean, abs_diff_from_truth=abs(mean - truth),
                               or_plugin_mean=(mom[0]['or_plugin_mean'] + mom[1]['or_plugin_mean']) / 2,
                               strata={('easy', 'hard')[s]: mom[s] for s in (0, 1)},
                               var_task_equal_average_n250_r4=var_avg, se_task_equal_average_n250_r4=math.sqrt(var_avg),
                               expected_within_task_estimator_n250_r4=e_est,
                               within_task_estimator_rel_diff=abs(e_est - var_avg) / var_avg,
                               nuisance_sha256=nu.sha256, missing_q_cells_in_training=nu.missing_q_cells_in_training)
            rows.append(dict(config=c['config'], policy=name, truth=truth, fixtures=res,
                             fixture_training=training_cost(fixture_log)))
    return dict(train_digest=dt, eval_digest=de, rows=rows)


def main():
    out = exact_checks()
    tol = 1e-12
    worst = max(f['abs_diff_from_truth'] for r in out['rows'] for f in r['fixtures'].values())
    worst_v = max(f['within_task_estimator_rel_diff'] for r in out['rows'] for f in r['fixtures'].values())
    art = dict(request='DTR-REQ-003 P0 honest sample-split DR wiring and exact checks (lead f4db0f7)',
               kind='EXACT enumeration under the known logging kernels, scored through episode_scores; no Monte Carlo study, no model',
               design=dict(train_tasks='t0000..t0249 (balanced, frozen list)', eval_tasks='t0250..t0499 (distinct, balanced)',
                           replicates=dict(train=R_LOG, eval=R_LOG, fresh=R_FRESH),
                           namespaces="cfg=<config>|rep=<b>|cohort=<train|eval|fresh>|<log|fresh>|<logger or policy>|<task>|<replicate>",
                           feature_map=FEATURE_MAP, pre_decision='z_pre = 1{first_call_pass} - C[0], weight 1',
                           variance_candidate='within-task replicate estimator on evaluation scores CONDITIONAL on the frozen fit; fresh variance additive for D; NOT for overlapping cross-fitted scores'),
               task_list_sha256=dict(train=out['train_digest'], eval=out['eval_digest']),
               fixtures=dict(known_q_ORACLE='exact known-kernel Q (oracle control, not a fitted nuisance)',
                             zero_q='Q = 0 everywhere, fallback 0 (every lookup is a fallback)',
                             bounded_wrong_q="known Q -0.25 (small) / +0.25 (large) on every key; stage-2 keys whose latest observation is 'asr' removed, so they use the fallback {0: -0.2, 1: 0.3}",
                             fitted_frozen_q_devbatch_rep0='EA.fit_q on the existing dev_batch rep-0 log of the 250 training tasks (seed 2026092101, no new seed), frozen'),
               identities_requiring_known_logging_probabilities=[
                   'conditional DR mean equals the policy value for ANY frozen Q (all four fixtures, both strata averaged)'],
               identities_requiring_iid_evaluation_replicates_given_frozen_fit=[
                   'within_block_variance is unbiased for the conditional variance of the task-equal average of ANY per-episode score '
                   '(replicates i.i.d. given the task and the frozen fit, independent of training); it does not use the logging '
                   'probabilities and measures spread about the conditional mean; centring that mean at the policy value additionally '
                   'needs known logging probabilities (or a correct Q)'],
               identities_requiring_correct_q=['OR plug-in mean equals the policy value (known-Q oracle only)'],
               not_covered='arbitrary nuisance or propensity misspecification; finite-sample normal coverage; repeated-training operating characteristics',
               tolerance=tol, max_abs_diff_conditional_dr_mean_vs_truth=worst, all_conditional_dr_means_exact=worst <= tol,
               max_rel_diff_expected_within_task_estimator_vs_exact_variance=worst_v, rows=out['rows'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'exact_checks.json').write_text(json.dumps(art, indent=1) + '\n')
    lines = ['# Honest sample-split DR: exact conditional checks (DTR-REQ-003; lead f4db0f7)', '',
             'Exact enumeration under the known logging kernels, scored through `episode_scores`; no Monte Carlo study. '
             'Max |conditional DR mean − truth| over 4 cells × 3 policies × 4 frozen-Q fixtures: %.1e (tolerance %.0e). '
             'Max relative difference between the enumerated expectation of the within-task variance estimator and the exact '
             'conditional variance of the task-equal average (n=250, r=4): %.1e. Known-Q is an oracle control.' % (worst, tol, worst_v), '',
             '| Cell | Policy | Truth | Fixture | DR mean − truth | OR plug-in mean − truth | Fallback mass easy / hard | Score var easy / hard | SE of task-equal avg (n=250, r=4) |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in out['rows']:
        for fx, f in r['fixtures'].items():
            lines.append('| %s | %s | %.6f | %s | %+.1e | %+.5f | %.4f / %.4f | %.4f / %.4f | %.5f |' % (
                r['config'].replace('K2-crossing-', ''), r['policy'], r['truth'], fx, f['conditional_dr_mean'] - r['truth'],
                f['or_plugin_mean'] - r['truth'], f['strata']['easy']['fallback_hit_mass'], f['strata']['hard']['fallback_hit_mass'],
                f['strata']['easy']['variance'], f['strata']['hard']['variance'], f['se_task_equal_average_n250_r4']))
    (OUT / 'exact_checks.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines[:3]))


if __name__ == '__main__':
    if sys.argv[1:] == ['exact']:
        main()
