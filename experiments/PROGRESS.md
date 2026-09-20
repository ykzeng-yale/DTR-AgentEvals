# Progress log — experiments workstream

Pushed about every two hours while experiments run. Newest entry first. Interim entries for the log/live stages give
counts, error rates and timing only; outcomes by arm are not looked at before a stage is complete.

## 2026-09-20 04:50 EDT — scheduled check: static-replay comparator closed, and it is a null

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn. No runner alive, both llama-servers
healthy on 8191/8193, no foreign llama-server generating at any episode start.

**Closed a comparator that had been open for four ticks** (`experiments/tools/static_replay.py`), CPU-only on the
frozen log — the failure control required by `docs/experiment_protocol.md` §3.3 and framed by `docs/theory.md` §7.1.
Two exactly specified rules: **A** hold-the-future-fixed (relabel the action, keep the recorded outcome) and **B**
prefix-matched donor stitching (take the target's action, splice the continuation from the same task's logged episode
sharing that action prefix, smallest run index winning).

| estimator | mean abs. error vs live (5 deterministic policies) | Spearman vs live |
|---|---:|---:|
| Rule A, hold-the-future-fixed | 0.032 | constant, undefined |
| Rule B, prefix-matched stitching | **0.0161** | 0.880 |
| Cross-fitted DR | **0.0182** | 0.886 |

**The failure control did not fail.** Static stitching was not detectably worse than doubly robust estimation here —
nominally slightly better. That is a null against the expectation the protocol sets up, and it is reported straight.
Two design features explain it and bound how far it travels: success is absorbing and **78.6% of episodes stop after
one decision**, so stitching engages for only about a fifth of them and there is little future to get wrong; and with
8 episodes per task covering all action prefixes, a well-matched same-task donor always existed (0 tasks lacked one).
Replay should still be expected to fail with longer horizons, sharper post-switch state divergence, or cross-task
donors — regimes this study does not exercise. So this does not license replay in general; it cautions against
citing its invalidity as automatic in short-horizon, densely-replicated designs.

**A limitation of my own rule, stated rather than hidden:** Rule B reads the target deterministically, so a
stochastic target collapses to its modal action. `soft_escalation_d2` is misrepresented by it (error +0.036, the
largest in the table) and is excluded from the aggregate with its row retained.

**Problems:** none in the data. 62 tests pass; all three stages verify unchanged.

**Next:** the joint-inference derivation under a stated target/source-frame model using the new fixed-frame sampling
proposition; the competitive published router baseline; the remaining gate items (reject missing reference data
rather than skipping the membership check, match retained decisions on episode+invocation+attempt+stage, a recovery
ledger with a positive recovery fixture, parent-hash recomputation, host-writer exclusion, atomic snapshot);
independent reproduction from immutable inputs; manuscript integration.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
one required comparator is now executed and reported, which is genuine new analysis of existing records rather than
new collection — but it closes a *control*, not a milestone, and its result is a null that narrows rather than
extends what the study can claim. Categories unchanged at 75/75/50/50/25, weighted 58.75 → 60%. I am not raising
"core evidence" on the strength of a comparator whose main contribution is to qualify an expectation, while the
competitive-router baseline, joint inference and independent reproduction all remain open. Main remaining work:
(1) joint branch/log inference under a stated sampling model, and the competitive-router baseline;
(2) independent reproduction of numerical summaries from immutable inputs; (3) manuscript integration and packaging.
*This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint is
recorded here.*

## 2026-09-20 02:50 EDT — scheduled check: third review round; claims aligned, gate widened

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn records. No runner alive, both
llama-servers healthy on 8191/8193, no foreign llama-server generating. Contention is reported as **a per-episode
check at each episode's start, not continuous observation of the host** — a wording correction, since the earlier
"zero foreign GPU load" phrasing claimed more than the records support.

**A factual error of mine, corrected.** The deterministic targets' positive-support range is **317–325**, not the
317–330 I published: the two stochastic targets reach all 330 and I had folded them into the deterministic range.

**Claims aligned to evidence** after `docs/theory_feedback_20260920_sampling.md`. Removed: headings saying the two
routes "agree" or that evaluation is "cheaper"; the assertion that one validation timeout cannot have moved a result;
"miscalibrated"/"calibrated" framing in favour of pointwise compatibility at this sample size, which is neither a
coverage nor an equivalence statement. The branch band [−0.109, +0.080] is now labelled an **exploratory algebraic
band pending a sampling justification**, and nothing is inferred from its including zero. The cross-product point is
accepted too: the archived 0.0572 is a marginal bootstrap quantity, so the like-for-like comparison inside the same
linearization is **0.0484 against 0.0587**. Figure titles are descriptive and the branch annotation now sits clear of
the error bars; the previous version is preserved.

**Publication gate widened.** An independent audit of the previous gate found **14 defect classes still accepted**,
and correctly noted that my `test_false_restoration_flag_fails` actually tested a *missing parent with true flags*.
Both fixed. The gate now also fails on: false **or absent** restoration evidence on an analysed branch row; a branch
row with no parent or naming a parent that is not a completed log episode; required frozen hashes absent or null as
well as wrong; a seed differing from the frozen design/plan; missing or empty `decisions.jsonl`; missing, empty or
torn `run_manifest.jsonl`; durable decisions with a null/absent invocation or one absent from the manifest; and
durable decisions whose recorded action disagrees with the episode's own record. Fixtures went from 9 to **22**,
including a genuinely False restoration flag with the missing-parent case kept separate. **62 tests pass** and the
three real stages still verify unchanged.

**Deliberately not attempted:** the design-aware branch variance. `docs/theory_branch_sampling.md` (the conditional
proof I had asked for) landed in the same commit as this review; using it properly means stating the finite-frame
versus population target, the source-frame model and the continuation assumptions, then deriving and checking the
combined variance. Rushing that in a scheduled tick is how the previous two errors happened, so it is deferred and
the band stays labelled exploratory. Also still open: actual-host writer exclusion (a clone cannot attest remote
process liveness), an atomic publication snapshot, parent transcript-hash recomputation, a rejected-record ledger,
and the competitive-router and static-replay comparators.

**Problems:** none new in the data. The pattern worth naming is that three consecutive review rounds each found real
errors in my reporting — a factual range, an estimand substitution, and an overstated gate. The data collection has
held up; the claims about it needed external checking, which is an argument for keeping independent validation open.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
none that the rubric counts — no new episodes, no new estimand, no closed comparator. This tick corrected published
claims and widened an integrity gate, which protects evidence rather than adding it. Categories unchanged at
75/75/50/50/25, weighted 58.75 → 60%, matching the theory workstream's checkpoint. Main remaining work:
(1) design-aware branch variance from the new sampling note, plus the competitive-router and static-replay
comparators; (2) independent reproduction of numerical summaries from immutable inputs; (3) manuscript integration
and the submission package. *This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the
experiment host), so the checkpoint is recorded here.*

## 2026-09-20 00:45 EDT — scheduled check: second review round; my own "fix" was wrong and is repaired

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn records. No runner alive, both
llama-servers healthy on 8191/8193, **no foreign llama-server generating** — contention stayed 0 for the whole study.
Calls attached to retained completions: **13,001** (log + live + branch), **13,164** including the pilot; both
exclude the executions lost in the publishing incident and environment-construction calls, so neither is the total
physical cost.

**The theory workstream reviewed my previous correction and it was itself wrong.** Its new
`docs/theory_feedback_20260920_branch.md` shows that my "linkage fix" **changed the estimand** rather than the
variance: restricting to 42 tasks and re-weighting them equally moved the difference from −0.0147 to −0.0914, and it
decomposes the shift (pooled −0.0147 → original weighting on 42 tasks −0.0567 → equal-task weighting −0.0914). A
variance correction must leave the difference alone. Accepted in full.

**Target-preserving repair implemented** (`experiments/tools/branch_linkage_linearized.py`): pooled estimators and
**all 330 source tasks** retained, so the difference stays **−0.014654**; the influence identity supplied in the
review is used for its uncertainty and verified numerically by central differences over every source-task multiplier
(Σ U_g = 7×10⁻¹⁸, max error 3.8×10⁻¹¹). Result: SE **0.0484**, interval **[−0.109, +0.080]** — *tighter* than the
0.0572 independence implies, because the linkage is positive. Labelled a first-order approximation: it does not
account for without-replacement sampling of 200 of 564 prefixes, within-prefix replication, or cross-task selection
dependence. The 42-task version is retained and marked exploratory.

**Other accepted corrections:** ESS now described as overlap, not cost; the 2.19 precision ratio no longer presented
as equal-compute or as replication of the synthetic result, and stated to exclude prefix acquisition and lost-run
overhead; the 8% figure is a sample statistic over 400 pairs, not a noise bound; restoration described as evidence
about recorded hash and tool-result fields, not universal replayability; the third figure panel now annotates the
difference of the two estimates it actually plots, with the previous version preserved as
`calibration_and_frontier_v2_20260920.png`; protocol §11 no longer asserts the incident "could not affect inference"
and instead states the loss/recovery and execution-stability assumptions, and records the 1,439 durable branch rows
(1,434 retained + 5 orphans, `attempt=1` reused across invocations).

**Gate hardened.** `verify_stage.py` now **fails** rather than prints on a torn tail, duplicate completed rows,
frozen-metadata drift, a restoration flag claimed without a recorded parent, durable decisions lacking an invocation
id, and orphan decisions. Nine fixtures in `experiments/tools/test_verify_stage.py` prove each check fails on its
defect and that the three real stages still pass. **Not done:** refusing publication from a checkout that cannot
attest the writer's liveness on the actual host.

**Problems:** the substantive one is above — I published a correction that silently re-targeted an estimand, and it
took an external review to catch it. That is the second time this cycle that review caught an error of mine, which is
an argument for the independent-audit item remaining open rather than closed by self-assessment.

**Overall submission readiness: about 60% (change: −5 percentage points; judgment range 50–65%).** Evidence advanced:
none new; this tick repaired analysis. I am **lowering** my own score and adopting the theory workstream's 60%:
"Core simulations and real-agent evidence" goes back from 75 to 50 because a published inference correction was
itself defective and the branch comparison still lacks a design-aware interval, so the category is not "most
delivered with only integration left". Categories 75/75/50/50/25, weighted 58.75 → 60%. Main remaining work:
(1) design-aware branch variance and the missing comparators (competitive router baseline, static replay);
(2) independent reproduction of numerical summaries from immutable inputs; (3) manuscript integration and packaging.
*This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint is
recorded here.*

## 2026-09-20 00:10 EDT — scheduled check: pipeline complete, review corrections applied

**Stage status: nothing to advance.** All stages of the frozen pipeline are finished and verified against the frozen
design (`experiments/tools/verify_stage.py`): pilot 120, log **4,488/4,488**, live **3,960/3,960**, branch
**800/800**; 0 unresolved, 0 intention-to-treat scorings, 0 torn records. No stage runner is alive; both
llama-servers are healthy on 8191/8193; **no foreign llama-server is generating**, so contention remains 0 across
every stage. Total 13,001 model calls, 1 validation timeout, 0 hidden-test timeouts, 3 truncated generations.

**This tick did analysis corrections, not collection.** The theory workstream published
`docs/theory_feedback_20260920.md`. Its findings were checked against the data and **four were my errors**:

1. **Improvement claim overstated.** Only six of nine frozen policies ran live, so only those six can satisfy a rule
   requiring a live contrast. It is met by `always_large`, `learned`, `soft_escalation_d2`. I had also listed
   `large_then_small` and `soft_escalation_d4`, which have **no live data at all**. Corrected.
2. **Figure defect.** The success panel annotated the *utility* difference (−0.005) rather than the success
   difference (−0.008 [−0.029, +0.014]), and fixed axis limits clipped the calibration error bars. Both fixed.
3. **Equivalence wording.** "Same success, 11% fewer calls" implies equality that a null does not establish;
   the live success interval admits either policy being better by ~0.03. Reworded as a failure to detect.
4. **Cost conflation.** The 3,662 calls that support all nine policies are the CONFIRM portion; the whole log cost
   6,063 calls including 2,401 TRAIN calls spent on policy learning. Both figures now stated.

**One correction changed a scientific conclusion.** The review asked for branch/log linkage to be accounted for. The
published branch-minus-log difference assumed independence, but branch prefixes are drawn from the same confirm
episodes and per-task estimates correlate at **r = 0.54**. A paired task-clustered recomputation on the 42 tasks
where both are estimable gives **−0.091, 95% CI [−0.208, +0.025]** instead of −0.015 [−0.127, +0.098]. It still
covers zero, but it is wider in implication, so the claim is downgraded from "two independent routes agree" to
"compatible, and not shown to be equal". Restoration evidence is unaffected and now covers the full cohort:
**800/800** transcript hashes and tool results reproduced exactly.

Replies are recorded in `docs/experiment_handoff.md`; corrections are itemised in `docs/experiment_results.md`.

**Problems:** none new. The earlier publishing incident (protocol §11) is closed: the re-run completed and all
stages verify.

**Next:** items that need no new collection — a competitive published router baseline and an explicit static-replay
comparator (issue #3), independent reproduction of the numerical summaries from immutable inputs, and manuscript
integration. None are claimed as done.

**Overall submission readiness: about 65% (change: 0 percentage points; judgment range 55–70%).** Evidence advanced:
none that the rubric counts — this tick corrected published analysis and reporting rather than producing new
evidence, and two of the corrections weakened previously published claims. Category scores are unchanged at
75/75/75/50/25 (weighted 66.25 → 65%). The theory workstream independently scored 60% at its 02:53 UTC checkpoint
before the completed branch cohort and these corrections were visible to it; the difference is a scoring judgment
between workstreams on "core evidence", not a factual dispute, and that workstream owns the rubric. Main remaining
work: (1) integrate reviewed results and limitations into the manuscript; (2) add the missing comparators and an
independent reproduction from immutable inputs; (3) finish reproducibility and submission packaging.
*This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint is
recorded here.*

## 2026-09-19 23:10 EDT — STUDY COMPLETE (log + live + branch); two corrections accepted from review

**All four stages executed and verified against the frozen design** (`experiments/tools/verify_stage.py`):
pilot 120, randomized log **4,488/4,488**, live **3,960/3,960**, branch **800/800** — 0 unresolved episodes,
0 intention-to-treat scorings, 0 torn records, 0 episodes under foreign GPU load. 13,001 model calls in total,
1 validation timeout, 0 hidden-test timeouts, 3 truncated generations. Committed at `f984f15`.

### Findings

1. **The evaluation claim holds.** Off-policy values from ONE randomized log matched what the policies did when
   actually run: 5 of 6 paired differences cover zero, Spearman 0.886, SE ratio 0.91–1.07. One policy
   (`class_tailored`) is miscalibrated (−0.037 [−0.070, −0.005]) and is reported as a failure cell.
2. **The improvement claim fails where it counts.** Five policies beat the pre-registered `always_small` baseline,
   but the learned tailored regime does **not** beat simply always using the large model: utility +0.018
   [−0.016, +0.051] offline and **−0.005 [−0.027, +0.017]** live. Success is close to monotone in large-model calls
   and every frozen policy sits on that line. The learned regime gets the same success with 11% fewer large calls —
   cheaper, not better. **This null is the headline.**
3. **Forking works, and transfers from simulation.** 800/800 restorations reproduced the saved state exactly
   (transcript hash and tool result). Forked replay and the randomized log agree on the same causal contrast
   (0.120 vs 0.135, difference −0.015 [−0.127, +0.098]), with forking **2.19× more precise using 39% of the calls**.
   The synthetic study predicted 2.1–2.3×; the real system delivered 2.19×.
4. **The design earns its keep.** Naive association −0.484; IPW with a deliberately wrong propensity returns 2.015
   on success, outside [0, 1]. Same-state same-model continuations disagree 8.0% — the serving-noise floor.

### Corrections accepted from the theory workstream's independent review

It audited the committed snapshot and was right on three counts, all now fixed: the wrong-propensity control is on
**success** not utility; the IPW/DR/g-computation disagreement reaches 0.0167 on success rather than staying under
0.016; and **Theorem 5 is not merely vacuous here but inapplicable as computed** — it assumes nuisances fitted on
data independent of the evaluation sample, which cross-fitting *within* CONFIRM does not supply. It is now reported
as a scale calculation, not a certificate. Its fourth finding — that only 135 of 800 branch continuations were in
that snapshot — was also correct; see below.

### Incident (retained, not repaired silently)

665 of the first 800 branch continuations were **lost by an operator error in publishing**: the stage directory was
`git add`-ed, committed and rebased while the runner still held its files open, so writes went to an unlinked inode
and the runner reported "800/800, errors 0" and exited 0. They were re-run from the frozen plan with the same seeds.
The lost outcomes were never readable, so no selection on outcome was possible. Protocol §11 records it.
`experiments/tools/verify_stage.py` now gates publication: it checks episodes **on disk** against the frozen design
rather than trusting the runner's counter, and refuses a stage whose runner is live or whose file was just written.
Verified retrospectively that `log` and `live` were idle before they were committed and are intact.

### Next

Manuscript integration of these results; a competitive published router baseline and an explicit static-replay
comparator (issue #3); shared-prefix variance treatment in the branch analysis; independent audit of the new code.

**Overall submission readiness: about 65% (change: +5 percentage points; judgment range 55–70%).** Evidence
advanced and independently reviewed: all four real-model stages completed and verified, with the improvement result
a reported null and two analysis errors corrected by external review. "Core simulations and real-agent evidence"
50→75: known-truth operating characteristics, the randomized log, fresh-policy validation and branch validation all
exist with limitations and nulls reported; still missing are a competitive published router baseline, a static-replay
comparator and shared-prefix variance handling. "Independent validation" stays at 50: the theory workstream reviewed
the results and found real errors, but the experiment code, protocol adherence and final analysis have not had a full
audit — and this workstream should not grade its own. Weighted: 0.25×75 + 0.20×75 + 0.30×75 + 0.15×50 + 0.10×25 =
66.25 → 65%. Main remaining work: (1) integrate results, figures and limitations into the manuscript; (2) add the
missing comparators and shared-prefix variance treatment; (3) independent audit and the submission package.
*Checkpoints are recorded here because this host has no GitHub CLI or token for issue #4.*

## 2026-09-19 18:00 EDT — randomized log COMPLETE; policy frozen; live stage running

**Stage `log`: finished, 4,488 of 4,488 episodes.** 0 infrastructure errors, 0 episodes owing a retry, 0
intention-to-treat scorings, 0 validation or hidden-test timeouts, 0 truncated generations, 0 sandbox hack flags,
0 episodes begun under foreign GPU load. 6,063 model calls, 517,326 completion tokens, 2.28 s per episode, 11.2
agent-hours over 4 workers. All 561 train+confirm tasks covered. Assignment balance at t=0 was 0.508 large against
0.500 by design. Committed at `035d245`.

**Learned policy frozen** (`learned_policy.json`, sha256 `4f22e7b4…`, recorded in protocol §9), fitted-Q on the 231
TRAIN tasks only, pushed **before** any live episode. It is genuinely tailored rather than a fixed scaffold:

| pre-action state | action |
|---|---|
| first attempt | large |
| after an **assertion** failure by the **small** model | escalate to large |
| after an **assertion** failure by the **large** model | fall back to small |
| after an **exception** failure at t=1 | small |

i.e. it alternates rather than repeating the model that just failed. Whether that helps is exactly what the
confirmatory analysis will decide; **no outcome by arm has been inspected.**

**Stage `live`: running.** 3,960 fresh executions of six frozen policies (always-small, always-large,
escalate-after-first-failure, class-tailored, soft-escalation δ=2, learned) on the 330 confirm tasks, 2 runs each.
2.45 s per episode, ETA ≈ 160 min (finish ≈ 20:45 EDT). 0 errors so far.

**Housekeeping:** one TRAIN episode's traceback contained the host interpreter path (a `RecursionError` inside the
standard library). The host prefix is masked as `<HOME>` — 4 occurrences, one episode, no numeric field touched —
and recorded in `results/code_routing/redactions.json`. The tool refuses confirm-split episodes, whose stored traces
the branch audit rehashes, and lives outside the directories hashed into `code_sha256`.

**Problems:** none. **Next:** `analysis.py --calibration` (offline vs live, paired by task), then the branch audit
(800 continuations, ≈0.5 h), then `--ope`, `--branch`, `--ops` and the write-up.

**Overall submission readiness: about 60% (change: +10 percentage points; judgment range 50–60%).** Evidence
advanced, and *inspectable* rather than merely started: the randomized log is complete with its raw episode and
pre-action decision records committed, and the learned policy is frozen and published before the validation it will
be judged by. Scoring "Core simulations and real-agent evidence" 25→50: two of its three components now exist
(known-truth operating characteristics from `results/sim` and `results/s1_grid`; the real-agent randomized log),
while fresh-policy validation and the branch audit are outstanding and **no outcome has been analysed**. Weighted:
0.25×75 + 0.20×75 + 0.30×50 + 0.15×50 + 0.10×25 = 58.75 → 60%. Main remaining work: (1) complete live-policy
validation and the branch audit and report their outcomes including nulls; (2) integrate validated results and
limitations into the manuscript; (3) independent audit of the new experiment code, protocol adherence and analysis.
*This is the experiments workstream scoring its own category; the theory agent owns `docs/readiness.md` and may
re-score. Checkpoints are recorded here because this host has no GitHub CLI or token for issue #4.*

## 2026-09-19 16:20 EDT — randomized log 44% done, no errors

**Stage:** `log` (frozen design `cb9481d`). **1,974 of 4,488 episodes**, **0 infrastructure errors**, 0 episodes
owing a retry. 2.26 s per episode; ETA about 96 min (finish ≈ 17:55 EDT). 555 of 561 tasks touched so far;
train 804 / confirm 1,170 episodes.

**Operational only — no outcomes by arm are looked at before the stage completes.**

| quantity | value |
|---|---:|
| model calls / completion tokens | 2,661 / 225,049 |
| decisions per episode (1 / 2 / 3) | 1,590 / 81 / 303 → P(t=1 eligible) 0.195, P(t=2) 0.153 (pilot: 0.225 / 0.133) |
| truncated generations, validation timeouts, hidden-test timeouts, hack flags | 0, 0, 0, 0 |
| episodes begun under foreign GPU load / failed contention checks | 0 of 1,974 / 0 |
| mean call latency (uncontended, so interpretable) | small 4.26 s, large 8.90 s |
| assignment balance at t=0 (design check, not an outcome) | 0.508 large vs 0.500 by design |

**GPU sharing:** still sole occupant. The sibling ICLR project has committed only documents today and has not
started inference; it did finish downloading a coder model, so contention may begin at any time. Every episode
carries `foreign_gpu_load_at_start`, and the runner pauses before an episode while another server is generating.
(Note for anyone reading process lists: this project's two servers run the llama-server *binary* from the sibling's
scratchpad directory, so they look like sibling processes; ownership is by port — 8191 and 8193 are this project's.)

**Problems:** none. **Next:** on completion — `analysis.py --learn`, freeze and push `learned_policy.json`, then
the live stage (3,960 episodes, ≈2.5 h), calibration, branch audit (≈0.5 h).

**Overall submission readiness: about 50% (change: 0 percentage points; judgment range 45–60%).** Evidence
advanced: none that the rubric counts — the randomized log is *running*, and `docs/readiness.md` explicitly says not
to count an experiment's runtime fraction as its scientific completion fraction, so "Core simulations and real-agent
evidence" stays at 25% until confirmatory results exist and are inspected. Main remaining work: (1) complete the
randomized log, live-policy validation and branch audit, and report their outcomes including nulls; (2) integrate
validated results and limitations into the manuscript; (3) independent audit of the new experiment code, protocol
adherence and analysis. *(Scoring rubric added by the theory agent in `docs/readiness.md` at `8041a0e`; it asks for
checkpoints in GitHub issue #4, which this workstream cannot post to — no GitHub CLI or token on the experiment
host — so checkpoints are recorded here instead.)*

## 2026-09-19 15:10 EDT — design FROZEN (`cb9481d`); randomized log running

**Stage:** `log` — 4,488 pre-drawn episodes on 561 train + confirm tasks. 50 done at the time of writing, 0 errors,
2.8 s per episode, ETA about 3.4 h. No foreign GPU load observed.

**Second independent review** (27 agents) of the first round of fixes: 23 findings, **22 confirmed, none critical,
5 major**, all fixed before the freeze. The one that mattered scientifically: after certification, a visible check
whose *input* coincides with a hidden-test input is a hidden assert with its answer, and it was pasted into repair
prompts. The 7B writer has memorised benchmark examples — **514 of 2,977 written checks used a hidden input (43% of
HumanEval checks, 7% of MBPP)**. They are now removed at environment construction together with vacuous checks; the
protocol sentence "hidden tests never enter any prompt" was restated to say exactly where hidden tests are consulted
(once, to remove coinciding checks). Also fixed: a torn final line became fatal on the second resume; analysis could
freeze a learned policy on a log that still owed retries; episodes in flight at an abort were discarded.

**Environment as frozen:** 2,977 written checks → 38 vacuous, 514 hidden-input overlaps, 798 failed by the
reference → **1,627 certified checks**; 94 of 591 tasks fall back to a load check.

**Pilot gate (30 disjoint tasks × 4 runs; descriptive, enters no analysis):** first-call hidden-test success small
0.667 / large 0.762 (inside 15–85%; the 7B is the stronger model here); P(t=1 eligible) 0.225, P(t=2) 0.133;
visible-test false-alarm rate **0.074** (was 0.57 before certification), false-pass rate 0.097; 0 infrastructure
errors, 0 timeouts, 0 truncations. No configuration value was changed after the pilot.

**Next:** when the log completes — `analysis.py --learn` (freeze and push the learned routing table), then the live
stage (3,960 fresh target-policy episodes, ≈2.4 h), OPE-vs-live calibration, branch audit (≈0.5 h).

## 2026-09-19 14:45 EDT — real execution started; harness hardened before any freeze

**Stage:** environment construction (visible tests), second pass running on the GPU; pilot next. No design task has
been touched by a model. Nothing is frozen yet.

**GPU sharing.** The sibling tau2 stream finished overnight; the author asked for both projects to co-run. Both
llama-servers are up (3B 116 tok/s, 7B 67 tok/s over 4 slots; 9.4 GB resident). No foreign GPU load has been
observed so far today. Correction recorded in `experiments/README.md`: the claim that tau2 "uses latency as an
outcome tier" was wrong (its tiers are success / completion tokens / tool calls).

**Independent pre-freeze review** (48 agents, six lenses, every finding attacked by a second agent): 41 findings,
**38 confirmed, 3 refuted, none critical, 13 major**. Fixed before any episode:
- an errored episode was marked done forever, the promised same-seed rerun had no code path, and the analysis then
  crashed on unequal runs per task → retry with the same pre-drawn randomization (≤3 attempts), last good attempt
  wins, exhausted episodes scored intention-to-treat; both paths exercised with injected failures;
- pre-registered analyses that did not exist: live contrasts vs always-small (the A2 decision rule) and both
  negative controls → implemented; Bonferroni critical value now exact;
- downstream stages did not require a complete upstream log; the branch-audit sample depended on whatever the log
  held at launch → completeness gates; branch plan drawn once from the complete log and frozen;
- a repair reply quoting the old code first re-submitted the OLD code; ```` ```Python ```` and truncated replies were
  mis-parsed → last defining block, case-insensitive, unclosed fences handled;
- HumanEval helpers that exist only in the prompt were missing at verification → shared prelude; **all 591
  reference solutions now pass the hidden-test verifier (591/591)**;
- per-slot context was 4,096 tokens and a third-round transcript can reach ~4.7k → 8,192 per slot;
- single-writer stage lock, torn-line tolerance, task-file sha check (file now pinned locally), per-run sandbox
  read isolation, wall-clock limit 2× the CPU limit, decision log carries draw / eligibility / attempt.

**Finding that changed the environment.** The first visible-test file (7B, T=0) gave zero usable asserts for 111 of
591 tasks (pytest-style wrappers) and, after fixing that, **rejected the correct reference solution in 336 of 588
tasks (57%)**. Visible checks are now certified against the reference (inputs from the model, expected values from
the reference; hidden tests untouched). The unvalidated file was never frozen or used.

**Second review** of these fixes is running now; the pilot waits for the regenerated tests, the freeze waits for
both the review and the pilot gate.

**Problems:** none blocking. A one-day delay was self-inflicted (see the correction above).
