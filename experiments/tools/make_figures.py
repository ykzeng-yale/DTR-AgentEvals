"""Frontier table and figures for the code-routing study (post-hoc reporting only).

Lives in experiments/tools/, NOT in experiments/code_routing/, because that directory is hashed into every episode's
`code_sha256`: reporting code must never change the experiment's code identity. It reads the frozen artifacts and the
analysis CSVs and writes results/code_routing/analysis/{frontier_live.csv,figures/}.

Palette: validated categorical slots (scripts/validate_palette.js passes on the light surface; the low-contrast
slots are never used alone - every mark is direct-labelled and every number is in the CSVs). Colour follows the
entity across panels: blue = the learned tailored regime, orange = always-large, aqua = stochastic escalation,
yellow = always-small (the pre-registered baseline), grey = the remaining frozen policies.
"""
from __future__ import annotations
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'results' / 'code_routing' / 'analysis'
BLUE, ORANGE, AQUA, YELLOW, GREY = '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#898781'
INK, INK2, MUTED, SURFACE = '#0b0b0b', '#52514e', '#898781', '#fcfcfb'
COLOUR = {'learned': BLUE, 'always_large': ORANGE, 'soft_escalation_d2': AQUA, 'always_small': YELLOW}
SHORT = {'always_small': 'always small', 'always_large': 'always large', 'learned': 'learned (tailored)',
         'soft_escalation_d2': 'soft escalation', 'class_tailored': 'class-tailored', 'escalate_after_first_failure': 'escalate on failure'}


def style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc='left', fontsize=11, color=INK, pad=10, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=9, color=INK2); ax.set_ylabel(ylabel, fontsize=9, color=INK2)
    ax.tick_params(colors=MUTED, labelsize=8.5, length=0)
    ax.grid(color='#e6e5e1', linewidth=0.8); ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)


def frontier() -> pd.DataFrame:
    """Success-cost frontier from the LIVE executions: what each frozen policy actually achieved and spent."""
    import sys
    sys.path.insert(0, str(ROOT / 'experiments' / 'code_routing')); sys.path.insert(0, str(ROOT / 'experiments' / 'common'))
    import common, analysis as A
    cfg = common.load_config()
    live, _ = A.read(common.RESULTS / 'live' / 'episodes.jsonl', cfg)
    rows = []
    for nm in sorted({e['policy'] for e in live}):
        e = [x for x in live if x['policy'] == nm]
        by_task = {}
        for x in e:
            by_task.setdefault(x['task_uid'], []).append(x)
        succ = np.array([np.mean([y['success'] for y in v]) for v in by_task.values()])
        util = np.array([np.mean([y['utility'] for y in v]) for v in by_task.values()])
        rows.append(dict(policy=nm, n_tasks=len(by_task), success=succ.mean(), success_se=succ.std(ddof=1) / np.sqrt(len(succ)),
                         utility=util.mean(), utility_se=util.std(ddof=1) / np.sqrt(len(util)),
                         calls_per_episode=float(np.mean([x['n_decisions'] for x in e])),
                         large_calls_per_episode=float(np.mean([sum(d['a'] for d in x['decisions']) for x in e])),
                         completion_tokens_per_episode=float(np.mean([x['completion_tokens'] for x in e])),
                         llm_wall_seconds_per_episode=float(np.mean([x['llm_wall_seconds'] for x in e]))))
    return pd.DataFrame(rows)


def main():
    cal = pd.read_csv(SRC / 'calibration_ope_vs_live.csv'); cal = cal[cal.outcome == 'utility']
    fr = frontier(); fr.to_csv(SRC / 'frontier_live.csv', index=False)
    fig, ax = plt.subplots(1, 2, figsize=(12.6, 5.0), facecolor=SURFACE)
    fig.subplots_adjust(left=0.07, right=0.97, wspace=0.28, top=0.80, bottom=0.14)

    # ---- panel 1: does the offline estimate match what actually happens?
    style(ax[0], 'Offline estimate vs. what the policy actually did', 'off-policy estimate from ONE shared randomized log',
          'value measured by running the policy')
    lo, hi = 0.56, 0.715
    ax[0].plot([lo, hi], [lo, hi], color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax[0].annotate('perfect agreement', (0.595, 0.595), xytext=(10, -12), textcoords='offset points', fontsize=8, color=INK2, rotation=0)
    OFF1 = {'always_small': (0, -17, 'center'), 'class_tailored': (0, 11, 'center'), 'escalate_after_first_failure': (9, -14, 'left'),
            'soft_escalation_d2': (-9, 8, 'right'), 'always_large': (-9, 9, 'right'), 'learned': (8, -15, 'left')}
    for _, r in cal.iterrows():
        c = COLOUR.get(r.policy, GREY)
        ax[0].errorbar(r.ope_dr, r.live, xerr=1.96 * r.ope_se, yerr=1.96 * r.live_se, fmt='o', color=c, markersize=7,
                       markeredgecolor=SURFACE, markeredgewidth=1.5, elinewidth=1.4, capsize=0, zorder=3)
        dx, dy, ha = OFF1.get(r.policy, (0, 9, 'center'))
        ax[0].annotate(SHORT.get(r.policy, r.policy) + ('' if r.covers_zero else '  (x)'), (r.ope_dr, r.live),
                       xytext=(dx, dy), textcoords='offset points', fontsize=8.5, color=INK, ha=ha)
    ax[0].set_xlim(lo, hi); ax[0].set_ylim(lo, hi)
    ax[0].annotate('(x) = paired difference excludes 0\n1 of 6 policies miscalibrated', (0.5625, 0.7115), fontsize=8, color=INK2,
                   va='top', ha='left')

    # ---- panel 2: the frontier that explains the null
    style(ax[1], 'Success is bought with large-model calls', 'large-model calls per episode (live runs)', 'hidden-test success rate')
    fr = fr.sort_values('large_calls_per_episode')
    ax[1].plot(fr.large_calls_per_episode, fr.success, color=MUTED, linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
    OFF2 = {'always_small': (10, -4, 'left'), 'class_tailored': (-2, 10, 'center'), 'escalate_after_first_failure': (8, -14, 'left'),
            'soft_escalation_d2': (10, -4, 'left'), 'learned': (-10, -6, 'right'), 'always_large': (-6, 9, 'right')}
    for _, r in fr.iterrows():
        c = COLOUR.get(r.policy, GREY)
        ax[1].errorbar(r.large_calls_per_episode, r.success, yerr=1.96 * r.success_se, fmt='o', color=c, markersize=8,
                       markeredgecolor=SURFACE, markeredgewidth=1.5, elinewidth=1.4, capsize=0, zorder=3)
        dx, dy, ha = OFF2.get(r.policy, (10, -4, 'left'))
        ax[1].annotate(SHORT.get(r.policy, r.policy), (r.large_calls_per_episode, r.success), xytext=(dx, dy),
                       textcoords='offset points', fontsize=8.5, color=INK, ha=ha)
    ax[1].set_xlim(-0.12, 1.62); ax[1].set_ylim(0.560, 0.772)
    ax[1].annotate('the learned regime buys the same success with 11% fewer\nlarge-model calls, but does not beat always-large\n(live difference -0.005, 95% CI -0.027 to +0.017)',
                   (1.60, 0.564), fontsize=8.3, color=INK2, va='bottom', ha='right')

    fig.suptitle('Code-routing study · Qwen2.5 3B vs 7B · MBPP + HumanEval · 330 held-out tasks · 4,488 randomized + 3,960 live episodes',
                 x=0.07, ha='left', fontsize=9.5, color=INK2, y=0.955)
    out = SRC / 'figures'; out.mkdir(exist_ok=True)
    fig.savefig(out / 'calibration_and_frontier.png', dpi=170, facecolor=SURFACE)
    fig.savefig(out / 'calibration_and_frontier.svg', facecolor=SURFACE)
    print('wrote', out / 'calibration_and_frontier.png')


if __name__ == '__main__':
    main()
