"""Independent rational reconstruction of REQ-003 slice 1; no worker imports or sampling."""
import hashlib
import itertools
import json
import subprocess
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = '72edb472490532d0d47b2d9444ae44bd788c7107'
SOURCE = 'experiments/v2_sim/exact_control_truth.json'
raw = subprocess.check_output(['git', 'show', f'{REF}:{SOURCE}'], cwd=ROOT)
report = json.loads(raw)
policies = {'const_0': (0, 0), 'const_1': (1, 1), 'observe_F': (0, 1), 'observe_not_F': (1, 0)}
loggers = {'uniform_floor_0.5': (F(1, 2), F(1, 2)),
           'state_dependent_floor_0.2': (F(1, 5), F(4, 5)),
           'zero_support_negative_control': (F(1, 2), F(1))}
checks = 0


def events(eta, q, cost, policy):
    # Enumerate (latent type, observed feedback, outcome); integrate the noise bit out.
    for u, feedback, y in itertools.product((0, 1), repeat=3):
        action = u if policy == 'oracle_U' else policies[policy][feedback]
        mass = F(1, 2) * ((1 - q) if feedback == u else q)
        success = F(1, 2) + (eta if action == u else -eta)
        mass *= success if y else 1 - success
        yield feedback, action, y, cost * action, mass


def truth(eta, q, cost, policy):
    rows = list(events(eta, q, cost, policy))
    assert sum(r[4] for r in rows) == 1
    return tuple(sum(r[4] * value(r) for r in rows) for value in
                 (lambda r: r[2], lambda r: r[3], lambda r: r[2] - r[3]))


def equal(saved, expected):
    global checks
    assert F(saved['exact']) == expected
    assert saved['decimal'] == float(expected)
    checks += 1


for cell in report['cells']:
    eta, q, cost = (F(cell[k]) for k in ('eta', 'q', 'c'))
    computed = {}
    for name, row in cell['policies'].items():
        computed[name] = truth(eta, q, cost, name)
        for field, expected in zip(('success', 'cost', 'utility'), computed[name]):
            equal(row[field], expected)
        if name == 'oracle_U':
            continue
        for lname, prob_one in loggers.items():
            weighted = mass = matched = F(0)
            for feedback, action, y, _, pr in events(eta, q, cost, name):
                p = prob_one[feedback] if action else 1 - prob_one[feedback]
                if p:
                    weighted += pr * p * y / p
                mass += pr * p
                matched += pr * p * y
            saved = row['loggers'][lname]
            equal(saved['ipw_expectation'], weighted)
            equal(saved['unweighted_matched_mean'], matched / mass)
            assert saved['ipw_equals_truth'] == (weighted == computed[name][0])
            assert saved['unweighted_equals_truth'] == (matched / mass == computed[name][0])
    equal(cell['observe_F_utility_gain_over_const_0'], computed['observe_F'][2] - computed['const_0'][2])
    best_fixed = max(computed[p][2] for p in ('const_0', 'const_1'))
    best_observed = max(computed[p][2] for p in policies)
    equal(cell['exact_adaptive_advantage'], best_observed - best_fixed)
    equal(cell['best_fixed']['utility'], best_fixed)
    equal(cell['best_observed_history']['utility'], best_observed)

eta, q, cost = F(1, 5), F(2, 5), F(1, 10)
added = {p: dict(zip(('success', 'cost', 'utility'), map(str, truth(eta, q, cost, p))))
         for p in (*policies, 'oracle_U')}
assert added['observe_F'] == {'success': '27/50', 'cost': '1/20', 'utility': '49/100'}
assert max(F(added[p]['utility']) for p in policies) == F(1, 2)
output = dict(reviewed_commit=REF, source=SOURCE, source_sha256=hashlib.sha256(raw).hexdigest(),
              scope='Independent exact diagnostic; no worker imports, models, Monte Carlo or interval validation',
              cells_checked=len(report['cells']), policies_checked=sum(len(c['policies']) for c in report['cells']),
              exact_numeric_comparisons=checks, all_equal=True,
              additional_development_cell=dict(eta=str(eta), q=str(q), c=str(cost), policies=added,
                  observe_F_gain_over_const_0='-1/100', best_observed_advantage_over_best_fixed='0',
                  status='Lead-approved design extension; not yet added to worker generator/output'))
path = ROOT / 'docs/audits/exact_control_audit_72edb47.json'
path.write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({k: v for k, v in output.items() if k != 'additional_development_cell'}, indent=2))
