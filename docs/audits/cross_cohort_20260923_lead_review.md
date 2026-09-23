# Independent retrospective review of the two completed pilot cohorts

Review completed: 2026-09-23 UTC. Source checkpoint:
[`4927adc9fd28f2bea2a21a2751337f83b2e60dbf`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/4927adc9fd28f2bea2a21a2751337f83b2e60dbf).
This is a deterministic review of published records, not a new experiment,
runtime validation, or CONFIRM analysis. No model, container, server, evaluator,
or Monte Carlo job was run. Existing records were not edited.

## Sources and evidence boundary

The reviewed cohorts are the 16 original episodes in
`results/v2_agent/pilot_20260922/` and the 16 corrected-binding episodes in
`results/v2_agent/pilot_20260922_yaml_v1/`. Each episode's `trajectory.json`,
`episode.json`, and `submission.diff` was read directly. The worker's
`results/v2_agent/analysis_20260922/{action_profile,repetition_taxonomy,cross_cohort_divergence,cross_cohort_diagnostic}.json`,
`SUMMARY.md`, associated analysis source, and the six questions in
`docs/experiment_handoff.md` were inspected for interpretation and consistency.

The counts below were re-derived from the published trajectories independently
of the worker's output-generating analysis scripts. They validate properties of
those records, conditional on their completeness. They do not independently
authenticate unpublished raw files, the actual model weights loaded into a
server, or the post-sanitization effective-configuration identity. The separate
configuration-projection review addresses that last issue. No claim below
silently upgrades raw configuration provenance to verified.

## Recalculation method and totals

For each trajectory, traverse messages in stored order. For every assistant
message with `extra.actions`, require exactly one recorded action and extract
its `command` string. Pair it with the following message: an ordinary tool
observation has role `user`; the immediate successful submission has role
`exit` and no ordinary return-code field. Command positions below are one-based
positions among recorded commands, not logical model-call numbers. Format
errors and failed physical requests need not produce recorded commands.

Within each episode, maintain a list of observation `content` strings for each
exact command string. Every occurrence after the first is a repeated command.
Compare its rendered observation string both with the first observation for
that command and with the immediately preceding observation for that command.
No whitespace, warning, timestamp, or output normalization was applied.
Cross-cohort command sequences were paired by `(instance_id, backend)`, compared
as complete ordered lists, and scanned from their starts to the first unequal
command or the end of the shorter list.

Separately, count non-null `episode.json.final_tree` and inspect actual
`submission.diff` bytes. The following values were reproduced in a fresh
standard-library Python read-only pass during this review:

| Quantity | Original | yaml-v1 | Total |
|---|---:|---:|---:|
| Episodes | 16 | 16 | 32 |
| Recorded commands | 326 | 348 | 674 |
| Repeated command occurrences | 214 | 232 | 446 |
| Observation identical to previous occurrence | 212 | 231 | 443 |
| Observation identical to first occurrence | 208 | 229 | 437 |
| Non-null `final_tree` | 1 | 1 | 2 |
| Empty `submission.diff` files | 16 | 16 | 32 |

Twelve of 16 matched assignments have identical complete command sequences;
the sum of identical-prefix lengths over all 16 assignments is 292. The two
repetition denominators are the same 446 occurrences, with different reference
observations. Neither is a success measure. Identical visible output does not
establish an unchanged filesystem or absence of other state changes.

## Attempted writes are not confirmed file mutations

For requests/small, there are 21 `sed -i` action strings in each cohort, at
recorded command positions 4--24. All 42 return shell exit code 2 and the same
unmatched-quote / unexpected-end-of-file error. The malformed single command
fails shell parsing before `sed` executes. Thus these records support **42
attempted write commands and zero successful `sed` executions from them**, not
42 installed-package edits. This conclusion is limited to those attempts; it
is not a measurement of the entire episode's filesystem state.

The exact repeated command is:

```text
sed -i '/self.headers\[\'Content-Length\'\] = length/a if request.method != \'GET\':' /opt/miniconda3/envs/testbed/lib/python3.9/site-packages/requests/models.py
```

The following paths identify the directly inspected records:

- `results/v2_agent/pilot_20260922/psf__requests-1142__small__pilot-cp2-wc2__20260922T054827Z-85153d/trajectory.json`
  SHA-256 `15d07a73870204ac74c13beebea31da20be014e35b15f1010d5027f704554493`.
- `results/v2_agent/pilot_20260922_yaml_v1/psf__requests-1142__small__pilot-cp2-wc2-yaml-v1__20260922T080423Z-7ad659/trajectory.json`
  SHA-256 `8e2ff4b9b671467b54b8240a7091a6f68b11e1d890e9cbebfc968d3d6ec63fc1`.

Two additional qualifications matter when interpreting the worker's syntactic
write classification:

1. In sympy/large, `sed -i` returning zero does not prove that a substitution
   matched. The trajectory does show creation and execution of a reproduction
   file, but does not show a readback diff establishing the proposed source
   substitution.
2. In sklearn/small, three compound clone/write action strings occur per
   cohort. The first fails at `git checkout master` and the second at `git
   clone`, so their later `sed` commands do not run. The third returns zero,
   but subsequent `git commit` attempts inside the new clone report `nothing
   to commit, working tree clean`. That weighs against interpreting the third
   action as a successful source correction. The clone is reached by a
   relative `cd scikit-learn` from `/testbed`; do not rewrite “outside the
   base repository” as “outside /testbed.”

The relevant sklearn/small trajectory directories are
`pilot_20260922/scikit-learn__scikit-learn-10297__small__pilot-cp2-wc2__20260922T052252Z-def348/`
and
`pilot_20260922_yaml_v1/scikit-learn__scikit-learn-10297__small__pilot-cp2-wc2-yaml-v1__20260922T073224Z-a920da/`,
both under `results/v2_agent/`. Commands 1--3 are the clone/write attempts;
commands 8, 11, 14, 17, 20, and 23 contain the unsuccessful commit-and-test
chains. The third clone action prints the submission sentinel after other
output. The pinned Docker implementation's `_check_finished` requires its
first non-leading-whitespace output line to be the sentinel and return code
zero. The prompt explicitly requires the sentinel command alone. A sentinel
appearing later in this compound output therefore does not establish a missed
valid submission by the harness.

## Empty submitted patches and missing terminal workspaces

Only the two immediate astropy/small Submitted episodes have `final_tree`.
The other **30 terminal workspaces are uncaptured**, not observed empty. All
32 `submission.diff` files are empty under the declared Submitted-only
collection rule. Consequently the operational endpoint is zero throughout,
and no eligible nonempty submitted patch exists for the conditional algorithmic
endpoint. This is not 32 evaluated incorrect programs and does not identify
whether an uncaptured workspace contained useful changes.

`experiments/v2_agent/workspace_capture.py` documents and implements wc2 using
a private Git index (`read-tree HEAD`, `add -A`, `write-tree`) in `/testbed`.
It includes ordinary new/untracked files except ignored paths when capture
actually occurs. A blanket claim that new files are excluded would be false.
A nested clone also does not establish that the clone's individual source
changes would be captured as ordinary base-repository files. Neither point
repairs the missing 30 terminal snapshots retrospectively.

## What `run_tests = 0` establishes

The worker's command-family count is a source-code heuristic, not an execution
trace of every program started by a shell. In
`experiments/v2_agent/analysis/action_profile.py`, heredoc bodies are stripped,
quoted spans are masked, and a fixed priority assigns a primary family.
`run_tests` matches named test-runner patterns such as pytest, tox, unittest,
`runtests`, and `manage.py test`. Its zero count should not be expanded into
“no testing occurred.” No explicit repository test-suite invocation was
identified in the recorded command inventory, but there are directly observed
executions of agent-written reproductions:

- **sympy/large, original:** `python test_distance.py` runs at recorded command
  positions 14, 16, 18, 20, and 22, all returning zero and printing `1` with
  warnings. Source:
  `results/v2_agent/pilot_20260922/sympy__sympy-11618__large__pilot-cp2-wc2__20260922T053340Z-fa1672/trajectory.json`.
- **sympy/large, yaml-v1:** a combined heredoc creation of `test_distance.py`
  followed by `python test_distance.py` runs at positions 13, 16, 19, and 21,
  all returning zero and printing `1` with warnings. Source:
  `results/v2_agent/pilot_20260922_yaml_v1/sympy__sympy-11618__large__pilot-cp2-wc2-yaml-v1__20260922T074338Z-1b5364/trajectory.json`.
- **sklearn/small, both cohorts:** command 5 creates and executes
  `test_ridge_classifier_cv.py`. Its traceback shows that Python ran and raised
  `TypeError: __init__() got an unexpected keyword argument 'store_cv_values'`.
  Later strings ending in `&& python test_ridge_classifier_cv.py` do not by
  themselves show another execution: their preceding Git commands fail.

The sympy reproduction constructs `Point(2, 0)` and `Point(1, 0, 2)` and prints
their distance. Running it is evidence of an executed reproduction, not of a
passing existing regression suite or a successful benchmark patch. Appropriate
manuscript language is: **“No explicit repository test-suite invocation was
recorded; some episodes executed agent-written reproductions and received
their outputs.”**

## Cross-cohort disagreement does not isolate the YAML repair

| Assignment | Original commands | yaml-v1 commands | Identical prefix | Nature of disagreement |
|---|---:|---:|---:|---|
| seaborn/large | 4 | 24 | 4 | Original sequence is a prefix |
| sympy/small | 11 | 14 | 11 | Original sequence is a prefix |
| requests/large | 24 | 24 | 2 | Different command at position 3 |
| sympy/large | 23 | 22 | 11 | Different recorded command at position 12 |

Both pairs with a disagreement at a shared command position already had
different visible observations after their first `ls -la`. The `..` directory
line is dated `Sep 22 05:51` versus `Sep 22 08:07` for requests/large, and
`Sep 22 05:33` versus `Sep 22 07:43` for sympy/large. The requests/large records
are:

- `results/v2_agent/pilot_20260922/psf__requests-1142__large__pilot-cp2-wc2__20260922T055112Z-48dc58/trajectory.json`
- `results/v2_agent/pilot_20260922_yaml_v1/psf__requests-1142__large__pilot-cp2-wc2-yaml-v1__20260922T080700Z-49aae1/trajectory.json`

The sympy/large paths are listed above. These observations establish that the
histories were not byte-identical before the command divergence; they do not
establish that directory timestamps caused it. Temperature zero alone does
not make this a controlled same-input replay or isolate the YAML binding's
causal effect. The 12/16 agreement is descriptive, not an expected-agreement
test that requires additional inference to explain the remaining four.

## Context failures and remaining uncertainty

The worker's wording that the context mechanism is “not recoverable” is too
strong. Archived oversized observations and their positions in the retained
conversation support oversized-output and accumulated-history explanations.
The earlier `docs/audits/pilot_block1_20260922_lead.json` records the original
oversized-output examples. The corrected cohort's elision markers and context
exits also show that per-output truncation did not guarantee a bounded total
conversation. Exact rejected wire payloads and server-side tokenization were
not independently archived, so complete request-level causal attribution and
exact reconstruction of the server's prompt accounting remain unavailable.
No context-limit increase or new batch is justified merely by these counts.

## Discriminating next step and limits

The evidence supports a bounded DEVELOPMENT repair: separate all-exit shadow
workspace capture and durable pre-dispatch request receipts, followed by a
prespecified single recovery cue for repeated visible feedback. The lead
selected a trigger of either three consecutive identical
`(command, returncode, rendered observation)` triples or three repetitions of
an identical ordered two-cycle (`ABABAB`), with at most one cue per episode.
The cue must not assert an unchanged hidden state or provide a task-specific
solution. It must not force submission, stop the episode, reset context,
increase H24, or grant an extra model call. Existing endpoint rules stay fixed.

Acceptance first requires deterministic fixtures for capture success/failure,
failed compound commands, no-op edits, primary-versus-shadow separation, exact
trigger boundaries, and exactly one cue with unchanged call accounting. Live
execution remains held pending review of that implementation and a separately
frozen, limited controlled DEV design with an instrumentation-only baseline.
The contrast should distinguish cue delivery, a changed action, useful new
observations or in-tree changes, and an eligible submission; those are distinct
outcomes. A changed command alone is not evidence of progress or task success.

This choice is supported by abundant repeated visible feedback and concrete
shell/interface failures. It does not prove that repetition is the sole cause
of failure, that the models can solve the tasks, or that one cue will help.
Model/learner limitations, task difficulty, context loss, and weak verification
remain plausible. No unchanged 16-episode rerun, budget escalation, adaptive
routing release, or CONFIRM promotion follows from this audit. Preserve both
completed cohorts and any unfavorable diagnostic outcomes without pooling
them as prospective confirmatory evidence.
