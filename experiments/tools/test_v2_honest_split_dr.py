"""Acceptance checks for the honest sample-split DR wiring (lead f4db0f7): cohorts and namespaces, frozen nuisance,
instrumented absence of evaluation-to-training leakage, outcome mutation, manifest guard, an independent per-episode DR
recursion, exact conditional unbiasedness and variance identities by enumeration, and the job wiring on a small block."""
import hashlib, json, math, sys
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dev_batch as D  # noqa: E402
import dr_bridge as DB  # noqa: E402
import honest_split_dr as H  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402

CAT = {p.name: p for p in G.catalog(2)}
SPEC = D.cells()[3]                       # weak feedback, feedback-dependent .2 logger
CELL = G.Cell(2, 'crossing', SPEC['feedback'])
LOGGER = L.LOGGERS[SPEC['logger']]


def small(n=12, seed=7):
    tr, ev, _, _ = H.cohorts(n)
    d = S.SeededDraws(seed)
    lg = dict(logger=LOGGER, logger_name=SPEC['logger'])
    train = S.run_blocks(tr, CELL, 4, d, H.cohort_namespace('t', 0, 'train'), 'log', **lg)
    evalu = S.run_blocks(ev, CELL, 4, d, H.cohort_namespace('t', 0, 'eval'), 'log', **lg)
    return tr, ev, train, evalu


def test_cohorts_are_disjoint_balanced_and_train_is_the_frozen_list():
    import fixed_task_blocks as B
    tr, ev, dt, de = H.cohorts()
    assert tr == B.task_list(250)[0] and dt == B.task_list(250)[1]
    assert not {t for t, _ in tr} & {t for t, _ in ev} and len(ev) == 250
    assert sum(s for _, s in tr) == sum(s for _, s in ev) == 125
    ns = {c: H.cohort_namespace('cfg', 3, c) for c in ('train', 'eval', 'fresh')}
    assert len(set(ns.values())) == 3 and all(v.startswith('cfg=cfg|rep=3|cohort=') for v in ns.values())
    with pytest.raises(ValueError):
        H.cohort_namespace('cfg', 3, 'log')


def test_frozen_nuisance_is_immutable_and_hash_stable():
    tr, ev, train, evalu = small()
    nu = H.fit_frozen_q(train, CAT['fixed_LS'], CELL.K, tr, 4)
    with pytest.raises(TypeError):
        nu.Q[0][next(iter(nu.Q[0]))][0] = 99.0
    with pytest.raises(Exception):
        nu.fallback = ()
    Q, fb = nu.tables(); fb[0][0] = 123.0
    assert H.fit_frozen_q(train, CAT['fixed_LS'], CELL.K, tr, 4).sha256 == nu.sha256
    assert nu.training_tasks == frozenset(t for t, _ in tr) and nu.training_episodes == len(train)


def test_instrumented_no_evaluation_data_enters_fitting(monkeypatch):
    tr, ev, train, evalu = small()
    seen, real_fit = [], H.EA.fit_q
    monkeypatch.setattr(H.EA, 'fit_q', lambda L_, pol, **k: (seen.append(set(L_.task)), real_fit(L_, pol, **k))[1])
    pol = CAT['prompt_only_large_if_hard']
    nu = H.fit_frozen_q(train, pol, CELL.K, tr, 4)
    assert seen == [{t for t, _ in tr}]
    # scoring must never fit or reselect fallbacks
    monkeypatch.setattr(H.EA, 'fit_q', lambda *a, **k: (_ for _ in ()).throw(AssertionError('fit_q called while scoring')))
    H.dr_estimate_and_variance(evalu, pol, CELL.K, nu, ev, 4)
    # evaluation records cannot be passed as training data, and overlapping tasks are refused at scoring
    with pytest.raises(S.ManifestError):
        H.fit_frozen_q(evalu, pol, CELL.K, tr, 4)
    with pytest.raises(H.LeakageError):
        H.episode_scores(train, pol, CELL.K, nu, tr, 4)
    with pytest.raises(TypeError):
        H.episode_scores(evalu, pol, CELL.K, nu.tables(), ev, 4)
    with pytest.raises(ValueError):
        H.episode_scores(evalu, CAT['fixed_LS'], CELL.K, nu, ev, 4)


def test_mutating_evaluation_outcomes_changes_scores_only_through_the_frozen_nuisance():
    tr, ev, train, evalu = small()
    pol = CAT['history_large_after_exception']
    nu = H.fit_frozen_q(train, pol, CELL.K, tr, 4)
    Q, fb = nu.tables()
    mutated = [dict(e, success=1 - e['success'], utility=(1 - e['success']) - e['cost']) for e in evalu]
    for recs in (evalu, mutated):
        # every scored value must equal the definition evaluated with the SAME frozen tables (no refit, no fallback reselection)
        got = H.episode_scores(recs, pol, CELL.K, nu, ev, 4)['score']
        assert np.allclose(got, [independent_dr(e, pol, Q, fb) for e in recs], atol=1e-12, rtol=0)
    b, a = H.dr_estimate_and_variance(evalu, pol, CELL.K, nu, ev, 4), H.dr_estimate_and_variance(mutated, pol, CELL.K, nu, ev, 4)
    assert a['or_plugin'] == b['or_plugin'] and a['estimate'] != b['estimate']   # OR part depends on Q and states only
    assert hashlib.sha256(H._canonical(*nu.tables()).encode()).hexdigest() == nu.sha256   # tables unchanged by scoring


def test_job_level_evaluation_mutation_and_instrumented_fits(monkeypatch):
    spec = dict(SPEC, config='hs-test')
    base = H.job(spec, 0, 99, n=12)
    real_blocks, real_fit, seen = H.S.run_blocks, H.EA.fit_q, []

    def flip_eval(tasks, cell, r, draws, ns, role, **kw):
        out = real_blocks(tasks, cell, r, draws, ns, role, **kw)
        if '|cohort=eval' in ns:
            out = [dict(e, success=1 - e['success'], utility=(1 - e['success']) - e['cost']) for e in out]
        return out
    monkeypatch.setattr(H.S, 'run_blocks', flip_eval)
    monkeypatch.setattr(H.EA, 'fit_q', lambda L_, pol, **k: (seen.append(set(L_.task)), real_fit(L_, pol, **k))[1])
    mut = H.job(spec, 0, 99, n=12)
    train_ids = {t for t, _ in H.cohorts(12)[0]}
    assert seen and all(s == train_ids for s in seen) and len(seen) == len(spec['policies'])
    for name in spec['policies']:
        assert mut['policies'][name]['nuisance_sha256'] == base['policies'][name]['nuisance_sha256']
        assert mut['policies'][name]['dr'] != base['policies'][name]['dr']
        assert mut['policies'][name]['fresh'] == base['policies'][name]['fresh']        # fresh cohort untouched


def test_manifest_guard_rejects_empty_duplicate_and_missing_evaluation_records():
    tr, ev, train, evalu = small()
    pol = CAT['fixed_LS']
    nu = H.fit_frozen_q(train, pol, CELL.K, tr, 4)
    for bad in ([], evalu + [evalu[0]], evalu[:-1]):
        with pytest.raises(S.ManifestError):
            H.dr_estimate_and_variance(bad, pol, CELL.K, nu, ev, 4)


def independent_dr(rec, pol, Q, fb):
    """Per-episode DR written from the definition, not via estimators_absorbing:
    z_pre + V_0 + sum_t W_{0:t} (r_t + V_{t+1} - Q_t(h_t, a_t)), W = prod 1{a = pi(h)} / b, V_t = Q_t(h_t, pi(h_t))."""
    def q(t, key, a):
        return Q[t].get(key, {}).get(a, fb[t][a])
    ds = rec['decisions']
    total = float(DB.z_pre(rec))
    if not ds:
        return total
    keys, acts_pi = [], []
    pkey = pol.init_key(rec['stratum'], rec['observations'][0], None)
    for j, d in enumerate(ds):
        keys.append(DB.state_key(DB.observed_state(rec, j)))
        acts_pi.append(pol.act(rec['stratum'], d['t'], pkey))
        if j + 1 < len(rec['observations']):
            pkey = pol.update(pkey, d['action'], rec['observations'][j + 1], None)
    V = [q(j, keys[j], acts_pi[j]) for j in range(len(ds))] + [0.0]
    total += V[0]
    w = 1.0
    for j, d in enumerate(ds):
        w *= (1.0 if d['action'] == acts_pi[j] else 0.0) / float(d['p_logged'])
        r = -float(G.C[d['action']]) + (rec['success'] if j == len(ds) - 1 else 0)
        total += w * (r + V[j + 1] - q(j, keys[j], d['action']))
    return total


def test_scores_match_an_independent_recursion_and_are_conditionally_unbiased():
    tr, _, _, _ = small()
    fixture = S.run_blocks(H.cohorts()[0], CELL, 4, S.SeededDraws(D.ROOT_SEED), S.stream_namespace(SPEC['config'], 0), 'log',
                           logger=LOGGER, logger_name=SPEC['logger'])
    kernel = json.loads(G.OUT.read_text())
    kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', SPEC['feedback']))
    for name in SPEC['policies']:
        pol = CAT[name]
        nu = H.fit_frozen_q(fixture, pol, CELL.K, H.cohorts()[0], 4)
        Q, fb = nu.tables()
        mean = 0.0
        for s in (0, 1):
            br = H.branches(CELL, s, logger=LOGGER)
            recs = [dict(r, task_id='v%d' % s, replicate=i, stream='v%d|%d' % (s, i)) for i, (_, r) in enumerate(br)]
            got = H.episode_scores(recs, pol, CELL.K, nu, [('v%d' % s, s)], len(recs))['score']
            ind = np.array([independent_dr(r, pol, Q, fb) for r in recs])
            assert np.allclose(got, ind, atol=1e-12, rtol=0)
            mean += 0.5 * sum(float(p) * x for (p, _), x in zip(br, ind))
        assert abs(mean - float(Fr(kc['policies'][name]['utility']['exact']))) < 1e-12


def test_interface_values_match_independent_computations_on_a_cohort():
    tr, ev, train, evalu = small()
    for name in SPEC['policies']:
        pol = CAT[name]
        nu = H.fit_frozen_q(train, pol, CELL.K, tr, 4)
        Q, fb = nu.tables()
        ind = {e['stream']: independent_dr(e, pol, Q, fb) for e in evalu}
        sc = H.episode_scores(evalu, pol, CELL.K, nu, ev, 4)
        assert np.allclose(sc['score'], [ind[e['stream']] for e in evalu], atol=1e-12, rtol=0)
        # separate target / behaviour probabilities are exposed and match the records
        for i, e in enumerate(evalu):
            for j, d in enumerate(e['decisions']):
                assert sc['behaviour_prob'][i, j] == float(d['p_logged']) and sc['eligible'][i, j]
        by = {}
        for e in evalu:
            by.setdefault(e['task_id'], []).append(ind[e['stream']])
        n, r = len(by), 4
        est = sum(sum(v) / r for v in by.values()) / n
        var = sum(sum((x - sum(v) / r) ** 2 for x in v) / (r - 1) for v in by.values()) / (r * n * n)
        out = H.dr_estimate_and_variance(evalu, pol, CELL.K, nu, ev, 4)
        assert math.isclose(out['estimate'], est, rel_tol=0, abs_tol=1e-12) and math.isclose(out['variance'], var, rel_tol=1e-10)


def test_production_variance_is_exactly_unbiased_in_both_strata_given_the_frozen_fit():
    # n = 2 evaluation tasks (one easy, one hard), r = 2. Enumerate every independent PAIR of episodes for one task while the
    # other task holds two identical records (sample variance 0); by linearity the production estimator's expectation is
    # sum_g E[s_g^2] / (r n^2), which must equal the exact Var of the task-equal average, (var_easy + var_hard) / (r n^2),
    # with per-stratum variances computed by the independent recursion, not the code under test.
    tr, _, train, _ = small()
    pol = CAT['fixed_LS']
    nu = H.fit_frozen_q(train, pol, CELL.K, tr, 4)
    Q, fb = nu.tables()
    tasks = [('e', 0), ('h', 1)]
    total, exact = 0.0, 0.0
    for s in (0, 1):
        br = H.branches(CELL, s, logger=LOGGER)
        xs = [(float(p), independent_dr(r, pol, Q, fb)) for p, r in br]
        m1 = sum(p * x for p, x in xs)
        exact += (sum(p * x * x for p, x in xs) - m1 * m1) / (2 * 2 * 2)
        tg, other = tasks[s], tasks[1 - s]
        other_rec = H.branches(CELL, other[1], logger=LOGGER)[0][1]
        fixed = [dict(other_rec, task_id=other[0], replicate=j, stream='%s|%d' % (other[0], j)) for j in range(2)]
        for p, a in br:
            ea = dict(a, task_id=tg[0], replicate=0, stream='%s|0' % tg[0])
            for q, b in br:
                eb = dict(b, task_id=tg[0], replicate=1, stream='%s|1' % tg[0])
                total += float(p) * float(q) * H.dr_estimate_and_variance([ea, eb] + fixed, pol, CELL.K, nu, tasks, 2)['variance']
    assert math.isclose(total, exact, rel_tol=1e-9)


def test_job_wiring_on_a_small_block_is_deterministic_and_reports_training_cost():
    spec = dict(SPEC, config='hs-test')
    a, b = H.job(spec, 0, 99, n=12), H.job(spec, 0, 99, n=12)
    assert a == b
    assert a['training']['episodes'] == 48 and a['training']['model_calls'] >= 48 and a['training']['total_cost'] > 0
    for name in spec['policies']:
        p = a['policies'][name]
        assert all(math.isfinite(p[k]) for k in ('dr', 'dr_var', 'or_plugin', 'fresh', 'fresh_var', 'd', 'd_var'))
        assert math.isclose(p['d_var'], p['dr_var'] + p['fresh_var']) and math.isclose(p['d'], p['dr'] - p['fresh'])


def close_tree(a, b, tol=1e-12, path='$'):
    """Recursive comparison (lead 3f4dfc2): dict keys, list lengths/order and every NON-float value (ids, counts, hashes,
    strings, booleans, ints) must match exactly; floats must agree within abs OR rel 1e-12. Returns a list of problems."""
    if isinstance(a, bool) or isinstance(b, bool) or not (isinstance(a, float) or isinstance(b, float)):
        if isinstance(a, dict) and isinstance(b, dict):
            if list(a) != list(b):
                return ['%s: keys %s != %s' % (path, list(a), list(b))]
            return [x for k in a for x in close_tree(a[k], b[k], tol, '%s.%s' % (path, k))]
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return ['%s: length %d != %d' % (path, len(a), len(b))]
            return [x for i, (u, v) in enumerate(zip(a, b)) for x in close_tree(u, v, tol, '%s[%d]' % (path, i))]
        return [] if (type(a) is type(b) and a == b) else ['%s: %r != %r' % (path, a, b)]
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))) or isinstance(a, bool) or isinstance(b, bool):
        return ['%s: %r != %r' % (path, a, b)]
    d = abs(a - b)
    return [] if (d <= tol or d <= tol * max(abs(a), abs(b))) else ['%s: %r != %r (diff %.3g)' % (path, a, b, d)]


def test_close_tree_accepts_rounding_and_rejects_material_or_metadata_changes():
    import copy
    base = json.loads((H.OUT / 'exact_checks.json').read_text())
    assert close_tree(base, copy.deepcopy(base)) == []
    tiny = copy.deepcopy(base); tiny['rows'][0]['fixtures']['zero_q']['strata']['easy']['variance'] *= (1 + 4e-16)
    assert close_tree(base, tiny) == []                                   # platform-level rounding accepted
    for mutate in (lambda x: x['rows'][0]['fixtures']['zero_q']['strata']['easy'].__setitem__('variance', x['rows'][0]['fixtures']['zero_q']['strata']['easy']['variance'] + 1e-6),
                   lambda x: x['rows'][0]['fixtures']['zero_q'].__setitem__('nuisance_sha256', '0' * 64),
                   lambda x: x['rows'][0]['fixtures']['zero_q']['strata']['easy'].__setitem__('branches', 474),
                   lambda x: x['rows'][0].__setitem__('policy', 'fixed_SS'),
                   lambda x: x['rows'].pop(),
                   lambda x: x['rows'][0]['fixtures'].pop('zero_q')):
        bad = copy.deepcopy(base); mutate(bad)
        assert close_tree(base, bad), 'a material or metadata change was accepted'


def test_exact_check_artifact_regenerates_and_matches_independent_moments():
    committed = json.loads((H.OUT / 'exact_checks.json').read_text())
    out = H.exact_checks()
    problems = close_tree(json.loads(json.dumps(out['rows'])), committed['rows'])
    assert problems == [], problems[:5]
    assert committed['all_conditional_dr_means_exact'] and committed['max_abs_diff_conditional_dr_mean_vs_truth'] <= 1e-12
    assert committed['max_rel_diff_expected_within_task_estimator_vs_exact_variance'] <= 1e-12
    assert len(committed['rows']) == 12 and all(len(r['fixtures']) == 4 for r in committed['rows'])
    ev = H.cohorts()[1]
    for row in committed['rows']:
        spec = next(c for c in D.cells() if c['config'] == row['config'])
        cell, logger, pol = G.Cell(2, 'crossing', spec['feedback']), L.LOGGERS[spec['logger']], CAT[row['policy']]
        Qk, fbk = DB.known_kernel_q(cell, pol)
        f = row['fixtures']['known_q_ORACLE']
        var = {}
        for s, sname in ((0, 'easy'), (1, 'hard')):
            xs = [(float(p), independent_dr(r, pol, Qk, fbk)) for p, r in H.branches(cell, s, logger=logger)]
            m1 = sum(p * x for p, x in xs); m2 = sum(p * x * x for p, x in xs)
            assert math.isclose(f['strata'][sname]['mean'], m1, abs_tol=1e-12)
            assert math.isclose(f['strata'][sname]['second_moment'], m2, rel_tol=1e-12)
            var[s] = m2 - m1 * m1
        want = sum(var[s] for _, s in ev) / (4 * len(ev) ** 2)
        assert math.isclose(f['var_task_equal_average_n250_r4'], want, rel_tol=1e-10)
        assert abs(f['or_plugin_mean'] - row['truth']) < 1e-12
        assert row['fixtures']['bounded_wrong_q']['strata']['hard']['fallback_hit_mass'] > 0   # wrong-Q fallback is exercised
