# REQ030AG v6 source-image gate correction — 30 September 2026

## Question and evidence

The highest-impact open gate is whether the frozen eight SWE-bench task images
contain the declared source state and whether the v5 failure is an evaluator
implementation defect or a wrong image/data binding. V5 job `27928205` stopped
before source export, controls, model assets, or episodes. Its original gate
discarded the subprocess diagnostics, so the lead released one read-only check
against the eight exact SIFs retained by that immutable attempt.

Diagnostic job `27930700` ran on `pi_gt353/day`, 2 CPU/8 GiB, from 01:35:48 to
01:37:22 ET (1:34), `COMPLETED 0:0`, MaxRSS `8388848K`. It verified the same
v5 manifest SHA-256
`5f21c08e68d83901790ef70b1f591d367455cd1fe4ba4fde165d03ac9921a085` and all
eight retained SIF byte counts and SHA-256 values. Each original Git command
returned zero, had empty stderr, and reported a clean tree. For each image, the
separately scoped `git -c safe.directory=/testbed` check returned the same
HEAD/tree with clean status. All eight observed HEADs differ from the task
dataset's `base_commit`. The full receipt is
[`diagnostic.json`](../results/local_req030/req030ag_image_git_diagnostic_20260930/diagnostic.json),
bound to the completion line's report hash
`4b8deceaf616b864ce789e61ba40e8492ad6c8cfb4084e76649363acc9bf8d20`; the
independently saved log hash is
`fa8805f61ec4fa7b9f29df64e6e2c18d12f15d37dc116ec6a8b6bd34ccba4bb4`.
The diagnostic recorded zero tests, controls, model calls, and task actions.

The safe-directory explanation is ruled out: the original and scoped checks
agree for all eight images. Dirty worktrees and failed Git commands are also
ruled out by the returned statuses and `CLEAN=1`. The pinned SWE-bench source
at evaluator commit `f7bbbb2ccdf479001d6467c9e34af59e44a840f9` explains the
HEAD discrepancy: `make_repo_script_list_py` resets the checkout to
`base_commit`, performs environment setup, then runs
`git commit --allow-empty -am SWE-bench`. That deliberately creates a clean
post-setup child commit, so requiring `HEAD == base_commit` is an invalid
implementation assumption. The first diagnostic did not inspect parent links;
v6 therefore verifies each image is either exactly at the declared base or is
one clean child whose sole parent is that base and whose subject is exactly
`SWE-bench`. Anything else fails closed before source export or controls.

The evaluator wrapper repeated the same mistaken HEAD equality. V6 binds the
fresh grading workspace to the exact checked initial image HEAD, while patch
harvesting continues to compute the candidate diff against the declared
dataset `base_commit`, consistent with the pinned SWE-bench contract. The
baseline/reference controls remain mandatory and unchanged; no weights are
downloaded until both controls pass for all eight tasks.

## V6 release boundary

V6 changes source-state validation, grading's initial-HEAD assertion, failure
receipts, and image transport only. It keeps the exact eight task/family IDs,
public projections, evaluator bundle, model revisions, BF16/B200 runtime,
prompt, decoding, per-task budgets, statuses, endpoints, and uncertainty rules
from v5. It pins each SIF's SHA-256 and byte size from `27930700` and reuses
those same retained SIF files read-only; it does not redownload, rebuild, or
mutate them. The eight expected commit-parent relations remain a per-image
runtime check, not an assumption promoted to evidence by this source review.

Image receipts are now durably written as each SIF passes its hash/size check.
Each source-gate record preserves return code, stdout, stderr, parsed parent
relation, and clean status in the private run summary. This makes a repeat
failure attributable without accepting its exit code alone. The newly pinned
local suite covers exact base commits, the stock setup-child form, wrong
parents/subjects, dirty trees, command failure diagnostics, SIF reuse identity,
and independent replay of the eight diagnostic receipts.

This is one justified replacement of a cohort that had no controls or model
exposure. It remains a purposive eight-family SWE-bench DEVELOPMENT feasibility
screen. It cannot establish the archived MBPP/HumanEval executor's competence,
an H/P router effect, population inference, or CONFIRM. Full benchmark and
CONFIRM remain held.
