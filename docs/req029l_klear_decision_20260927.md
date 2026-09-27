# REQ-029L Klear admission failure and paired-screen decision

The frozen second arm cmp029e-django16560-klear-a ended without a model load,
model call, or sandbox action. Fifteen admission samples over the original
900-second window reported70–73%systemwide free memory, normal pressure, no
foreign inference. None met the unchanged75%gate. The worker retained
ADMISSION_WINDOW_EXPIRED locally. This is infrastructure/resource admission
failure, not a Klear format failure, coding failure, or evidence of general model
incapacity. The cell remains closed with no retry or renewed window.

Direct SSH retrieval replaces remote chat reporting. Lead verified all113worker
archive member hashes and archived6101localcontroller files. Actual OS checks
found worker51624/controller76999 absent; Docker inventory was empty. Worker
records not_loaded/owned_absent, and local guardian confirms owned container
absence after preflight lease expiry. There was no model PID to stop. Full raw
records and audit are results/local_req029/klear_terminal_20260927.

## Separate implementation diagnosis

Worker Base.deadline remains the300-second setup deadline until model.start
returns, although model.start may spend900seconds in admission. Base.finish
persists local terminal evidence but skips network publication after Base.deadline.
The actual admission failure occurred611.484seconds after that reported deadline.
A deterministic data-only fixture executed Base.finish with an expired deadline:
local terminal was retained and no peer publication occurred. This explains why
the controller waited for its own sandbox preflight lease rather than promptly
receiving the worker failure. The sandbox guardian terminated about258.924seconds
after worker admission expiry. This delayed cleanup is distinct from, and did not
cause, the failed memory admission. Preserve both events and all incurred costs.
No source was changed under the completed release.

## Scientific acceptance and next work

The one-task paired screen is incomplete for model-performance comparison.
Qwen's cell is an observed operational format failure after3calls/2actions; Klear
has no task-performance observation. Do not score this as two model task failures,
an empirical null routing effect, or a successful comparison. No eligible patch
exists in either cell, so no candidate evaluator is released. The74Django test
outcomes in prior controls remain within-task evaluator qualification only.

The next implementation work should correct pre-model terminal delivery with a
separate bounded cleanup/publication deadline and executed fake-clock/peer-exit
fixtures. A future direct-SSH internal transport must preserve claims, immutable
bindings, cancellation and independent cleanup, and demonstrate bounded terminal
propagation before any new model run. These are source-only requirements, not
permission to relaunch this cell or tune prompts/thresholds. The owner’s32GiBauxiliary
Mac is a resource candidate; deployment remains contingent on measured memory,
swap/disk envelope and pinned runtime/model attestation. No inference or weight
transfer to that host is authorized by this decision alone.

Lead owns the failure and redesign. More hardware cannot establish competent
comparators, later routing opportunities or valid primary inference. Keep the
fixed primary H/P target and heldCONFIRM. Review remains TWO HOURS; no live job
from this pair remains and no additional monitor is needed.

Readiness55%,change0points,range45–65%; competent fixed-target comparison/valid
inference,final synthesis,independent reproducibility/author-approved package remain.
