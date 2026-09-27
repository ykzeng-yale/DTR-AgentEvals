# REQ-029M terminal delivery correction — source only

The Klear admission failure exposed an implementation gap: Base.deadline still
represented setup when admission expired, suppressing peer terminal publication.
This change is source/inert-test preparation only. It authorizes no model,
container, admission retry, download or replacement of a completed approval.

After cleanup and durable local terminal persistence, reporting receives a distinct
window capped at15seconds (the existing cleanup reserve) and absolute release
expiry. Only the transport deadline is temporarily set; execution deadline and
claims remain unchanged, chain is terminal, and the old transport deadline is
restored on success or exception. Poisoned transports are not retried. Reporting
failure retains the local record and an indeterminate publication failure receipt.
A second finish cannot overwrite the immutable local record or dispatch again.
This is a changed execution implementation and must receive a new exact source
approval for any later use. Historical source7aded9d and all run artifacts remain
in Git unchanged; old manifests fail against changed current source inventory.

Six deterministic tests cover setup expiry, absolute-expiry cap/boundary,
poisoned transport, publication exception, and duplicate finish. Existing inert
worker/controller fixtures also exercise both arms and cleanup; fake HTTP,
Docker, tokenization and localGit are explicitly not real inference validation.
No directSSH inter-process transport is implemented by this change. Outer task
dispatch/inspection uses SSH; any future replacement relay needs its own full
binding/cancellation/crash qualification before execution.

Auxiliary MacBook read-only snapshot during this review: M2Max32GiB12CPU,
48%systemwidefree,9456.12MiBswapused,18,527,952KiBdiskavailable,ACattached.
No ollama/llama/mlx/vllm process was returned by the bounded process-name query.
Ollama0.21.2 symlink exists; llama-server was not found at the checked Homebrew
path, which is not a whole-host absence proof. No process stopped or service
started, no weight copied. Capacity remains unqualified: retaining12GiBdisk after
an existing5,027,783,808byte Klear asset would leave only about1GiB for runtime,
artifacts and growth. Actual model working-set/pressure/swap behavior is unknown.
A later deployment specification must bind runtime/weights, admission/abort
conditions and storage headroom. Do not equate32GiBinstalled with32GiBavailable,
weaken the mini's archived75%gate, or reuse a completed task approval.

Readiness55%,change0points,range45–65%; competent fixed-target comparison/valid
inference,synthesis,independent reproducibility/author-approved package remain.
