"""Figure for the design-efficiency simulation (reads results/sim/, writes results/sim/figures/).

Palette: validated categorical slots 1-4 (scripts/validate_palette.js: all checks pass on the
light surface; aqua and yellow are below 3:1 contrast, so every series is direct-labelled,
has its own marker shape, and the numbers are in results/sim/summary_table.csv).
Colour follows the entity across panels: blue = one sequentially randomized experiment,
orange = one arm per scaffold, aqua = forked replay, yellow = best fixed scaffold.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'results' / 'sim'
BLUE, ORANGE, AQUA, YELLOW = '#2a78d6', '#eb6834', '#1baf7a', '#eda100'
INK, INK2, MUTED, SURFACE = '#0b0b0b', '#52514e', '#898781', '#fcfcfb'


def style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc='left', fontsize=10.5, color=INK, pad=10, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=9, color=INK2); ax.set_ylabel(ylabel, fontsize=9, color=INK2)
    ax.set_xscale('log'); ax.set_xticks([300, 600, 1200, 2400, 4800]); ax.set_xticklabels(['300', '600', '1,200', '2,400', '4,800'])
    ax.minorticks_off(); ax.tick_params(colors=MUTED, labelsize=8.5, length=0)
    ax.grid(axis='y', color='#e6e5e1', linewidth=0.8); ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)


def line(ax, x, y, color, marker, label, dy=0.0, va='center'):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ax.plot(x, y, color=color, linewidth=2, marker=marker, markersize=6.5, markeredgecolor=SURFACE, markeredgewidth=1.5, clip_on=False)
    ax.annotate(label, (x[-1], y[-1]), xytext=(8, dy), textcoords='offset points', fontsize=8.5, color=INK, va=va)


def main():
    d = pd.read_csv(SRC / 'replicates.csv'); m = json.loads((SRC / 'manifest.json').read_text())
    truth = m['truth']; keys = list(truth); best = max(truth, key=truth.get); ns = sorted(d.n.unique())
    g = d.groupby('n')
    rmse = lambda est: [float(np.sqrt(np.nanmean(np.array([g.get_group(n)['%s_%s' % (est, k)] - truth[k] for k in keys]) ** 2))) for n in ns]
    tab = pd.DataFrame(dict(n=ns, rmse_smart_aipw=rmse('aipw'), rmse_smart_ipw=rmse('ipw'), rmse_one_arm_per_scaffold=rmse('conv'),
                            regret_smart=g.aipw_pick_regret.mean().to_numpy(), regret_one_arm=g.conv_pick_regret.mean().to_numpy(),
                            value_best_fixed_picked=g.v_aipw_pick.mean().to_numpy(), value_qlearned=g.v_qlearn.mean().to_numpy(),
                            value_qlearned_forked=g.v_qlearn_fork.mean().to_numpy(),
                            p_qlearned_beats_best_fixed=[float((g.get_group(n).v_qlearn > truth[best]).mean()) for n in ns],
                            contrast_rmse_randomized=[float(np.sqrt(((g.get_group(n).s4_rand - m['s4_truth']) ** 2).mean())) for n in ns],
                            contrast_rmse_forked=[float(np.sqrt(((g.get_group(n).s4_fork - m['s4_truth']) ** 2).mean())) for n in ns]))
    tab['value_best_fixed_truth'] = truth[best]; tab['value_oracle_tailored'] = m['oracle_value']
    tab.to_csv(SRC / 'summary_table.csv', index=False)

    fig, ax = plt.subplots(1, 3, figsize=(15.5, 4.3), facecolor=SURFACE)
    fig.subplots_adjust(left=0.05, right=0.90, wspace=0.62, top=0.80, bottom=0.15)
    style(ax[0], 'Error in each scaffold\'s estimated value', 'total episodes in the evaluation', 'RMSE over 12 scaffolds')
    line(ax[0], ns, tab.rmse_one_arm_per_scaffold, ORANGE, 's', 'one arm per\nscaffold', dy=14)
    line(ax[0], ns, tab.rmse_smart_aipw, BLUE, 'o', 'one randomized\nexperiment (AIPW)', dy=-12)
    ax[0].set_ylim(0, 0.095)

    style(ax[1], 'True value of the regime you end up deploying', 'episodes in the randomized experiment', 'expected utility (known truth)')
    ax[1].axhline(m['oracle_value'], color=MUTED, linewidth=1, linestyle=(0, (4, 3))); ax[1].axhline(truth[best], color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax[1].annotate('oracle tailored regime', (ns[0], m['oracle_value']), xytext=(0, 4), textcoords='offset points', fontsize=8, color=INK2)
    ax[1].annotate('best fixed scaffold (truth)', (ns[-1], truth[best]), xytext=(0, 4), textcoords='offset points', fontsize=8, color=INK2, ha='right')
    line(ax[1], ns, tab.value_qlearned_forked, AQUA, '^', 'tailored, learned\nfrom forked replay', dy=12)
    line(ax[1], ns, tab.value_qlearned, BLUE, 'o', 'tailored, learned\nfrom randomization', dy=-14)
    line(ax[1], ns, tab.value_best_fixed_picked, YELLOW, 'D', 'fixed scaffold\npicked from data', dy=-4)
    ax[1].set_ylim(0.715, 0.772)

    style(ax[2], 'Error in a rescue-action contrast, equal compute', 'compute budget (randomized-episode equivalents)', 'RMSE of escalate − repair')
    line(ax[2], ns, tab.contrast_rmse_randomized, BLUE, 'o', 'randomize\none arm', dy=14)
    line(ax[2], ns, tab.contrast_rmse_forked, AQUA, '^', 'fork: replay all\narms from state', dy=-12)
    ax[2].set_ylim(0, None)

    fig.suptitle('Synthetic coding-agent simulator with known truth · 1,000 Monte Carlo replicates per point · NOT real model output',
                 x=0.05, ha='left', fontsize=9.5, color=INK2, y=0.965)
    out = SRC / 'figures'; out.mkdir(exist_ok=True)
    fig.savefig(out / 'design_efficiency.png', dpi=170, facecolor=SURFACE); fig.savefig(out / 'design_efficiency.svg', facecolor=SURFACE)
    print(tab.round(4).to_string(index=False))


if __name__ == '__main__':
    main()
