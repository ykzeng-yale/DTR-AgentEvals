"""DTR-REQ-003 P0 (lead 64cc65a): consolidated, source-linked K=2 inference evidence table. No reruns and no sampling.

Every number is computed here from a committed artifact read at its IMMUTABLE result commit (`git show <commit>:<path>`),
and every row links to commit-pinned GitHub blobs: the result artifact, its frozen manifest, the worker's recompute
checker (where one exists) and the lead's saved-record audit (resolved from git history). Validation levels:
  W  worker-computed, with a worker recompute/checker where linked;
  A  lead independent saved-record arithmetic audit (script + JSON) — NOT a regeneration of trajectories;
  E  exact/deterministic identity (enumeration under known kernels) — no sampling error;
  R  regeneration of saved streams (bit-for-bit replay) — only where stated, and only for the listed streams.
Development diagnostics are never labelled CONFIRM.
  python evidence_table.py        -> results/v2_sim/evidence_table_20260921.{json,md}
"""
from __future__ import annotations
import json, math, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = 'https://github.com/ykzeng-yale/DTR-AgentEvals/blob'
OUT_JSON, OUT_MD = ROOT / 'results/v2_sim/evidence_table_20260921.json', ROOT / 'results/v2_sim/evidence_table_20260921.md'
Z95 = 1.959963984540054


def git(*a):
    return subprocess.run(['git', '-C', str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def full(commit):
    return git('rev-parse', commit).strip()


def load(commit, path):
    return json.loads(git('show', '%s:%s' % (commit, path)))


def added_in(path):
    """Commit that first added a file (for lead audit links)."""
    out = git('log', '--diff-filter=A', '--format=%H', '--', path).split()
    return out[-1] if out else None


def link(commit, path, label=None):
    return '[%s](%s/%s/%s)' % (label or path.split('/')[-1], REPO, full(commit)[:12], path)


def audit(path):
    c = added_in(path)
    return link(c, path, 'lead audit %s' % c[:7]) if c else 'no dedicated lead audit file'


def rng(vals, fmt='%.4f'):
    return (fmt + '–' + fmt) % (min(vals), max(vals))


def outside(covs, n):
    se = math.sqrt(0.95 * 0.05 / n)
    return sum(1 for c in covs if abs(c - 0.95) > 2 * se)


def rows():
    R = []
    # 1. development batch: IPW vs fresh (point estimation)
    c, p = '35b2f36', 'results/v2_sim/dev_batch_20260921/summary.json'
    s = load(c, p)
    zi = max(abs(r['ipw']['bias'] / r['ipw']['bias_mcse']) for r in s['rows'])
    zf = max(abs(r['fresh']['bias'] / r['fresh']['bias_mcse']) for r in s['rows'])
    sd = [r['ipw']['empirical_sd'] / r['ipw']['exact_sd'] for r in s['rows']]
    R.append(dict(study='Development batch: trajectory IPW vs fresh (point estimation)', cells='4 K=2 crossing cells × 3 policies; n=250, r=4',
                  reps='%d of %d' % (sum(s['complete_repetitions_per_cell'].values()) if isinstance(s['complete_repetitions_per_cell'], dict) else s['complete_repetitions_per_cell'] * 4,
                                     (s['repetitions_requested_per_cell'] * 4)),
                  result='IPW max abs(bias/MCSE) %.2f; fresh %.2f; IPW empirical/exact SD %s; IPW RMSE %s' % (
                      zi, zf, rng(sd, '%.3f'), rng([r['ipw']['rmse'] for r in s['rows']])),
                  adverse='—', validation='W; A; exact SDs E (accepted tables)',
                  links=[link(c, p, 'summary'), link('ffd0e5c', 'results/v2_sim/dev_batch_20260921/manifest.json', 'manifest ffd0e5c'),
                         audit('docs/audits/dev_batch_audit_35b2f36.json')]))
    # 2. cross-fitted DR/OR (point estimation)
    c, p = '8a34f6f', 'results/v2_sim/dev_batch_dr_20260921/summary.json'
    s = load(c, p)
    ratio = [r['dr']['rmse'] / r['ipw']['rmse'] for r in s['rows']]
    orz = [(r['or_plugin']['bias'] / r['or_plugin']['bias_mcse'], r) for r in s['rows']]
    worst = max(orz, key=lambda x: abs(x[0]))
    R.append(dict(study='Original three-fold cross-fitted DR / OR plug-in (point estimation)', cells='same 4 cells × 3 policies; paired logs',
                  reps='%d of %d' % (sum(r['repetitions_complete'] for r in s['rows']) // 3, 800),
                  result='DR max abs(bias/MCSE) %.2f; DR/IPW RMSE %s; known-kernel DR/IPW RMSE %s; OR/IPW RMSE %s' % (
                      max(abs(r['dr']['bias'] / r['dr']['bias_mcse']) for r in s['rows']), rng(ratio, '%.3f'),
                      rng([r['dr_known_kernel']['rmse'] / r['ipw']['rmse'] for r in s['rows']], '%.3f'),
                      rng([r['or_plugin']['rmse'] / r['ipw']['rmse'] for r in s['rows']], '%.3f')),
                  adverse='OR plug-in bias %+.4f (z %.1f) in %s / %s' % (worst[1]['or_plugin']['bias'], worst[0], worst[1]['config'].replace('K2-crossing-', ''), worst[1]['policy']),
                  validation='W; A', links=[link(c, p, 'summary'), link('34abfa6', 'results/v2_sim/dev_batch_dr_20260921/manifest.json', 'manifest 34abfa6'),
                                             audit('docs/audits/dr_batch_audit_8a34f6f.json')]))
    # 3. oracle stage-2 OR diagnostic
    c, p = '7c77c4c', 'results/v2_sim/dev_batch_or_stage2_20260921/summary.json'
    s = load(c, p)
    pz = [(r['paired_difference_oracle_minus_standard']['mean'] / r['paired_difference_oracle_minus_standard']['mcse'], r) for r in s['rows']]
    w = min(pz, key=lambda x: x[0])
    R.append(dict(study='Retrospective oracle stage-2 Q intervention on the fitted OR', cells='same 4 cells × 3 policies; regenerated identical logs',
                  reps='800 of 800 (after documented write-loss recovery)',
                  result='largest paired oracle−standard change %+.4f (z %.1f), %s / %s; oracle OR max abs(z) %.2f' % (
                      w[1]['paired_difference_oracle_minus_standard']['mean'], w[0], w[1]['config'].replace('K2-crossing-', ''), w[1]['policy'],
                      max(abs(r['or_oracle_stage2_error']['mean'] / r['or_oracle_stage2_error']['mcse']) for r in s['rows'])),
                  adverse='supports a stage-2 contribution only; does not isolate fallback; write-loss incident recorded',
                  validation='W; A', links=[link(c, p, 'summary'), link('4927dcb', 'results/v2_sim/dev_batch_or_stage2_20260921/manifest.json', 'manifest 4927dcb'),
                                             link(c, 'results/v2_sim/dev_batch_or_stage2_20260921/incident_20260921.json', 'incident'),
                                             audit('docs/audits/stage2_audit_7c77c4c.json')]))
    # 4. fixed-score coverage
    c, p = 'b2ad9a3', 'results/v2_sim/coverage_fixed_score_20260921/summary.json'
    s = load(c, p)
    cv = {k: [r[k]['wald_coverage'] for r in s['rows']] for k in ('ipw', 'fresh', 'ipw_minus_fresh')}
    R.append(dict(study='Fixed-score coverage: IPW, fresh, IPW−fresh (nominal 95% Wald, within-task variance)', cells='same 4 cells × 3 policies',
                  reps='8,000 of 8,000 (2,000 per cell)',
                  result='coverage IPW %s, fresh %s, IPW−fresh %s; exact-variance IPW %s' % (
                      rng(cv['ipw']), rng(cv['fresh']), rng(cv['ipw_minus_fresh']), rng([r['ipw']['exact_variance_coverage'] for r in s['rows']])),
                  adverse='%d of 36 entries outside 0.95 ± 2 MCSE (IPW studentization shortfall, feedback-dependent logger)' % sum(outside(v, 2000) for v in cv.values()),
                  validation='W (checker); A', links=[link(c, p, 'summary'), link('aac1abb', 'results/v2_sim/coverage_fixed_score_20260921/manifest.json', 'manifest aac1abb'),
                                                       link(c, 'experiments/v2_sim/check_coverage_summary.py', 'checker'),
                                                       audit('docs/audits/coverage_audit_b2ad9a3.json')]))
    # 5. replication sensitivity
    c, p = 'c8a028b', 'results/v2_sim/replication_sensitivity_20260921/summary.json'
    s = load(c, p)
    pf = [r for r in s['rows'] if r['policy'] != 'history_large_after_exception']
    R.append(dict(study='Replication sensitivity: nested r=4 vs r=16 (development)', cells='2 feedback-dependent cells × 3 policies',
                  reps='2,000 of 2,000',
                  result='prompt/fixed_LS IPW coverage r=4 %s → r=16 %s; paired r16−r4 %s' % (
                      rng([r['ipw']['4']['wald_coverage'] for r in pf]), rng([r['ipw']['16']['wald_coverage'] for r in pf]),
                      rng([r['ipw']['paired_r16_minus_r4']['wald_coverage']['mean'] for r in pf], '%+.3f')),
                  adverse='weak/fixed_LS stays below at r=16 (IPW %.3f); tail asymmetry persists; more budget, not a repair' % next(
                      r['ipw']['16']['wald_coverage'] for r in pf if 'weak' in r['config'] and r['policy'] == 'fixed_LS'),
                  validation='W (checker); lead reran worker checker', links=[link(c, p, 'summary'), link('f6f450f', 'results/v2_sim/replication_sensitivity_20260921/manifest.json', 'manifest f6f450f'),
                                                                           link(c, 'experiments/v2_sim/check_replication_sensitivity.py', 'checker')]))
    # 6. saved-record diagnosis + 7. replay
    c, p = 'd45f01d', 'results/v2_sim/replication_sensitivity_20260921/diagnosis_retrospective.json'
    s = load(c, p)
    ent = [r[k] for r in s['rows'] for k in r if k not in ('config', 'policy')]
    R.append(dict(study='Retrospective saved-record diagnosis (MSE, centered variance, tails)', cells='sensitivity records',
                  reps='2,000 (no new data)',
                  result='centered variance/exact %s; skewness > 2 jackknife SE in %d entries (all r=4 IPW/D)' % (
                      rng([e['centered_variance_over_exact'] for e in ent], '%.3f'),
                      sum(1 for e in ent if abs(e['skewness'] / e['skewness_jackknife_se']) > 2)),
                  adverse='right-skewed errors with lower-heavy Wald misses (studentization)', validation='W; A',
                  links=[link(c, p, 'diagnosis'), audit('docs/audits/diagnosis_audit_d45f01d.json')]))
    c, p = '4ad7345', 'results/v2_sim/replay_integrity_20260921/summary.json'
    s = load(c, p)
    r933 = next(r for r in s['replays'] if r['repetition'] == 933)
    R.append(dict(study='Deterministic replay of repetitions 0, 1, 933 (weak/.2/fixed_LS fresh)', cells='3 repetitions',
                  reps='12,000 replayed episodes (no new seed)',
                  result='all regenerated values equal the records (max abs diff %.1e); repetition 933 at %+.2f exact SDs' % (
                      max(cc['abs_diff'] for r in s['replays'] for cc in r['comparisons']), r933['error_r16_exact_sd']),
                  adverse='outlier retained; integrity of these streams only', validation='R (worker); lead checked hashes/comparisons',
                  links=[link(c, p, 'replay summary')]))
    # 8. honest-split exact checks
    c, p = 'de029c0', 'results/v2_sim/honest_split_dr_20260921/exact_checks.json'
    s = load(c, p)
    fitted = [r['fixtures']['fitted_frozen_q_devbatch_rep0']['or_plugin_mean'] - r['truth'] for r in s['rows']]
    R.append(dict(study='Honest sample-split DR wiring: exact conditional identities', cells='4 cells × 3 policies × 4 frozen-Q fixtures',
                  reps='enumeration (no sampling)',
                  result='conditional DR mean − truth ≤ %.1e; expected within-task estimator vs exact conditional variance rel. diff ≤ %.1e' % (
                      s['max_abs_diff_conditional_dr_mean_vs_truth'], s['max_rel_diff_expected_within_task_estimator_vs_exact_variance']),
                  adverse='OR plug-in under fitted frozen Q off by %s' % rng(fitted, '%+.4f'),
                  validation='E; A (portable-comparison repair 4ec6831)', links=[link(c, p, 'exact checks'), audit('docs/audits/honest_split_review_de029c0.json')]))
    # 9. repeated-training coverage
    c, p = 'f532597', 'results/v2_sim/honest_split_coverage_20260921/summary.json'
    s = load(c, p)
    cov = {k: [r[k]['wald_coverage'] for r in s['rows']] for k in ('dr', 'dr_minus_fresh', 'ipw', 'fresh')}
    tr = s['training_resources_per_repetition']
    orz = max(((r['or_plugin_descriptive']['bias'] / r['or_plugin_descriptive']['bias_mcse']), r) for r in s['rows'])
    R.append(dict(study='Honest-split DR, repeated training (Q refitted each repetition)', cells='4 cells × 3 policies',
                  reps='{:,} of {:,}'.format(s['completed'], s['requested']),
                  result='coverage DR %s, DR−fresh %s, paired IPW %s, fresh %s; DR/IPW MSE %s (all 12 < 1)' % (
                      rng(cov['dr']), rng(cov['dr_minus_fresh']), rng(cov['ipw']), rng(cov['fresh']),
                      rng([r['paired_dr_minus_ipw_squared_error']['mse_ratio_dr_over_ipw'] for r in s['rows']], '%.3f')),
                  adverse='DR 1/12 and DR−fresh 2/12 beyond 2 MCSE (informative/.2); OR bias z up to %.1f; training cost %.0f episodes, %.1f model calls, %.2f cost units per repetition (not equal-budget)' % (
                      orz[0], tr['episodes'], tr['model_calls'], tr['total_cost']),
                  validation='W (asserting checker); A', links=[link(c, p, 'summary'), link('4ec6831', 'results/v2_sim/honest_split_coverage_20260921/manifest.json', 'manifest 4ec6831'),
                                                                 link('ff7099a', 'experiments/v2_sim/check_honest_split_coverage.py', 'checker'),
                                                                 audit('docs/audits/honest_split_coverage_f532597.json')]))
    # 10. conditional-moment diagnosis + correction
    c, p = 'ff7099a', 'results/v2_sim/honest_split_conditional_moments_20260921/summary.json'
    s = load(c, p)
    k = load('6ac98b5', 'results/v2_sim/honest_split_conditional_moments_20260921/correction_20260921.json')
    fl = next(r for r in s['rows'] if r['policy'] == 'fixed_LS')
    R.append(dict(study='Per-fit exact conditional moments, informative/.2 (retrospective) + correction', cells='1,000 reconstructed fits × 3 policies',
                  reps='3,000 of 3,000 table hashes matched',
                  result='fixed_LS DR Wald %.3f vs per-fit exact %.3f; DR−fresh prompt/fixed_LS exact %.3f/%.3f; corrected paired-jackknife z max %.2f' % (
                      fl['dr']['wald_coverage']['rate'], fl['dr']['exact_coverage']['rate'],
                      next(r for r in s['rows'] if r['policy'] == 'prompt_only_large_if_hard')['dr_minus_fresh']['exact_coverage']['rate'],
                      fl['dr_minus_fresh']['exact_coverage']['rate'],
                      max(abs(r[x]['jackknife']['exploratory_difference_z']) for r in k['rows'] for x in ('dr', 'dr_minus_fresh'))),
                  adverse='DR−fresh shortfalls not explained by estimated-scale variation; historical z omitted mean-exact randomness (corrected; negligible)',
                  validation='E (per-fit moments); W; A', links=[link(c, p, 'diagnosis'), link('6ac98b5', 'results/v2_sim/honest_split_conditional_moments_20260921/correction_20260921.json', 'correction'),
                                                                   link('6ac98b5', 'results/v2_sim/honest_split_conditional_moments_20260921/per_fit_records.jsonl', 'per-fit records'),
                                                                   audit('docs/audits/conditional_moment_review_ff7099a.json'), audit('docs/audits/conditional_correction_6ac98b5.json')]))
    # 11. fixed-fit conditional coverage
    c, p = '66fb04a', 'results/v2_sim/fixed_fit_coverage_20260921/summary.json'
    s = load(c, p)
    g = lambda key, which: [r[key][which]['rate'] for r in s['rows']]
    R.append(dict(study='Fixed-fit conditional coverage: five frozen fits (training repetitions 0–4)', cells='informative/.2 × 3 policies × 5 fits',
                  reps='{:,} of {:,}'.format(s['completed'], s['requested']),
                  result='Wald (exact-variance) DR %s (%s); DR−fresh %s (%s); fresh control %s (%s); IPW %s (%s)' % (
                      rng(g('dr', 'wald_coverage')), rng(g('dr', 'exact_coverage')), rng(g('dr_minus_fresh', 'wald_coverage')),
                      rng(g('dr_minus_fresh', 'exact_coverage')), rng(g('fresh', 'wald_coverage')), rng(g('fresh', 'exact_coverage')),
                      rng(g('ipw', 'wald_coverage')), rng(g('ipw', 'exact_coverage'))),
                  adverse='IPW Wald %d/15 beyond 2 MCSE; five fits only, no uniform conditional validity' % outside(g('ipw', 'wald_coverage'), 2000),
                  validation='W (asserting checker); A', links=[link(c, p, 'summary'), link('ffef6fd', 'results/v2_sim/fixed_fit_coverage_20260921/manifest.json', 'manifest ffef6fd'),
                                                                 link(c, 'experiments/v2_sim/check_fixed_fit_coverage.py', 'checker'),
                                                                 audit('docs/audits/fixed_fit_66fb04a.json')]))
    return R


PLANNED = [
    'Protocol v2 compact core: 32 cells (n ∈ {250, 1000} × K ∈ {2, 4} × floor {.5, .2} × crossing/no-crossing × informative/weak); only the four n=250, K=2 crossing cells above have sampled inference evidence.',
    'Stress cells (severe overlap, zero support, hidden assignment confounding, non-Markov coarsening, false-pass stopping, execution drift): not run.',
    'Cross-fitted (overlapping-training) DR inference: no justified variance; not claimed.',
    'Learned-policy / policy-selection studies (whole selection refit per repetition): not run.',
    'Branch-study primary target Δ = θ − ν₁ + ν₀: no validated estimate or interval.',
    'Real-agent SWE-bench study (DTR-REQ-002): static qualification only; runtime execution blocked (see REQ-002 status).',
]


def main():
    R = rows()
    OUT_JSON.write_text(json.dumps(dict(request='DTR-REQ-003 P0 consolidated evidence table (lead 64cc65a)', generated_from='immutable commits via git show',
                                        validation_levels=dict(W='worker-computed (+ worker recompute checker where linked)',
                                                               A='lead independent saved-record arithmetic audit (not trajectory regeneration)',
                                                               E='exact/deterministic identity by enumeration', R='regeneration (replay) of the stated streams only'),
                                        rows=R, planned_not_run=PLANNED, label='DEVELOPMENT evidence; nothing here is CONFIRM'), indent=1) + '\n')
    L = ['| # | Study (all DEVELOPMENT; none CONFIRM) | Cells | Repetitions (completed of requested) | Key verified result | Unfavourable / limits | Validation | Immutable links |',
         '|---|---|---|---|---|---|---|---|']
    for i, r in enumerate(R, 1):
        cells = [str(i), r['study'], r['cells'], r['reps'], r['result'], r['adverse'], r['validation']]
        assert not any('|' in x for x in cells), cells   # a bare pipe would break the Markdown table
        L.append('| ' + ' | '.join(cells) + ' | ' + ' · '.join(r['links']) + ' |')
    L += ['', 'Validation levels: **W** worker-computed (with recompute checker where linked); **A** lead independent saved-record '
          'arithmetic audit (not a regeneration of trajectories); **E** exact identity by enumeration; **R** replay of the stated '
          'streams only. No study above was independently rerun from new trajectories by the lead.', '',
          '**Planned protocol scope not yet run:**'] + ['- ' + x for x in PLANNED]
    OUT_MD.write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
