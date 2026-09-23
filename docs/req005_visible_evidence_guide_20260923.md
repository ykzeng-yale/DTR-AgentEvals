# REQ-005 visible-evidence coding guide, selected before cue collection

Version 1, 23 September 2026. Lead design for the held 12-assignment `cue-v1` DEV comparison.
This guide uses exposed archived examples to define coding; it is not retrospective preregistration
of those archives. It supplies descriptive mechanism labels, never a replacement success endpoint,
gold-path score, causal effect or confirmatory analysis.

## Unit, landmark and fields

Retain all 12 assignments. Code the first executed action/ordinary observation after the delivered cue,
and the corresponding first action/observation after the silent would-trigger landmark in baseline.
Use authoritative logical-call IDs. Record no-trigger, trigger-without-next-call, cue-not-dispatched,
no-parsed-action and missing-observation distinctly; do not replace them with a zero evidence score
or select only triggered episodes for operational success comparisons. For a parse failure at the
first post-landmark call, record it explicitly; any later response is a separate secondary trace.

Compare visible content with **the entire earlier episode**, not just the immediately previous
output. Store action/observation references and these separate fields:

- `evidence_kind`: new_source, new_reproducer_or_test_output, new_repository_diff,
  diagnostic_error, repeated_or_uninformative, unavailable, or ambiguous.
- `novelty_vs_prior_episode`: yes/no/unknown. New timestamp, ordering or formatting alone is no.
- `task_relevance`: yes/no/uncertain, with a concise reason from the task and visible records.
- `execution_status`: returned, failed, not_executed, or unknown; retain the return code.
- `observation_completeness`: complete, truncated, missing, or unknown. Missing content cannot
  establish no new evidence; a visible new excerpt may establish novelty despite truncation,
  while omitted content and completeness stay unknown.
- `reviewer_reason`: the newly learned fact or why the output adds none. Link the prior and
  current record locations rather than relying on a command-family classifier.

Task-relevant new source, reproduction/test output or an observed repository diff can be useful
new evidence without being a successful fix. A failure traceback can reveal behavior; return 0
alone does not establish repair correctness. A new path/command error is a separate diagnostic_error,
not an observed repository modification or a successful test. A changed command with the same
uninformative listing adds no evidence. One observation can have multiple source facets; preserve
the facets and a primary category with a reason rather than silently double-counting observations.

The worker provides these descriptive labels. The lead independently checks all 12 episodes and
records disagreements/unresolved labels before interpreting the mechanistic table. Do not use
hidden-test results or gold patches to label novelty. Operational Submitted/nonempty eligibility
and any legitimate hidden grade remain separate outcomes with their original denominators.

## Archived positive and negative examples

Positions below are **recorded command positions**, not logical call IDs. Exact logical landmarks
come from the corrected adapter and live driver, not these illustrative ordinal numbers.

| Example and visible record | Label and reason | Claim excluded |
|---|---|---|
| yaml-v1 `sympy__sympy-11618__large__pilot-cp2-wc2-yaml-v1__20260922T074338Z-1b5364/trajectory.json`, command 11: `cat ./sympy/geometry/point.py \| grep -A 50 "def distance(self, p)"`; compare command 10's 20-line excerpt | new_source; newly exposes the zip-based implementation beyond the earlier docstring | Not evidence of a correct edit or a cue effect |
| yaml-v1 `scikit-learn__scikit-learn-10297__small__pilot-cp2-wc2-yaml-v1__20260922T073224Z-a920da/trajectory.json`, command 5 creates/runs `test_ridge_classifier_cv.py` and raises TypeError for `store_cv_values` | new_reproducer_or_test_output; failed execution yields new observed behavior | Not a passing test or working repair |
| yaml-v1 `psf__requests-1142__large__pilot-cp2-wc2-yaml-v1__20260922T080700Z-49aae1/trajectory.json`, command 4 `ls -la`, compared with command 1 | repeated_or_uninformative; same listing adds no information | Action change alone is not informative progress |
| The sklearn/small episode above, command 6 `git diff` returning 128 | diagnostic_error if the repository/path error is new, otherwise repeated; no completed diff exists | Never code new_repository_diff from the command name alone |

All example paths are relative to `results/v2_agent/pilot_20260922_yaml_v1/`; those archives
remain immutable. These examples are classification anchors, not model-visible hints or future
prompt additions. The fixed neutral cue is unchanged. Freeze this guide's hash with the integrated
runner manifest before the first prospective DEV request.
