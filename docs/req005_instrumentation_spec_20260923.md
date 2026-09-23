# DTR-REQ-005 instrumentation specification (worker, 23 September 2026 UTC)

**Status: implemented and fixture-verified; NO live episode has been run; live release awaits lead review.**
This document specifies the instrumentation the lead requested in
[the 23 September review](theory_feedback_20260923_completed_pilots.md) (answers 1 and 5 and
**DTR-REQ-005 (P0)**), maps every acceptance fixture the lead listed to the test that covers it, and states
exactly what is *not* yet wired into a live runner.

Nothing here ran a model, server, container, evaluator or network call. No archive under `results/` was
read-write opened, no episode record was created, and the frozen yaml-v1 execution sources are unchanged
(hashes below). Retrospective fixture outputs are published in
[`req005_fixture_landmarks_20260923.json`](req005_fixture_landmarks_20260923.json).

## 1. The cue

Delivered as ONE text block, 290 characters, no internal line breaks, reflowed from the lead's blockquote
(`theory_feedback_20260923_completed_pilots.md:144-146`) by joining its three wrapped lines with single
spaces:

> Recent actions returned the same visible feedback repeatedly. Use the existing /testbed checkout. Choose a different action that will provide useful new evidence, or explain why repeating the action is necessary. Check the current working directory and the existing submission instructions.

| field | value |
|---|---|
| `cue_sha256` | `80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e` |
| characters / UTF-8 bytes | 290 / 290 |
| task-independent | no solution or file hint, no gold patch, no hidden-test information |

`test_cue_text_is_the_lead_blockquote_and_its_digest_is_a_hand_written_literal` rebuilds the cue from the
lead document itself and compares it against an independently typed literal and a hand-written digest, so
neither a reworded cue nor a module-side digest derivation can pass.

## 2. What each module does

All five modules are NEW files. `pilot_episode.py`, `pilot_runner.py`, `pilot_cohort.py`, `pilot_report.py`
and `pilot_grade.py` are untouched.

### `experiments/v2_agent/cue_detector.py` — repeated-action detector
Pure and side-effect free: no I/O, no mutation of caller objects, no model call.
* Records are exact triples `(command, returncode, rendered observation)`. A record is COMPLETE only when
  all three are present and parsable **and** its logical call id is a positive integer.
* Triggers on the FIRST completion of `AAA` (three identical consecutive complete triples) or `ABABAB`
  (three repetitions of an ordered pair of two distinct complete triples).
* "Consecutive" means consecutive **logical call ids**, not adjacent surviving rows: a caller that filters
  out an unparsable record (calls 1, 2, 4) does not trigger, and the gap is published in
  `call_id_discontinuities`. Duplicate ids (5, 5, 5) do not trigger.
* An incomplete record breaks adjacency and is never skipped over.
* At most ONE cue per episode, owed to `trigger_call_id + 1`. If that call is outside the horizon (H=24) the
  trigger is recorded **without delivery** and no cue text is ever handed out.
* Planned and actual delivery are separate fields: `delivery_call_id` / `delivery_planned` are the plan;
  `delivered` / `cue_emissions` / `cue_emitted_call_ids` are what was actually handed out (always
  `delivered=false`, `cue_emissions=0` for the pure `scan()`, which emits nothing by construction).
* Two modes over the same logic: `live` (emits the one cue) and `observe` (the silent baseline arm — the
  identical landmark, nothing ever emitted).
* No record content can raise into an episode driver: malformed records degrade to INCOMPLETE and malformed
  cue requests return `None` and are counted in `cue_requests_refused`. Only a bad `mode`/`horizon` raises,
  and that happens at construction, before any episode work.

### `experiments/v2_agent/trajectory_triples.py` — retrospective adapter (read-only)
Turns an archived `results/v2_agent/<cohort>/<run>/trajectory.json` into detector records using the lead's
frozen linking rule (answer Q8): one record per logical model call, numbered from 1 in assistant-message
order, linked ONLY to that call's immediate ordinary recorded return-code observation. An exit message, a
format-error message with no return code, a missing message or a reported executor exception all mean the
observation is MISSING for that call; no proximate earlier or later observation is substituted. Rendered
observations are the exact bytes the agent was shown, with no timestamp or whitespace normalisation.

### `experiments/v2_agent/exit_capture.py` — all-exit diagnostic capture (binding `xc1`)
On EVERY exit and BEFORE container cleanup: bounded `tree` (whole working tree through a private index,
reusing `workspace_capture.TREE_CMD` verbatim), `status` (`git status --porcelain --untracked-files=all`),
`diff` against the recorded starting tree (`tree_to_tree`, falling back to `base_to_worktree` with the mode
recorded), and `untracked` paths with full-content digests, sizes and bounded contents.
* Section states: `captured`, `no_change` (a COMPLETED empty observation), `incomplete` (it ran but is known
  partial), `unavailable`, `failed`, `timeout`. Absent is never empty, incomplete is never silent, and
  unknown counts stay `null` rather than 0.
* `changes_observed` is `true` if any of the three change signals (status, diff, untracked) observed
  something, `false` only when all three completed and observed nothing, else `null`. The porcelain status is
  one of those signals, because `git diff <base>` against the worktree cannot see a new untracked file.
* Every bound is explicit: validated `caps` (a malformed value is ignored and named in `caps_error`, never
  published as the declared bound), per-section `truncated`, `digest_scope` naming what each sha256 covers,
  `per_command_timeout_s`, `total_budget_s`, the six `exclusions`, and `failures` for every degraded *or*
  knowingly incomplete section.
* Body integrity: every command's body is read through `head -c` and that read's exit status is the status
  the executor reports, and a recorded body whose byte count disagrees with the container-reported full byte
  count degrades the section to `failed`. A container warning line before the bound header is recorded as
  `container_preamble` instead of demoting the capture.
* Endpoint untouched: never written into `submission.diff` (all case spellings and any `.diff`/`.patch`
  suffix are refused), never marks Submitted, never graded, never changes eligibility or endpoint bytes.
* Cleanup is never blocked: no argument or executor behaviour raises out of `capture()` or
  `capture_exit_diagnostic()`; every section key is present even when the capture breaks internally; only
  `KeyboardInterrupt`/`SystemExit` pass through.

### `experiments/v2_agent/request_receipt.py` — pre-dispatch request receipts
* Before dispatch: the exact serialized bytes to a private file under `work/` (git-ignored), with the raw
  sha256, logical/physical ids, and model/decoding/server/tokenizer identity. A preflight token count is
  recorded only with the method that produced it; extra fields that would read as verification claims are
  refused.
* Published separately: a sanitized projection with its own digest and explicit transformation metadata
  (field, occurrences, why) — including the bounded truncation of an error detail. `raw_request_sha256` and
  `published_projection_sha256` are distinct names over distinct byte sequences, and the record always
  states `raw_request_equality = reported_unverified`.
* Failed/rejected requests keep the same durable record plus a linked write-once outcome carrying the error
  class, finish reason, HTTP status and whatever usage the server did report.
* Unknown usage stays `null`, never 0. A server-reported total is retained as reported even when the split
  is unknown, and a total that disagrees with the reported pair is recorded in `total_discrepancy`.
* Both files of an attempt are serialized before either is written, so a serialization failure cannot burn
  an attempt key; `completeness()` lists any remaining hole so nobody reports subtotals over a set with
  skipped records.
* Receipt bookkeeping never changes an episode: the pre-dispatch write may refuse (before any model call),
  but an outcome-recording failure neither replaces the real dispatch exception nor aborts a call that
  succeeded — it is surfaced through `dispatch.receipt_errors` / `on_receipt_error`.
* The private raw directory may not be the published directory, may not be nested with it, may not be under
  any `results/` tree whatever root is declared, and may not be inside the repository root outside `work/`.

### `experiments/v2_agent/cue_cohort.py` — 'cue-v1' cohort registry
Registry only: it creates no directory, writes no episode record and imports no runtime or frozen source.
Cohort `cue-v1`, output directory `results/v2_agent/pilot_20260923_cue_v1`, and the frozen 12-assignment
frame (`assignments()`, `frozen_plan()` with `plan_sha256`
`dc687c8413d5aa8f81cb498b22cc5fac5f4fcf2535bf0c66aea8db2fb882c1ae`).

| # | task | backend | arm | pair | order |
|---|---|---|---|---|---|
| 1 | psf__requests-1142 | small | baseline | 1 | B |
| 2 | psf__requests-1142 | small | cue | 1 | B |
| 3 | psf__requests-1142 | large | cue | 2 | C |
| 4 | psf__requests-1142 | large | baseline | 2 | C |
| 5 | scikit-learn__scikit-learn-10297 | small | cue | 3 | C |
| 6 | scikit-learn__scikit-learn-10297 | small | baseline | 3 | C |
| 7 | scikit-learn__scikit-learn-10297 | large | baseline | 4 | B |
| 8 | scikit-learn__scikit-learn-10297 | large | cue | 4 | B |
| 9 | sympy__sympy-11618 | small | baseline | 5 | B |
| 10 | sympy__sympy-11618 | small | cue | 5 | B |
| 11 | sympy__sympy-11618 | large | cue | 6 | C |
| 12 | sympy__sympy-11618 | large | baseline | 6 | C |

Declared bounds: H=24, two physical attempts per logical call, maximum 576 physical requests, both existing
pinned backends, no replacement/repeat/extension, all 12 retained in operational endpoint accounting. The
baseline arm is instrumentation-only (detector in `observe`); the cue arm changes only the one scheduled cue.
This is a fixed-order descriptive comparison, not a randomized causal effect estimate.

## 3. Acceptance fixtures mapped to tests

The lead's acceptance list (`theory_feedback_20260923_completed_pilots.md:154-160`), fixture → test.

| Acceptance fixture (lead) | Test |
|---|---|
| AAA | `test_v2_cue_detector.py::test_three_identical_consecutive_triples_trigger_aaa` |
| AAA, archived episode | `test_v2_cue_detector.py::test_the_archived_repeat_that_triggers_aaa_is_the_same_bytes_three_times` |
| ABABAB | `test_v2_cue_detector.py::test_three_repetitions_of_an_ordered_pair_trigger_ababab` |
| ABABAB, archived episode | `test_v2_cue_detector.py::test_the_archived_ababab_repeat_alternates_two_distinct_triples` |
| nonrepeat | `test_v2_cue_detector.py::test_a_nonrepeating_sequence_never_triggers` |
| changed return code | `test_v2_cue_detector.py::test_a_changed_return_code_never_triggers` |
| changed output | `test_v2_cue_detector.py::test_a_changed_observation_text_never_triggers` |
| missing observations (no trigger, no skipping) | `test_v2_cue_detector.py::test_incomplete_records_never_trigger_and_are_never_skipped` |
| missing observations, archived episode | `test_v2_cue_detector.py::test_the_one_archived_episode_without_any_observation_is_incomplete_not_a_nonrepeat` |
| missing observations, immediate-observation linking | `test_v2_cue_detector.py::test_the_adapter_links_only_the_immediate_ordinary_observation` |
| pattern not formed by skipping incomplete records | `test_v2_cue_detector.py::test_a_dropped_record_cannot_fabricate_three_consecutive_calls`, `::test_duplicate_logical_call_ids_never_trigger` |
| one-cue maximum | `test_v2_cue_detector.py::test_one_cue_maximum_per_episode` |
| one-cue maximum, no second cue leaking | `test_v2_cue_detector.py::test_a_cue_is_never_handed_to_a_call_id_that_is_not_a_positive_integer` |
| final-call trigger (no next call allowed) | `test_v2_cue_detector.py::test_trigger_on_the_final_budgeted_call_is_recorded_without_delivery` |
| final-call trigger, smaller horizon | `test_v2_cue_detector.py::test_a_trigger_inside_the_horizon_still_delivers_when_the_horizon_is_smaller` |
| no cue for a call that cannot exist | `test_v2_cue_detector.py::test_negative_call_ids_never_schedule_a_cue_for_a_call_that_cannot_exist` |
| exact cue hash, one character included | `test_v2_cue_detector.py::test_cue_text_is_the_lead_blockquote_and_its_digest_is_a_hand_written_literal` |
| baseline leaves model-visible messages unchanged | `test_v2_cue_detector.py::test_observe_only_baseline_records_the_same_landmark_without_emitting` |
| intervention changes only the one scheduled cue | `test_v2_cue_detector.py::test_the_live_arm_asks_call_by_call_as_the_episode_runs` |
| retrospective fixtures over `4927adc`'s 32 episodes | `test_v2_cue_detector.py::test_the_detector_runs_over_every_archived_yaml_v1_episode`, `::test_twenty_one_of_the_thirty_two_archived_episodes_would_have_triggered` |
| Submitted exit capture | `test_v2_exit_capture.py::test_every_exit_kind_is_captured_and_none_is_marked_submitted_or_graded`, `::test_tracked_modifications_appear_in_the_diff_and_the_status_snapshot` |
| context exit capture | `test_v2_exit_capture.py::test_untracked_files_are_recorded_with_digests_and_bounded_contents` |
| timeout exit capture | `test_v2_exit_capture.py::test_an_executor_that_times_out_is_recorded_as_timeout_without_raising`, `::test_the_total_budget_stops_dispatch_and_is_recorded_as_timeout`, `::test_a_slow_executor_exhausts_the_budget_and_the_remaining_sections_are_timeout` |
| capture failure does not block cleanup | `test_v2_exit_capture.py::test_an_executor_that_raises_is_recorded_as_failed_without_raising`, `::test_a_base_tree_that_is_not_a_sha_string_cannot_block_the_capture`, `::test_an_internal_capture_error_still_records_every_section_key` |
| never label absent capture empty | `test_v2_exit_capture.py::test_a_clean_workspace_is_recorded_as_no_change_not_unavailable`, `::test_a_missing_starting_tree_is_unavailable_not_no_change`, `::test_a_truncated_untracked_listing_is_never_recorded_as_an_empty_workspace`, `::test_a_truncated_listing_with_a_failed_tree_still_reports_changes_from_the_status_snapshot` |
| unchanged endpoint bytes, never `submission.diff` | `test_v2_exit_capture.py::test_the_diagnostic_is_never_written_to_submission_diff`, `::test_a_nonexistent_out_dir_is_refused_rather_than_written_as_a_file`, `::test_capture_output_is_write_once_and_a_second_write_refuses` |
| every bound, exclusion and truncation recorded | `test_v2_exit_capture.py::test_all_bounds_and_exclusions_are_recorded_explicitly`, `::test_an_oversized_file_and_diff_are_truncated_with_flags_and_recorded_caps`, `::test_a_malformed_cap_declaration_is_named_and_the_declared_default_is_published` |
| request persistence for failed/rejected calls | `test_v2_request_receipt.py::test_failed_or_rejected_request_keeps_a_full_durable_record_with_unknown_usage_null`, `::test_recorded_dispatch_keeps_the_record_when_the_dispatch_raises` |
| public/raw hash separation | `test_v2_request_receipt.py::test_successful_request_writes_private_raw_and_public_records_with_two_distinct_digests`, `::test_verify_refuses_a_tampered_or_mislabelled_published_projection`, `::test_an_outcome_never_republishes_a_raw_digest_the_retained_bytes_contradict` |
| raw bytes never inside the published tree | `test_v2_request_receipt.py::test_raw_request_bytes_may_not_be_stored_inside_the_published_tree`, `::test_a_published_directory_inside_the_private_directory_is_refused` |
| explicit transformation metadata | `test_v2_request_receipt.py::test_public_projection_replaces_home_paths_and_withholds_secrets_with_transformation_metadata`, `::test_a_credential_in_a_list_or_under_a_token_key_is_withheld`, `::test_a_truncated_error_detail_says_so_and_a_short_one_does_not` |
| unknown server usage stays unknown | `test_v2_request_receipt.py::test_known_usage_totals_and_partially_unknown_usage_stays_unknown`, `::test_a_server_reported_total_is_kept_even_when_the_pair_is_unknown`, `::test_a_server_total_that_disagrees_with_the_reported_pair_is_recorded_not_overwritten` |
| preflight count only with its method | `test_v2_request_receipt.py::test_preflight_token_count_is_always_published_with_its_method`, `::test_a_preflight_token_count_without_its_method_string_or_with_extra_claims_is_refused` |
| receipts never relabel a terminal assignment | `test_v2_request_receipt.py::test_a_receipt_failure_after_dispatch_never_replaces_or_aborts_the_episode_result`, `::test_a_pre_dispatch_receipt_failure_still_refuses_before_the_model_is_called` |
| no receipt hole reported as a complete set | `test_v2_request_receipt.py::test_completeness_names_every_hole_in_the_published_set`, `::test_a_payload_that_cannot_be_canonicalised_refuses_without_burning_the_attempt` |
| planned comparison: 12 assignments, frozen order | `test_v2_cue_cohort.py::test_the_twelve_assignments_are_in_the_lead_s_frozen_order_with_their_arm_labels`, `::test_each_row_carries_its_detector_mode_and_a_unique_assignment_id`, `::test_the_frame_is_balanced_exactly_as_the_lead_specified` |
| planned comparison: declared limits | `test_v2_cue_cohort.py::test_the_declared_limits_are_the_lead_s_numbers`, `::test_the_baseline_arm_is_declared_as_instrumentation_only` |

Suite counts at publication: `test_v2_cue_detector.py` 77, `test_v2_exit_capture.py` 45,
`test_v2_request_receipt.py` 83, `test_v2_cue_cohort.py` 18. Full suite
(`tests experiments/code_routing/test_estimators_absorbing.py experiments/tools/`): **719 passed, 8 subtests
passed**.

Every expectation in these fixtures is written out by hand in literal form (patterns, call ids, reason
strings, digests, byte counts, caps, exclusions, the 12 rows). Where a git-computed or digest value is
needed, the test computes it with its own explicit invocation rather than through the module under test, so a
defect cannot be cancelled by the same defect in the fixture.

## 4. Retrospective fixture output (published)

[`req005_fixture_landmarks_20260923.json`](req005_fixture_landmarks_20260923.json) holds the detector's
`observe`-mode landmark for all 32 archived episodes of `4927adc`, with the adapter's per-call notes, the
source pins and the planned comparison. Summary:

| | count |
|---|---|
| archived episodes scanned | 32 |
| would have triggered | 21 |
| pattern AAA / ABABAB | 12 / 9 |
| no trigger | 11 |
| triggers with no next budgeted call | 0 |
| cues actually delivered | 0 (retrospective, observe mode) |
| incomplete records across all episodes | 2 |

These are landmarks over saved records. They describe what the detector *would* have marked; they are not an
intervention, an outcome, or evidence that a cue helps.

## 5. Not yet wired into a live runner

Deliberately not done, because it would require editing a frozen source or running an episode:

1. **No episode driver calls any of this.** `pilot_episode.py` is frozen (its hash is in
   `results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json`), so the cue arm's message append, the
   before-cleanup `capture_exit_diagnostic()` call and the `recorded_dispatch()` wrapper around
   `AccountedModel._query` are **specified here but not installed**. Installing them means a NEW episode
   source in the `cue-v1` namespace, reviewed and frozen before use.
2. **No runner/queue for `cue-v1`.** `cue_cohort.py` names the cohort, its output directory and the frozen
   12-assignment order; nothing schedules, resumes or accounts for those assignments, and the output
   directory does not exist.
3. **No `cue-v1` source binding file.** The equivalent of `cohort_binding.json` for the new namespace is not
   written; the plan digest (`plan_sha256`) is the reviewable stand-in until the lead freezes the list.
4. **No host block, no server, no container.** No reservation is claimed, and none is implied by this work.
5. **No grading path touches the diagnostic.** The exit diagnostic is never graded and never marks
   Submitted; `pilot_grade.py` and the endpoint rule are unchanged.
6. **The new-visible-evidence coding guide** the lead requires (archived positive/negative examples, frozen
   before collection) is not written here.

## 6. Open items for the lead

1. **Published projection volume.** The sanitized projection is published in full (`payload_projection_bytes`
   records its size, `payload_projection_bound` says it is unbounded). With up to 576 physical requests and
   an accumulated transcript, this is a large published volume; the lead should approve it or set a bound.
2. **Post-dispatch receipt failures are non-fatal by design.** A failure while recording an *outcome* is
   reported (`dispatch.receipt_errors`, `completeness()`) but does not abort the episode, so a receipt hole
   is possible and is published as a hole rather than silently closed. The pre-dispatch write still refuses.
3. **Sanitization is deliberately broad.** Credential-looking keys, credential-looking assignments inside
   free text and `sk-` style literals are withheld wherever they appear, so a published projection can be
   masked more than strictly necessary; the private raw request keeps the exact bytes.
4. **Retrospective landmarks are descriptive.** 21 of 32 archived episodes would have triggered; that is a
   property of the saved records, not a power calculation or a reason to expect the intervention to work.

## 7. Source pins

New modules and fixtures (sha256):

| file | sha256 |
|---|---|
| `experiments/v2_agent/cue_detector.py` | `3407e6355018dc5fd6708f9c368162cb846fc588d47d636d41e9ac7a18251d6f` |
| `experiments/v2_agent/trajectory_triples.py` | `0b956ea365bf95407b5c0ce8587b12c116ae68c3e5b1de8eec7490b669ca3f3e` |
| `experiments/v2_agent/exit_capture.py` | `a2e299f00ed6521d112ad71c7b8ff12d4991d4a259002092e0ea901b0e3991b5` |
| `experiments/v2_agent/request_receipt.py` | `0ad5223b829fff45ee3f14dc6f954058272be9d692b0557c18fba9da940118b7` |
| `experiments/v2_agent/cue_cohort.py` | `20bcf472c83ca36b07b4704a39ce45d6215a4a4bd9deb7ada0ac19e198c055bd` |
| `experiments/tools/test_v2_cue_detector.py` | `e39b7d612ed58c23a7e7ddd151369374a2891a235c081706f963e8f094481748` |
| `experiments/tools/test_v2_exit_capture.py` | `9c3bdc316e99a97d83d661a87c79aa7e7b36fd4c26174098c55365a29a0f0788` |
| `experiments/tools/test_v2_request_receipt.py` | `ec8b85ca6f7491c75522516255db4343088cc1a584213bb25c596c50e9409987` |
| `experiments/tools/test_v2_cue_cohort.py` | `ef34156a245e82518878880f60ae37e1436f7cbbc9bfa6c15c4b73c43f3d2c5e` |

Frozen yaml-v1 execution sources, unchanged by this work and still agreeing with
`results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json`:

| file | sha256 |
|---|---|
| `experiments/v2_agent/pilot_episode.py` | `164b7878f7a720a74ba913b97ee07ba287a556cb3ac6310aa95d2f2c91dbe6f5` |
| `experiments/v2_agent/pilot_runner.py` | `974df398415db22ed6676e04f0be5c1d93a7599d725f43f03fb989d77cbba10c` |
| `experiments/v2_agent/pilot_cohort.py` | `59d271bd32217bd3c3a56c3dd4c20fd8eadd441377db7334c0932a325100851a` |
| `experiments/v2_agent/pilot_report.py` | `1afa9002344557f4fd518044313f2fd277528a06a5fef667966175804711e10f` |
| `experiments/v2_agent/pilot_grade.py` | `0c2a5a5da861a42fd1dbc79c01ff4b031bff8d0a3cbcda8b90e869161f70e7f1` |

`experiments/v2_agent/workspace_capture.py` is reused unmodified (`TREE_CMD`, `SHA`, `write_once`).

## 8. Live-release statement

**No live episode has been run under this instrumentation.** Every result above comes from deterministic
fixtures and from read-only scans of already published archives. The `cue-v1` comparison is planned and
held: its list, order, sources, limits, cost accounting and failure rules are frozen for review, and the
lead reviews this specification, the fixtures and the published fixture outputs before any live release.
