"""Independent exact logger audit using vector masses; no worker code imports or sampling."""
import hashlib
import json
import subprocess
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = 'facd4a87df8af37e22b4df1b36bf579316a0f9ed'


def read(path):
    return subprocess.check_output(['git', 'show', f'{REF}:{path}'], cwd=ROOT)


raw = read('experiments/v2_sim/repair_logger_v2.json')
rep = json.loads(raw)
genraw = read('experiments/v2_sim/repair_generator_v1.json')
gen = json.loads(genraw)
T = gen['tables']
checks = 0


def equal(actual, expected):
    global checks
    assert F(actual) == expected, (actual, expected)
    checks += 1


def calculate(cell, s, policy, logger):
    K = cell['K']
    p0, deep, fp = [F(T[k][str(s)]) for k in ('P0', 'DEEP0', 'FALSE_PASS')]
    kappa = F(T['KAPPA'][cell['feedback']])
    repair = {(u,a): F(T['REPAIR'][cell['action_effect']][f'U{u}_A{a}'])
              for u in (0,1) for a in (0,1)}
    stay = {(u,a): F(1,2) if cell['action_effect'].startswith('U_irrelevant')
            else F(T['STAY_DEEP'][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    cost = [F(T['COST'][str(a)]) for a in (0,1)]
    probabilities = rep['logger_tables'][logger]

    def observe(mass, obs):
        return tuple(mass[u]*(1-fp)*(kappa if (u == 1) == (obs == 'exc') else 1-kappa)
                     for u in (0,1))

    def advance(mass, a):
        failure = [mass[u]*(1-repair[u,a]) for u in (0,1)]
        return (sum(failure[u]*(1-stay[u,a]) for u in (0,1)),
                sum(failure[u]*stay[u,a] for u in (0,1)))

    def action(t, obs):
        if policy.startswith('fixed_'):
            return int(policy[6+t-1] == 'L')
        if policy == 'prompt_only_large_if_hard':
            return s
        if policy == 'history_large_after_exception':
            return int(obs == 'exc')
        assert policy == 'history_S_or_exception'
        return int(s == 1 or obs == 'exc')

    # IPW masses cancel positive logger probabilities; matching masses do not.
    totals = dict(ipw_success=p0, ipw_cost=(p0+(1-p0)*fp)*cost[0],
                  per_decision_cost=cost[0], match_success=p0, match_mass=p0+(1-p0)*fp)
    unsupported = set()

    def rec(t, mass, match, obs, spent):
        a = action(t, obs)
        totals['per_decision_cost'] += sum(mass)*cost[a]
        p1 = F(probabilities['after '+obs]); pa = p1 if a else 1-p1
        if not pa:
            unsupported.add(t)
            return
        match = tuple(x*pa for x in match)
        spent += cost[a]
        success = sum(mass[u]*repair[u,a] for u in (0,1))
        match_success = sum(match[u]*repair[u,a] for u in (0,1))
        nxt, match_nxt = advance(mass,a), advance(match,a)
        term = success + sum(nxt)*(1 if t == K else fp)
        match_term = match_success + sum(match_nxt)*(1 if t == K else fp)
        totals['ipw_success'] += success
        totals['ipw_cost'] += term*spent
        totals['match_success'] += match_success
        totals['match_mass'] += match_term
        if t < K:
            for o in ('exc','asr'):
                rec(t+1, observe(nxt,o), observe(match_nxt,o), o, spent)

    initial = ((1-p0)*(1-deep),(1-p0)*deep)
    for o in ('exc','asr'):
        mass = observe(initial,o)
        rec(1,mass,mass,o,cost[0])

    # Full logger state evolution, independently of target matching.
    reach = [F(0)]*K
    def logger_rec(t, mass, obs):
        reach[t-1] += sum(mass)
        if t == K:
            return
        p1 = F(probabilities['after '+obs])
        for a, pa in ((0,1-p1),(1,p1)):
            nxt = advance(tuple(x*pa for x in mass),a)
            for o in ('exc','asr'):
                logger_rec(t+1,observe(nxt,o),o)
    for o in ('exc','asr'):
        logger_rec(1,observe(initial,o),o)
    return totals, unsupported, reach


supported = final_only = early = rows = 0
for cell, truth_cell in zip(rep['cells'],gen['cells']):
    assert all(cell[k] == truth_cell[k] for k in ('K','action_effect','feedback'))
    for policy, saved in cell['policies'].items():
        truth = truth_cell['policies'][policy]
        y, c = F(truth['success']['exact']), F(truth['cost']['exact'])
        equal(saved['truth_success'],y); equal(saved['truth_cost'],c)
        for logger, row in saved['loggers'].items():
            per = [calculate(cell,s,policy,logger) for s in (0,1)]
            totals = {k: sum(p[0][k] for p in per)/2 for k in per[0][0]}
            times = set.union(*(p[1] for p in per))
            assert sorted(times) == row['unsupported_at_opportunities']
            for key in ('ipw_success','ipw_cost','per_decision_cost'):
                equal(row[key],totals[key])
            standardized = sum(p[0]['match_success']/p[0]['match_mass'] for p in per)/2
            pooled = totals['match_success']/totals['match_mass']
            equal(row['equal_stratum_standardized_matched_mean'],standardized)
            equal(row['pooled_matched_ratio'],pooled)
            for key, actual, target in (
                ('ipw_success_equals_truth',totals['ipw_success'],y),
                ('ipw_cost_equals_truth',totals['ipw_cost'],c),
                ('ipw_utility_equals_truth',totals['ipw_success']-totals['ipw_cost'],y-c),
                ('per_decision_cost_equals_truth',totals['per_decision_cost'],c),
                ('standardized_matched_equals_truth',standardized,y),
                ('pooled_matched_equals_truth',pooled,y)):
                assert row[key] == (actual == target)
            status = 'supported' if not times else 'identified' if times == {cell['K']} else 'UNSUPPORTED'
            assert row['status']['cost'].startswith(status)
            if not times:
                supported += 1
                assert totals['ipw_success'] == y and totals['ipw_cost'] == c and totals['per_decision_cost'] == c
            elif times == {cell['K']}:
                final_only += 1
                assert totals['per_decision_cost'] == c and totals['ipw_cost'] != c
            else:
                early += 1
                assert totals['per_decision_cost'] < c
            for t, value in enumerate(cell['logged_reach_by_logger'][logger]):
                equal(value,sum(p[2][t] for p in per)/2)
            rows += 1

v1 = read('experiments/v2_sim/repair_logger_v1.json')
v1sha = hashlib.sha256(v1).hexdigest()
assert v1sha == '40f7e8d297b514ec005f2970e5df38bebf9454cc19e72d23d2132b3420de734c'
assert (supported,final_only,early) == (348,12,108)
print(json.dumps(dict(reviewed_commit=REF, source_sha256=hashlib.sha256(raw).hexdigest(),
                     generator_sha256=hashlib.sha256(genraw).hexdigest(), preserved_v1_sha256=v1sha,
                     method='Exact latent-vector masses, independently coded; no worker imports',
                     numeric_comparisons=checks, policy_logger_rows=rows, supported_rows=supported,
                     final_only_rows=final_only, earlier_missing_rows=early, all_checks_pass=True,
                     scope='Synthetic first-moment and support checks only; not variance or empirical validation'), indent=2))
