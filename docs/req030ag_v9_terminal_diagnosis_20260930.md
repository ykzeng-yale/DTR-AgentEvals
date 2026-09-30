# REQ030AG v9 terminal diagnosis — 30 September 2026

Slurm job `27940522` actually started on one RTX PRO 6000 Blackwell
(`pi_gt353/gpu_rtx6000/normal`, 8 CPUs, 128 GiB) at 07:38:49 ET and ended
`FAILED 1:0` at 07:43:11 ET after 4:22. `sacct` reports MaxRSS 12,357,800 KiB;
the Python exception below identifies an implementation integration defect,
so this value is not evidence of OOM. Payload/source checks, all eight task
image/base gates, and source exports completed. The first unchanged-code
baseline control for `psf__requests-2931` started, but produced zero bytes.
The reference control and all 16 model episodes were not attempted. No model
weights were loaded and no task output or empirical endpoint was observed.

The bounded supervisor receipt reports `internal_error`, child return code
`-15`, and zero retained bytes. Static replay shows the caller had already
created the private output path with `O_EXCL`, after which the supervisor
attempted a second exclusive create of that same path. Python raised
`FileExistsError`; the supervisor terminated its process group. This accounts
for the observed receipt/output pair and directly identifies the failure as
an implementation defect, not a control failure, model failure, or capacity
failure. The generic receipt in v9 did not preserve the exception details;
v10 fixes that diagnostic gap as well.

Raw host-bearing evidence is preserved locally, uncommitted, at
`results/local_req030/req030ag_v9_failure_20260930_private/evidence.tar.gz`,
SHA-256 `fc8433613f11189fb6f7327375c8eb2c5c4dcd9940a9c3377d9c508127e3d39b`.
Do not publish those raw paths/logs. The sanitized lead replay and this
classification contain no evaluator/reference output. Since the baseline
control never completed and no model saw any task, the frozen pre-outcome
cohort remains unexposed and may continue under a new immutable release.

Readiness remains 55%, change 0 points, range 45–65%. This execution resolves
the v9 supervisor/output integration diagnosis only; it provides no
competence, routing, fixed-target, or population inference.
