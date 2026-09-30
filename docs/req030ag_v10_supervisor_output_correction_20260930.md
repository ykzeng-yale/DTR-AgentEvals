# REQ030AG v10 supervisor/output correction — 30 September 2026

V10 preserves the frozen eight-task, eight-family, 16-episode DEVELOPMENT
cohort, the 7B/14B model revisions, task images, prompts, decoding, strict
controls, endpoint, task order, and resource/isolation limits. It changes only
the bounded supervisor/output integration and binds deterministic tests for
that production call path into the immutable source manifest.

V9's terminal failure is diagnosed in
[`req030ag_v9_terminal_diagnosis_20260930.md`](req030ag_v9_terminal_diagnosis_20260930.md):
the wrapper created the output file, then the supervisor attempted an
exclusive create of the same file and exited before a baseline log was
produced. V10 therefore has the wrapper exclusively create only the receipt;
the supervisor exclusively creates the output with `O_NOFOLLOW` and mode
0600. The wrapper verifies the resulting path is a caller-owned regular file
with mode 0600 before reading it. The output directory must be caller-owned,
private mode 0700. Existing output/receipt paths remain fail-closed. Supervisor
exceptions are recorded with bounded type/message diagnostics before the
child process group is terminated, and the wrapper includes that receipt in
its surfaced error. Optional binds are normalized to a list at the exact
Apptainer argument construction point, avoiding a tuple/list integration
failure in direct callers.

The frozen regression invokes the production wrapper with a fake Apptainer
front-end that executes the exact staged supervisor, then checks captured
bytes, file ownership modes, duplicate-output rejection, timeout, output
cap, owner-pipe EOF cancellation, and detached-child cleanup. This is local
mechanism validation, not Slurm namespace qualification or a model/task
result. The immutable remote v10 job remains necessary to verify the same
production path under the pinned Apptainer task image and enclosing job.

One new v10 allocation is justified because v9 produced no baseline evaluator
receipt, downloaded no model asset, and made zero model calls. This is a
continuation of the same still-unexposed cohort after a concrete defect fix,
not a same-task inference retry. The run remains DEVELOPMENT only; full
benchmark and CONFIRM remain held. Readiness stays 55%, change 0 points,
range 45–65%.
