"""Deterministic saved-record algebra audit; no experiment imports or random draws.

The quantities called scales below are square roots of empirical squared task
ratio derivatives. This script makes no claim about their sampling variance,
confidence coverage, or whether the cross-product estimates a covariance.
"""
import argparse
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    root = args.repo or next(p for p in Path(__file__).resolve().parents
                             if (p / 'pyproject.toml').exists() and (p / 'results/code_routing').is_dir())
    ref = '29ee443cc3ba1d00bb7f37e90f8a8915e2a9357c'
    sources = {name: subprocess.check_output(['git', 'show', f'{ref}:results/code_routing/{name}'], cwd=root)
               for name in ('log/episodes.jsonl', 'branch/episodes.jsonl',
                'branch/branch_plan.json', 'analysis/branch_vs_log_linearized.json')}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}
    def read(stage):
        rows = [json.loads(s) for s in sources[stage + '/episodes.jsonl'].splitlines()]
        assert len({e['episode_id'] for e in rows}) == len(rows), 'duplicate completed episode'
        assert all(not e.get('error') for e in rows), 'unexpected recorded error'
        return rows
    log = [e for e in read('log') if e['split'] == 'confirm']
    branch = read('branch')
    plan = json.loads(sources['branch/branch_plan.json'])
    assert {e['episode_id'] for e in branch} == {e['episode_id'] for e in plan['episodes']}
    tasks = sorted({e['task_uid'] for e in log})
    per = defaultdict(lambda: defaultdict(list)); task_of = {}
    for e in branch:
        pid = e['parent_episode_id']; task_of[pid] = e['task_uid']
        per[pid][e['fork_arm']].append(e['success'])
    assert len(per) == 200
    assert all(set(d) == {'small', 'large'} and all(len(v) == 2 for v in d.values()) for d in per.values())
    A = {t: 0.0 for t in tasks}; M = {t: 0 for t in tasks}
    for pid, d in per.items():
        t = task_of[pid]
        A[t] += math.fsum(d['large']) / 2 - math.fsum(d['small']) / 2
        M[t] += 1
    N = {a: {t: 0.0 for t in tasks} for a in (0, 1)}
    D = {a: {t: 0.0 for t in tasks} for a in (0, 1)}
    eligible = [e for e in log if e['n_decisions'] >= 2]
    for e in eligible:
        ds = e['decisions']; arm = ds[1]['a']
        weight = 2.0 if len(ds) == 2 else (4.0 if ds[2]['a'] == arm else 0.0)
        N[arm][e['task_uid']] += weight * e['success']
        D[arm][e['task_uid']] += weight
    m = sum(M.values()); bs = math.fsum(A.values()); B = bs / m
    Ns = {a: math.fsum(N[a].values()) for a in (0, 1)}
    Ds = {a: math.fsum(D[a].values()) for a in (0, 1)}
    v = {a: Ns[a] / Ds[a] for a in (0, 1)}
    L = v[1] - v[0]; difference = B - L
    ub = {t: (A[t] - B * M[t]) / m for t in tasks}
    ul = {t: (N[1][t] - v[1] * D[1][t]) / Ds[1]
              - (N[0][t] - v[0] * D[0][t]) / Ds[0] for t in tasks}
    u = {t: ub[t] - ul[t] for t in tasks}
    qb = math.fsum(x*x for x in ub.values()); ql = math.fsum(x*x for x in ul.values())
    cross = math.fsum(ub[t] * ul[t] for t in tasks)
    joint = math.fsum(x*x for x in u.values())
    assert abs(joint - (qb + ql - 2*cross)) < 1e-16
    def reweighted_difference(t, step):
        weighted_b = (bs + step*A[t]) / (m + step*M[t])
        weighted_v = {a: (Ns[a] + step*N[a][t]) / (Ds[a] + step*D[a][t]) for a in (0, 1)}
        return weighted_b - (weighted_v[1] - weighted_v[0])
    eps = 1e-5
    derivative_error = max(abs((reweighted_difference(t, eps) - reweighted_difference(t, -eps))/(2*eps)-u[t]) for t in tasks)
    assert len(tasks) == 330 and len(eligible) == 564
    assert derivative_error < 1e-9 and abs(math.fsum(u.values())) < 1e-12
    reported = json.loads(sources['analysis/branch_vs_log_linearized.json'])
    assert abs(math.sqrt(joint) - reported['linearized_se']) < 1e-14
    assert abs(difference - reported['difference']) < 1e-14
    result = {
        'reviewed_checkpoint': '29ee443', 'input_sha256': hashes,
        'scope': 'Independent standard-library parsing and deterministic ratio algebra only. No model/candidate-code execution, random sampling, bootstrap, or Monte Carlo.',
        'n_confirm_tasks': len(tasks), 'n_eligible_prefixes': len(eligible), 'n_selected_prefixes': m,
        'n_tasks_with_branch': sum(M[t] > 0 for t in tasks),
        'n_tasks_with_any_positive_log_arm_denominator': sum(any(D[a][t] > 0 for a in (0, 1)) for t in tasks),
        'n_tasks_with_both_positive_log_arm_denominators': sum(all(D[a][t] > 0 for a in (0, 1)) for t in tasks),
        'branch_estimate': B, 'log_arm_numerators': Ns, 'log_arm_denominators': Ds,
        'log_estimate': L, 'difference': difference,
        'sum_branch_derivatives': math.fsum(ub.values()), 'sum_log_derivatives': math.fsum(ul.values()),
        'sum_joint_derivatives': math.fsum(u.values()), 'central_difference_max_error': derivative_error,
        'sum_squared_branch_derivatives': qb, 'sum_squared_log_derivatives': ql,
        'sum_branch_log_derivative_crossproducts': cross,
        'sum_squared_joint_derivatives': joint,
        'branch_square_root_scale': math.sqrt(qb), 'log_square_root_scale': math.sqrt(ql),
        'same_method_scale_omitting_crossproduct': math.sqrt(qb+ql),
        'same_method_scale_including_crossproduct': math.sqrt(joint),
        'reported_scale': reported['linearized_se'],
        'interpretation': 'The positive cross-product is an observed algebraic quantity; it is not asserted to consistently estimate a sampling covariance. The square-root quantities are derivative scales, not validated standard errors. No confidence interval is asserted. Fixed-size prefix sampling, task/frame target, execution assumptions and an asymptotic or finite-sample variance argument remain to be specified. Dependence or replicate averaging alone does not disprove possible unconditional sandwich validity.',
        'historical_comparison_caveat': 'The earlier 0.0572 combined a branch cluster calculation and a separate log bootstrap. Its difference from the current scale cannot be attributed solely to subtracting the same-method cross-product.',
    }
    output = args.output or root / 'work/branch_linearization_independent_29ee443.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
