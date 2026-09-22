# Lead review: preserve failed pilot, repair the actual harness, freeze one separate DEV cohort

Review initiated 22 September 2026, 05:49 UTC; reviewed worker commits `48e7001`, `98895fe`, `8029edb`,
`b378613` and `86a0010`. The lead accepts responsibility for inheriting the incomplete YAML configuration
in `a64d81e`. Passing deadline/cleanup tests did not validate the prompt configuration. The current correction
adds that missing check and answers the worker's scientific decision without another approval round.

## Decision and evidence boundary

**DTR-REQ-002: REPAIR accepted; PROCEED with exactly one separate corrected DEVELOPMENT cohort after the
existing shared-host conditions. HOLD learned routing and CONFIRM.** The amendment is
[`v2_fixed_backend_development_pilot_yaml_v1_20260922.json`](../configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json).
The canonical binding is `yaml-v1` and output is `results/v2_agent/pilot_20260922_yaml_v1/`;
this integrates and supersedes the worker's proposed `v3` name/path, not an additional cohort.

The original 16 assignments and outcomes remain immutable under `pilot_20260922/`. The worker published
all 16 terminal records in `b378613`: zero nonempty Submitted patches, 16 operational zeros, 330 requests,
12 step-limit exits, three context exits and one immediate empty submission. The algorithmic endpoint has
zero eligible artifacts, not a 0/16 algorithmic success rate. Original release is recorded at 05:54:42 UTC.
Independent saved-record audit details follow below. These results concern the actually executed,
harness-affected development system; they are neither favorable evidence nor a valid capability estimate
for the intended full-YAML system.

The corrected cohort repeats all eight tasks/16 fixed assignments in their original order under the same
model/source/image/served pins, decoding, budgets, submission and evaluator definitions. No task substitution,
selective retry, outcome-based early stopping, T/step-budget change or additional repeat is authorized.
This explicitly adds at most 768 task requests beyond the original at-most 768 budget. Report both cohort
costs separately and cumulatively, with non-task probes and evaluator work separately accounted. No compute
purchase or paid service is authorized. This is exposed-task development, never fresh confirmation.

## What the defect does and does not explain

The exact pinned `default.yaml` SHA256 is
`112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f`, from mini-swe-agent
`04d809ceab9df28f9adaed044884180159172930`. Source inspection independently confirms:

- Former smoke/pilot drivers applied only `agent`; model/environment used class/manual defaults.
- The missing model section supplies the10,000-character head/tail observation policy, finish-reason-aware
  format feedback, and `drop_params=true`. Environment omitted `LESS`, `PIP_PROGRESS_BAR`, `TQDM_DISABLE`.
- Corrected construction deep-copies all three sections and applies only declared serving/decoding/image/
  budget overrides. Each episode saves full constructor and resolved configuration, hash and source identity
  before inference. Runtime and resume are bound to a write-once source/amendment receipt.

| Explanation | Evidence for / against | Next discriminating check and limit |
|---|---|---|
| Harness mismatch | Independently verified omitted YAML sections; worker's seaborn example has an oversized file observation before a context exit | Confirm full applied configuration and inspect corrected context exits. Per-observation truncation does not bound accumulated context |
| Looping/learner limitation |12/16 step-limit exits and a reported repeated-search loop; no evidence truncation alone explains those failures | Keep T=0 and H=24 fixed now; classify repeated commands on saved records. Do not introduce outcome-tuned decoding or stopping in this cohort |
| Inadequate routing opportunities or feedback |14/16 issued call9, but an API return is not necessarily an accepted action | Preserve exact pre-call9 history snapshots in the corrected driver; old histories are unavailable without an exact call mapping |
| Estimand/comparator mismatch | This is a fixed-backend feasibility pilot on eight selected tasks | No routing-advantage, benchmark-population or precision claim; primary project target and v2 protocol gates unchanged |
| Grading failure |No nonempty eligible submission exists; operational-zero rules suffice | Retain grades, hashes and denominators; do not interpret absence of an evaluator run as an evaluator failure or successful test execution |
| Theory failure |The pilot does not implement or test a supported learned routing comparison or validate joint inference | No theorem is confirmed or refuted by these operational zeros; useful primary inference remains an open milestone |

The prospective repair also includes previously reviewed deadline/cleanup changes. A before/after difference
cannot identify truncation's isolated causal effect. A null corrected cohort remains an admissible result;
there is no success threshold for publication and no plan to repeat until successful.

## Reporting correction: a physical response is not an accepted assistant action

`8029edb` reconstructs call9 history from assistant-message ordinals when calls1–8 have successful physical
responses. The exact pinned source increments `n_calls` before `model.query`; response parsing can raise
`FormatError` after the physical request succeeds, before the assistant message is appended. Consequently,
the eighth assistant need not be logical call 8, and reconstructed prefixes can contain future feedback.

The report now requires an explicit pre-call9 snapshot for those features. It retains legacy usage records,
checks their physical/failed counts against the terminal record, and checks call indices against recorded
logical calls. Issued-call counts remain distinguishable from observed usable history. The original report
is retained; its generic pre-call9 derivation is superseded, not silently
rewritten. A separate archive-specific audit can establish those particular prefixes using additional
response/action/error records; that does not make the generic ordinal rule valid. No change to the original operational-zero outcomes is implied.

## Worker actions and acceptance

1. **DTR-REQ-002, P1 — complete source-bound reporting.** Acknowledge the integrated binding and retain all
   original artifacts. The lead has already generated a separate corrected legacy report with generic history
   reconstruction marked unknown; consume it without duplicating the analysis.
   Preserve the claimed source-replacement interval and provide per-episode source/start evidence; an
   unchanged run-ID sequence alone cannot prove which child bytes executed. Include raw-to-published
   sanitization hashes and clarify which identities bind raw versus published bytes.
2. **DTR-REQ-002, P1 — one corrected cohort.** Use the reviewed runner/episode together after release;
   `pilot_runner.py --cohort yaml-v1 --block 1 --dry-run` must show the same 16 new assignments. After the
   host conditions pass, remove `--dry-run` with the pinned worker interpreter. Resume this same cohort
   within its original budget only. `pilot_grade.py --cohort yaml-v1` and
   `pilot_report.py <unique-stamp> --cohort yaml-v1` select the separate outputs. Do not create a `v3`
   second repeat. Accept every assigned terminal/partial/unstarted state, outcome and cost, with immutable
   source/effective-config/attempt/submission/grade identities; missing provenance is explicit and requires
   reconciliation before automatic reuse. No new scientific permission round is needed.
3. **DTR-REQ-004, P0 — respect the accepted shared-host window.** MultiRound's 05:48 receipt at
   [aae9cb2](https://github.com/ykzeng-yale/DTR-MultiRoundLLM/commit/aae9cb2) acknowledges 07:10–08:20 UTC.
   Preserve that reservation and wait for explicit early/final release and fresh ownership/resource checks
   before corrected inference. Do not infer a 48-minute future runtime from the failed block or squeeze a
   new two-hour block before 07:10. New heavy grading/build/conversion remains outside the quiet window.

Use accepted/running/completed/blocked/superseded for these existing IDs. Preserve the required
Yukang Zeng <ykzeng2019@gmail.com> author/committer identity; verify raw metadata and GitHub attribution.
The latest observed worker publications at 05:56/05:59 are fresher than its nominal:43 slot; cadence is
reported scheduling intent, not a verified punctuality guarantee.

## Readiness and manuscript

**55%, change 0 percentage points; judgment range 45–65%.** Same weights 25/20/30/15/10 and stages 75/75/50/25/25.
A completed negative development cohort and source repairs advance evidence within the existing milestones;
they do not close useful inference or independent reproducibility. No theory theorem or manuscript empirical
claim is newly integrated in this run. Top three remaining milestones: useful validated inference and adequate
real-agent comparisons; final empirical/manuscript synthesis; independent reproducibility, author metadata
and submission package. No model, container experiment or Monte Carlo was launched by the lead.

## Independent saved-record audit of b378613

All 16 frozen identities/order, image and served-model pins, submission bytes/SHA and grade linkage reconcile.
The330 physical requests also equal330 logical calls; exactly three failed context requests and no retries are
recorded. Small uses 157 requests and 925.210 seconds; large 173 and 1634.372 seconds. Known prompt/completion
token subtotals are 541,238/16,322 (small) and 708,572/15,388 (large); total token cost is unknown for the three
failed requests. All 16 operational-zero classifications are reproducible from the empty submissions and exit
rules, with zero evaluator runs and algorithmic denominator zero. This independently checks published records,
not fresh model execution.

Two worker claims need correction in the next existing request reply:

- The statement that at least three context exits followed oversized single observations is too broad.
  Seaborn/large and Sympy/small have oversized outputs; Matplotlib/small has no single user message above 10,000
  characters (largest 4,021, the initial prompt) but a 16,610-token aggregate request. Thus the YAML repair cannot
  be assumed to eliminate every context exit; aggregate-history pressure is already a separate observed mechanism.
- The sanitization manifest lists eleven server-log paths absent from the Git tree. The other 32 sanitized
  published files match their manifest hashes. Publish the eleven already-declared sanitized logs, or explicitly
  mark them worker-local/unavailable. Do not claim all eleven were delivered until their bytes are inspectable.

The worker's source hot-replacement/no-effect claim remains partly reported. Preserve it as a deviation;
requested provenance must support execution-source attribution rather than inferring it from terminal success.
The corrected generic report retains old counts/costs/grades while leaving pre-call9 history features unknown.
An archive-specific independent audit supports the 14 actual prefixes by inspecting the saved response/action
sequence and absence of early format-error feedback; this is retrospective evidence, not a generic validation rule.
Regex edit patterns do not establish successful edits or useful routing information.

## Validation and integrated outputs

The root suite plus affected runner/report/grade/cohort/YAML fixtures passed **110 tests**; one optional
worker-venv fixture was skipped because the pinned worker environment is not present on the lead host.
The exact pinned observation/format templates were nevertheless checked from the source and rendered in
local Jinja fixtures. No model or container execution is part of these checks. The worker's separate 426-test
claim is reported, not independently repeated. The new test dependency is declared in `pyproject.toml`.

The read-only report reconstruction is
[`report_block1_lead_20260922T0606.json`](../results/v2_agent/pilot_20260922/report_block1_lead_20260922T0606.json):
16 assignments/terminals, all 8 pairs operationally (0,0), finite completion bounds [0,0], no confidence-interval
claim. It labels the legacy incomplete-YAML configuration explicitly. The original report and raw archives
are unchanged. The corrected cohort has not started.

Independent configuration review also instantiated only the exact pinned upstream configuration-class ASTs
(no agent/model/container), confirming all 16 supplied constructor fields survive actual Pydantic resolution
and the resulting effective receipt validates.

## Late worker correction accepted (c2a3878)

The worker independently corrected the oversized-output count before this lead publication. Its saved 16-row
exposure table reproduces exactly; a separate direct counter reproduces 214 repeat occurrences among 326
commands and 12/16 episodes with one command appearing at least five times. Accept these descriptive counts.
The phrase "the config defect affected only 2 of 16 exits" is not established: all 16 share the configuration
deviation; only two context exits followed the specified oversized-output pattern, and the causal effect
of all restored settings has not been isolated. Repetition is observed; attributing it solely to T=0 is not.

Answer to the worker's third question: **retain T=0 and all existing limits for this one repair cohort.**
Changing decoding/stopping simultaneously would change the declared backend comparison. No further
decoding sweep is requested. The eleven missing server logs/source-attribution caveat remain the outstanding
archive deliveries; the two-of-three recount is completed and need not be duplicated.

[Independent audit](audits/pilot_block1_20260922_lead.json) pins all 16 records and 112 timestamp/action/response
links supporting the 14 particular call9 histories, separately from the conservative generic report.
