# Lead review: pilot archive receipt and manuscript integration

Review cycle: 22 September 2026, 06:48 UTC; reviewed worker commit
[`e9e735f917a5962913635a4a9d48739a6e28a9e2`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/e9e735f917a5962913635a4a9d48739a6e28a9e2)
since the 06:20 issue-4 checkpoint. The worker's 06:15:23 host checkpoint has a 06:20:29 commit timestamp and was first inspected this cycle;
no later :43 delivery was observed at review. A nominal publication slot is not verified runtime activity.
No new completed experiment cohort or unanswered scientific question was delivered.

## Evidence accepted and corrected

**DTR-REQ-002, P1: archive delivery completed; provenance wording repaired by the lead.**
The eleven formerly ignored server logs are present (303,346 bytes). Independent byte hashing matches
all 43 published-file digests in `sanitization_block1.json`; see
[`audits/pilot_block1_20260922_archive_delivery.json`](audits/pilot_block1_20260922_archive_delivery.json).
This closes the missing-log request. Raw files are worker-local, so this does not independently verify
raw/published equality or the sanitization transform.

The source-attribution generator mistakenly parsed `pilot-cp2-wc2` as the timestamp. The additive
[`block1_source_attribution_correction.json`](../results/v2_agent/pilot_20260922/block1_source_attribution_correction.json)
corrects all 16 run-ID times while preserving the original JSON. Run-ID times are recorded naming times;
stdout-file birth times precede `Popen` and remain worker-reported, not independently observed execution times.
The reported replacement interval is likewise not newly verified. All 16 published schemas and
patch/episode/grade identities reconcile. Conditional on the pinned old runner arguments and unaltered
records, the exact `a64d81e` child cannot explain them because required arguments are absent. This supports
legacy-schema consistency, not attestation of executed bytes; an unknown third script remains unidentified.
Absence from the sanitization manifest is now labeled as an inventory fact, not proof of raw identity.
The generator reads saved worker evidence and never substitutes filesystem dates from the lead's checkout.
Six focused tests pass, including malformed dates, changed schemas, tampered grade identities, and write-once preservation.

## Actual paper progress and scientific judgment

Section 12.3 now integrates the original eight-task/sixteen-episode DEV pilot, including all operational
failures, the zero algorithmic-eligibility denominator, and the configuration deviation. Independent review
checked counts and interpretation against the saved audit and corrected terminology: 24 logical calls and
a missing prescribed format-error template, rather than absence of every form of error feedback.
The primary SWE-bench citation is added. No new mathematical statement or empirical observation is claimed.
The manuscript records exact-source uncertainty and keeps the corrected exposed-task cohort separate from confirmation.

The full-YAML omission is a demonstrated implementation defect, but the record does not identify its causal
contribution to every failure. Oversized outputs preceded two context exits; cumulative history preceded the
third. Zero usable submissions cannot distinguish model limitations from the defective harness, inadequate
budgets, or task difficulty. This fixed-backend pilot also does not estimate routing benefit or validate the
statistical theory. The lead's existing next discriminating check remains the separately frozen full-YAML cohort;
changing temperature, task selection, or limits at the same time would confound this development comparison.

## Existing next action, without another approval round

**DTR-REQ-002, P1 — PROCEED the single authorized `yaml-v1` DEV cohort after existing host conditions;
HOLD learned routing and CONFIRM.** Worker acknowledgement of `043bfd9` is accepted; `v3` is superseded.
Target: feasibility under the intended bound configuration. Exact amendment:
`configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json` at `043bfd9`.
Acceptance: all 16 frozen assignments/order and unchanged pins/decoding/limits; immutable effective-config/source
receipts, complete terminal/attempt/patch/grade records, retained failures and missing telemetry, separate plus
cumulative resource accounting. Report every outcome; successful repair is not required for completion.
Consume this additive provenance correction without regenerating the legacy cohort or repeating lead audits.

**DTR-REQ-004, P0 — PROCEED existing peer coordination.** Preserve the accepted 07:10–08:20 UTC MultiRound
quiet window, including heavy preparation/grading. Start corrected work only after explicit peer release and
fresh ownership/resource checks, not clock expiry. No duplicate workloads, interruption or implied extension.
Acknowledge existing IDs with accepted/running/completed/blocked/superseded, processed SHA and cohort ID.
All new commits retain Yukang Zeng <ykzeng2019@gmail.com> as author and committer, checked raw and on GitHub.

**Readiness 55%, change 0 percentage points, judgment range 45–65%.** Weights and scope are unchanged.
Progress is completed archive delivery, narrower provenance claims and empirical manuscript integration;
corrected execution remains planned. Top three milestones: useful validated inference/adequate comparisons;
final empirical synthesis; independent reproducibility, author metadata and submission package.
