# REQ-028: continuing Mac mini experimental execution program

The author explicitly requests a continuing remote Codex task/goal, shared
GitHub coordination and close lead iteration to obtain experiments needed by
this paper. Codex on the lead host owns design, metrics, inference and acceptance.
The dedicated Mac mini Codex implements and runs this program directly; no
Claude or existing Lean chats are involved. This supersedes earlier no-download
and no-inference restrictions **only for the bounded stages released below**.

## Objective and completion criteria

Qualify an isolated model-serving contribution from the 16-GiB mini, connect it
to the existing benchmark execution design if feasible, and produce immutable
DEVELOPMENT evidence needed to decide whether the frozen competent fixed-target
comparison can proceed. Infrastructure success alone does not complete the
scientific program. Do not stop after inventory or a successful build: continue
through every authorized stage, report concrete milestones, and bring a precise
failed gate or next design decision to the lead when a stage is held.

1. **028A, authorized now:** install/build a pinned isolated runner, retrieve the
   already selected Qwen3-4B artifact, and perform the exact serving mechanics
   qualification below. This is real-model inference, not task competence.
2. **028B, setup planning authorized:** prepare the source-bound split-host
   execution interface and stronger-model artifact plan using the existing
   Klear/Qwen pair and strict evaluator. Inspect already configured secure
   connectivity; do not expose a network listener or change credentials/firewall.
   No Klear download/conversion, benchmark episode or network-service release
   until lead review of exact sources, disk peak and execution law. Report the
   smallest remaining decision while continuing independent setup documentation.
3. **028C, held:** lead freezes already-exposed DEVELOPMENT task IDs, comparator
   allocation, common execution configuration and acceptance metrics; worker
   implements/runs that qualification only after the corresponding release.
   Full routing/CONFIRM stays held. No target changes or tuning on CONFIRM.

## 028A exact sources and configuration

Repository baseline: current published `main`, including `5030979`; read AGENTS,
README, research proposal, theory, protocol and REQ-020/026 decisions. Use a
separate remote checkout. Own only `experiments/remote_req028/` and new
`results/remote_req028/` outputs; lead owns design/handoff/readiness documents.

- Runner: official `ggml-org/llama.cpp`, commit
  `4fea119de30f6a923992780f6fd5ccb0bee5d47d`. Build locally with available official
  compiler/CMake, at most two build jobs. No global package replacement. If an
  essential tool is absent, isolated official package installation is permitted
  within resource caps; pin its version and retain license/source provenance.
- Model: `unsloth/Qwen3-4B-Instruct-2507-GGUF`, revision
  `a06e946bb6b655725eafa393f4a9745d460374c9`, file
  `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2,497,281,120 bytes, SHA-256
  `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`.
  Download directly from this pinned Hugging Face revision; verify before use.
  Apache-2.0 attribution; retain model/template metadata. No alternative model
  or quantization substitution. Do not load the existing Kimina/Lean artifact.
- One owned server, loopback only, unused port chosen and recorded before
  launch. Context 32,768, one slot, f16 K/V, prompt cache RAM disabled, per-request
  cache disabled, temperature 0, seed 20260927028, max output 128 tokens. Record
  actual supported flags from pinned source/help; refusal beats silently ignored
  cache/context flags. Metal use is allowed with no foreign inference resident.
- Full source/config/template hashes, process ownership token, prompts, runner
  command and response schema must be frozen in a new manifest before inference.
  Keep raw stdout/stderr, responses, timings, token counts and resource samples.

Four sequential logical calls, no automatic retry, identical system message
`Follow the user's formatting instructions exactly.`:

1. User: `Reply with exactly the text DTR_READY and nothing else.`
2. User: `Return exactly one fenced code block labelled mswea_bash_command containing the command printf DTR_READY. Do not add any other text.`
3. Repeat call 1 after stopping the owned server, confirming exit and restarting
   with the same configuration.
4. Repeat call 2 on the restarted server.

Never execute generated commands. Record literal and fence-format compliance
descriptively, with failure preserved. These four responses cannot establish
coding competence, determinism in general, throughput at full context or routing
benefit. Primary mechanics acceptance: verified source/model pins; successful
32k allocation and healthy serving; four recorded terminal requests or explicit
failure; no unintended model residency; confirmed owned-process release; no
resource abort. Record observed tokens/sec and load/response times separately.
Format failure is not an infrastructure failure. A failed first load does not
authorize silently lowering context, changing KV type, or trying another model.

## Resource and isolation envelope

No VM or benchmark execution on the mini. Static planning: 2.326-GiB weights +
4.5-GiB f16 KV + provisional 1-GiB compute + zero prompt cache + 3.2-GiB reserve
= 11.026 GiB, below 16 GiB; compute is an estimate requiring runtime observation.
Admission: normal pressure, no foreign active model job, at least 75% system-wide
free under the recorded macOS pressure metric, and at least 12 GiB disk remaining
after projected downloads/build outputs. This metric is a guard, not a memory
reservation or exact available-byte estimate. During own load/generation sample
pressure/free metric, swap and owned RSS every second. Abort own work if pressure
is adverse, free metric falls below 20%, swap grows by >512 MiB from admission,
owned RSS exceeds 11 GiB, or a foreign inference workload appears. Metal memory
may not all appear in RSS; retain system-wide guards. Do not stop peer processes.

Setup/download/build cap 45 minutes, 5 GiB downloaded and 8 GiB added disk;
inference phase cap 15 minutes total, 180 seconds per request, 180 seconds per
load. Two CPU build jobs maximum; one server and one request at a time. An
independent watchdog must stop only owned processes on caps/pressure; implement
and fake-test ownership/deadline/cleanup first. Do not import the unaccepted
REQ-026B controller. Keep failure records and partial downloads; no blind retry
loop or deletion of unrelated data. No paid resources, privileged changes,
Lean infrastructure edits or unisolated execution of model-generated code.

## Coordination and publication

Set a remote `/goal` for this continuing experimental objective at the user's
explicit request. If a goal already exists, inspect and report it rather than
inventing completion. A held later stage is a lead decision checkpoint, not a
claim that the full objective is complete. Report active goal status and actual
process/job handles. Do not burn a continuous goal loop solely waiting for a
download or lead decision; use the existing coordination mechanism.

Clone public GitHub with existing access; do not copy credentials from the lead.
If authenticated write access is already available, publish owned setup/results
directly to main after validation, fetching latest and preserving concurrent
commits. Both author and committer: Yukang Zeng <ykzeng2019@gmail.com>; no PR,
force-push or vendor trailers. Do not commit weights/binaries/credentials/private
process listings. Use issue #4 for material milestones if write access works.
If not, continue all local authorized work and return compact receipts plus
source/artifact transfer for the lead to integrate. GitHub auth is not a reason
to stop setup or inference. An implementation receipt is not scientific acceptance.

Milestones: acknowledged goal/checkout; download/build with active handles;
model-loaded/first actual inference; completed qualification or exact failure;
028B proposal. Lead uses event-driven `wait_threads` while active, plus the same
15-minute heartbeat fallback. Remote-to-lead push has failed and is not assumed.
No duplicate monitors or experiments. Do not stop after each command for new
instructions when the next step is authorized above.

Readiness **55%, change 0 points, range 45–65%**. Remaining milestones: competent
fixed-target comparison and valid inference; final empirical/manuscript
synthesis; independent reproducibility and approved submission package.
