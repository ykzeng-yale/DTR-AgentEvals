"""Post-hoc diagnosis (NOT pre-registered): why did the tailored regime fail to beat always-large?

Three candidate explanations are separated using the frozen randomized log, where the action at each eligible
decision is a fresh coin flip given the history, so within-stratum contrasts are clean randomized effects.

  A. DESIGN      the study leaves a dynamic regime almost nothing to act on.
  B. METRIC      the frozen cost weighting is too light for the tailored regime's only real advantage to register.
  C. THEORY      the framework is wrong about tailoring helping.

Output: results/code_routing/analysis/why_null.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for sub in ('code_routing', 'common', 'dtr'):
    sys.path.insert(0, str(ROOT / 'experiments' / sub))
import common, analysis as A  # noqa: E402


def contrast(eps, stage, key=None, min_arm=10):
    """Randomized large-minus-small contrast at `stage`, optionally within cells. a_t is a coin flip given history."""
    g = {}
    for e in eps:
        k = key(e) if key else 'ALL'
        g.setdefault(k, {}).setdefault(e['decisions'][stage]['a'], []).append(e['success'])
    out = {}
    for k, v in g.items():
        if 0 in v and 1 in v and min(len(v[0]), len(v[1])) >= min_arm:
            a, b = np.array(v[1], float), np.array(v[0], float)
            out[k] = dict(effect=float(a.mean() - b.mean()),
                          se=float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))), n=len(a) + len(b))
    return out


def main():
    cfg = common.load_config()
    log, _ = A.read(common.RESULTS / 'log' / 'episodes.jsonl', cfg)
    conf = [e for e in log if e['split'] == 'confirm']
    r1 = [e for e in conf if e['n_decisions'] >= 2]
    r2 = [e for e in conf if e['n_decisions'] >= 3]
    cellkey = lambda st: (lambda e: '%s|prev=%s' % (e['decisions'][st]['state']['fail_class'],
                                                    'L' if e['decisions'][st - 1]['a'] else 'S'))

    A_design = dict(confirm_episodes=len(conf), reach_second_decision=len(r1), reach_third=len(r2),
                    share_decided_by_first_action_alone=1 - len(r1) / len(conf))
    t1, t2 = contrast(r1, 1), contrast(r2, 2)
    c1, c2 = contrast(r1, 1, cellkey(1)), contrast(r2, 2, cellkey(2))

    # Oracle ceiling: an ORACLE that knew every cell's true sign, versus always-large. Because always-large already
    # takes the large arm everywhere, its only possible gain is in cells where SMALL is better (negative effect).
    def ceiling(cells, reach_share):
        tot = sum(c['n'] for c in cells.values())
        return float(reach_share * sum((c['n'] / tot) * max(0.0, -c['effect']) for c in cells.values()))
    ceil1 = ceiling(c1, len(r1) / len(conf))
    ceil2 = ceiling(c2, len(r2) / len(conf))

    # Metric: at what large-call penalty does the learned regime overtake always-large on live outcomes?
    fr = pd.read_csv(common.RESULTS / 'analysis' / 'frontier_live.csv').set_index('policy')
    L, B = fr.loc['learned'], fr.loc['always_large']
    dS = float(L.success - B.success)
    lgL, lgB = float(L.large_calls_per_episode), float(B.large_calls_per_episode)
    smL, smB = float(L.calls_per_episode) - lgL, float(B.calls_per_episode) - lgB
    coef = (lgB + smB / 3) - (lgL + smL / 3)          # keeping the frozen small:large ratio of 1:3
    flip = (-dS) / coef if coef else float('nan')

    out = dict(
        status='POST-HOC diagnosis, not pre-registered; uses the frozen log only, after all stages completed',
        A_design=dict(**A_design,
                      oracle_tailoring_ceiling_over_always_large_t1=ceil1,
                      oracle_tailoring_ceiling_over_always_large_t2=ceil2,
                      study_policy_value_se_approx=0.024,
                      reading='an oracle that knew every cell sign could beat always-large by at most this much; '
                              'compare with the study SE. In-sample and therefore optimistic.'),
        B_metric=dict(frozen_large_call_penalty=cfg['call_penalty']['large'], live_success_difference=dS,
                      large_calls_learned=lgL, large_calls_always_large=lgB,
                      flip_point_large_call_penalty=flip, flip_multiple_of_frozen=flip / cfg['call_penalty']['large'],
                      reading='the tailored regime buys fewer large calls at a small success cost; whether that is a '
                              'net gain is decided entirely by a cost weighting fixed before any data, with no '
                              'sensitivity analysis pre-registered or run'),
        C_theory=dict(effect_at_t1=t1.get('ALL'), effect_at_t2=t2.get('ALL'),
                      cells_t1=c1, cells_t2=c2,
                      stage_gradient=dict(
                          difference=float(t2['ALL']['effect'] - t1['ALL']['effect']),
                          se=float(np.sqrt(t1['ALL']['se'] ** 2 + t2['ALL']['se'] ** 2))),
                      reading='tailoring can only help where the effect VARIES with the state. Within a stage the '
                              'cells are mutually indistinguishable; across stages there is a suggestive gradient.'))
    (common.RESULTS / 'analysis' / 'why_null.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
