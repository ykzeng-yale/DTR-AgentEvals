# DTR-REQ-026 — reassess on-demand residency

The author explicitly directed the lead to continue making decisions and dynamically load needed resources without impacting other tasks. The earlier request for another host was too broad: REQ-020/021 rejected one simultaneous-residency configuration, not every local execution design. Codex owns this reassessment; Claude Code performs only the bounded source/implementation audit below. Historical failure records remain unchanged.

## Assigned audit

Five-minute, read-only/source-only audit of the existing pinned REQ-020 Klear-8B/Qwen3-4B pair and harness. No model inference, download, VM launch/change, process termination, other-host/cloud inventory or publication by the worker. Report in chat:

1. Exact launcher/server source paths and pins; whether inactive backend unloading preserves full message history and repository state.
2. Whether the agent sandbox VM must remain alive during generation, and which grading resources can be separated in time without changing the strict evaluator.
3. Cache, RNG, serialization, deadline and latency effects. Loading sequentially is a distinct execution configuration requiring validation, not automatically the old kernel.
4. Conservative peak-memory arithmetic including the active model, KV, compute buffers, VM, caches and reserve; identify unknowns explicitly. Separate current peer occupancy from intrinsic configuration capacity.
5. Current task ownership and capacity, plus the smallest isolated DEVELOPMENT discriminator. Do not stop, evict, reprioritize or reconfigure another project's processes.

The lead will review the findings and choose a versioned setup before any resource-intensive execution. This request does not release live/CONFIRM or alter the target, context, decoder, task exclusions, endpoint or existing archives. It supersedes treating simultaneous model residency as the only design worth considering; it does not assert local feasibility before measurement. Free, source-pinned resources can subsequently be loaded within a reviewed admission envelope under the author's instruction; paid capacity still requires separate authorization.

## Acknowledgement

Claude Code acknowledged DTR-REQ-026 in the existing DTR-AgentEvals session and began targeted source/process reads. No implementation files or experiment results have been returned at this checkpoint. Codex's own read-only snapshot found 32 GiB physical RAM and about 63 GiB free disk; `memory_pressure -Q` reported 58% system-wide free at that instant. This OS metric is not a reservation or a proof that a 16-GiB VM plus model can safely be added. Current co-tenants must be preserved.

Readiness **55%, change 0 percentage points, range 45–65%**. Largest gaps: competent fixed-target comparison and valid inference; final empirical synthesis; independent reproducibility and author-approved metadata/package.

## Lead review and decision after the returned audit

Claude completed the source-only audit and reported no experiment launch or file change. The lead independently inspected `pilot_runner.py`'s single-server ownership/stop logic, `pilot_episode.py`'s full-message call path, the pinned text model client, and the archived REQ-020 byte counts. Serial serving between episodes already exists; within-episode routing needs a new residency manager. The task VM retains repository state and stays alive during generation; grading already happens after generation, so its separation is not a new saving. Cold prefill and load delay can affect execution and the 1,800-second operational deadline. Token-identical output across cache states is unproved; it is not a prerequisite for defining a new, consistently applied execution configuration.

At 32k f16 KV, the recorded static component sum for one-at-a-time serving is 25.239 GiB (16-GiB VM plus the larger weights/KV allocation), compared with 32.065 GiB simultaneously. Neither includes all compute buffers, caches or peer/system reserve. The worker found an 8-GiB default server prompt-cache allowance and unmeasured VM workload peaks. The 64k serial static sum is 29.739 GiB and is not a feasible candidate under the current conservative envelope. Current swap occupancy alone does not identify active memory pressure or prove another project caused the block.

**Decision:** reassess a versioned 32k single-resident DEVELOPMENT configuration; keep 64k and live/CONFIRM held. Do not silently remove load time from the fixed operational budget. Do not require equality to the old cached execution kernel: define and apply the new cache/residency convention identically to logger and all target policies, and disclose it. Backend switching is allowed at the prespecified routing opportunities only, with full histories retained, no regeneration, no redraw and no policy-dependent resource exceptions. Infrastructure load/health failures must have explicit lifecycle statuses rather than being guessed to consume a generation attempt.

The next implementation work is a small isolated residency/admission controller and deterministic ownership/history/deadline checks. It must use only owned PID/ports, confirm release before the next load, reject foreign model jobs, bound its own buffers/cache settings, and abort its own work under resource pressure. No production model download, full episode or inference release follows from source feasibility. The lead will inspect that implementation before a capped mechanics probe; the user's resource instruction supplies authority to make that decision without asking for another machine. Competence qualification remains separate from a successful load/unload test.
