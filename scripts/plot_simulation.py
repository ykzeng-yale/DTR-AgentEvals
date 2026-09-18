#!/usr/bin/env python3
"""Plot the archived pilot summaries; no refitting or regenerated results."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parents[1]
base = json.loads((root / "results/simulation/summary.json").read_text())
policies = ["always_small", "always_large", "fixed_switch", "failure_escalation", "soft_escalation"]
labels = ["Small", "Large", "Fixed switch", "Error rule", "Soft error rule"]
methods = [("ipw", "IPW", "#176B93"), ("dr", "DR", "#B45B35")]
fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), layout="constrained")
for method, title, color in methods:
    rows = [next(r for r in base if r["policy"] == p and r["method"] == method and r["q_spec"] == "correct" and r["behavior"] == "known") for p in policies]
    axes[0].plot(range(5), [r["rmse"] for r in rows], marker="o", label=title, color=color)
    axes[1].errorbar(range(5), [r["coverage_95"] for r in rows], yerr=[1.96*r["coverage_mc_se"] for r in rows], marker="o", capsize=3, label=title, color=color)
axes[0].set(title="Value error", ylabel="RMSE")
axes[1].set(title="Pointwise interval coverage", ylabel="Coverage probability", ylim=(.83, 1.01))
axes[1].axhline(.95, color="#555555", linestyle="--", linewidth=1)
for ax in axes[:2]:
    ax.set_xticks(range(5), labels, rotation=28, ha="right")
    ax.legend(frameon=False)
for policy, label, color in [("always_small", "Always small", "#176B93"), ("soft_escalation", "Soft error rule", "#B45B35")]:
    ess = []
    for folder in ["simulation", "stress_h6_n1500", "stress_h8_n1500"]:
        diag = json.loads((root / f"results/{folder}/diagnostics.json").read_text())
        vals = [r["ess_by_stage"][-1] / 1500 for r in diag if r["policy"] == policy and r["q_spec"] == "correct" and r["behavior"] == "known"]
        if not vals:
            raise ValueError(f"No archived diagnostic rows for {folder}/{policy}")
        ess.append(np.mean(vals))
    axes[2].plot([3, 6, 8], ess, marker="o", label=label, color=color)
axes[2].set(title="Effective sample size", xlabel="Horizon (joint stress settings)", ylabel="Mean final ESS / 1,500", ylim=(0, 1))
axes[2].legend(frameon=False)
for ax in axes:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.18)
fig.suptitle("Synthetic pilot: valid routing probabilities; no language-model performance claim", fontsize=13)
fig.supxlabel("Left/middle: 400 replicates, n=1,500, T=3; bars are Monte Carlo uncertainty. Right: T=6/8 also change overlap.", fontsize=9)
out = root / "results/figures"
out.mkdir(parents=True, exist_ok=True)
fig.savefig(out / "simulation_overview.png", dpi=180)
fig.savefig(out / "simulation_overview.svg")
print(out / "simulation_overview.png")
