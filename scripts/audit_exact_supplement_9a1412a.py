"""Read-only independent rational check of the seven-cell supplement; no worker imports or sampling."""
import hashlib
import json
import subprocess
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = '9a1412a258df86a117b8f19defb467e8566ca5dc'
SOURCE = 'experiments/v2_sim/exact_control_supplemental_v1.json'
raw = subprocess.check_output(['git', 'show', f'{REF}:{SOURCE}'], cwd=ROOT)
rep = json.loads(raw)
policies = {'const_0': (0, 0), 'const_1': (1, 1), 'observe_F': (0, 1), 'observe_not_F': (1, 0)}
loggers = {'uniform_floor_0.5': (F(1, 2), F(1, 2)),
           'state_dependent_floor_0.2': (F(1, 5), F(4, 5)),
           'zero_support_negative_control': (F(1, 2), F(1))}
checks = unsupported = coinciding_cost = 0


def equal(saved, expected):
    global checks
    assert F(saved['exact']) == expected
    assert saved['decimal'] == float(expected)
    checks += 1


for cell in rep['cells']:
    eta, q, cost = (F(cell[k]) for k in ('eta', 'q', 'c'))
    utilities = {}
    for name, row in cell['policies'].items():
        if name == 'oracle_U':
            values = (F(1, 2) + eta, cost / 2, F(1, 2) + eta - cost / 2)
        else:
            # Integrate latent U analytically at each observed feedback value.
            rewards = [(F(1, 2) + eta * (2*a-1) * (2*f-1) * (1-2*q), cost*a)
                       for f, a in enumerate(policies[name])]
            values = (sum(x[0] for x in rewards)/2, sum(x[1] for x in rewards)/2,
                      sum(x[0]-x[1] for x in rewards)/2)
            for lname, probabilities in loggers.items():
                support = [bool(probabilities[f] if a else 1-probabilities[f])
                           for f, a in enumerate(policies[name])]
                expected = (sum(rewards[f][0] for f in (0, 1) if support[f])/2,
                            sum(rewards[f][1] for f in (0, 1) if support[f])/2,
                            sum(rewards[f][0]-rewards[f][1] for f in (0, 1) if support[f])/2)
                saved = row['ipw'][lname]
                assert (saved['status'] == 'supported') == all(support)
                for k, val, target in zip(('success', 'cost', 'utility'), expected, values):
                    equal(saved[k]['expectation'], val)
                    assert saved[k]['equals_truth'] == (val == target)
                if not all(support):
                    unsupported += 1
                    coinciding_cost += expected[1] == values[1]
                    assert expected[0] != values[0] and expected[2] != values[2]
            utilities[name] = values[2]
        for k, val in zip(('success', 'cost', 'utility'), values):
            equal(row[k], val)
    best_fixed = max(utilities[p] for p in ('const_0', 'const_1'))
    best_class = max(utilities.values())
    equal(cell['best_fixed']['utility'], best_fixed)
    equal(cell['best_F_measurable']['utility'], best_class)
    equal(cell['observe_F_gain_over_const_0'], utilities['observe_F']-utilities['const_0'])
    equal(cell['best_class_advantage_over_best_fixed'], best_class-best_fixed)
assert len(rep['cells']) == 7 and unsupported == coinciding_cost == 14
original = subprocess.check_output(['git', 'show', f'{REF}:experiments/v2_sim/exact_control_truth.json'], cwd=ROOT)
assert hashlib.sha256(original).hexdigest() == '5efc714f8323acf7d65df60016ca086a5ae0a4dfeb43bbfe28acf9628df0afb6'
result = dict(reviewed_commit=REF, source=SOURCE, source_sha256=hashlib.sha256(raw).hexdigest(),
              scope='Independent conditional-mean rational reconstruction; no worker imports, model, Monte Carlo or inference validation',
              cells=7, policy_values=35, numeric_comparisons=checks, all_equal=True,
              unsupported_policy_logger_rows=unsupported, unsupported_rows_with_equal_cost=coinciding_cost,
              interpretation='Known zero cost on the unsupported action makes its omitted cost contribution zero; success and utility still fail.',
              original_six_cell_sha256=hashlib.sha256(original).hexdigest())
(ROOT/'docs/audits/exact_supplement_audit_9a1412a.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
