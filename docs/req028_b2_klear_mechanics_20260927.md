# REQ-028B2: bounded Klear candidate serving qualification

## Lead review and decision

Reviewed B1 f4febb0. Lead independently verified54 stored artifact hashes,
151643 base and26 added-token mappings,151387 normalized merges, exact template
bytes and architecture dimensions against pinned canonical metadata. Seven
focused acquisition/guard tests passed locally. Remote acquisition receipt binds
5027783808bytes to SHA9c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae;
lead did not independently download/hash the5GB model. Both52961/52969 are reported
absent. No model inference occurred. Metadata compatibility is supported; source
weight/converter equivalence is still unknown. Treat this as a named community
artifact, not a reproduction of canonical reported performance.

A6R already demonstrates Qwen q8 serving through24k. Another Qwen repeat would
not establish a usable second model. B2 tests whether the acquired Klear candidate
can load and serve short/tool-format and8k requests under the same guarded32k
configuration. Nominal weights+q8KV=7.073GiB; allow provisional0.5GiB runtime/compute
plus3.2GiB system reserve in planning (10.773GiB total). This is not a measured
resident footprint or capacity guarantee. Normal admission and independent actual
pressure guards decide execution. A failure is a feasibility finding, not a routing
null. A successful literal/fence response is not benchmark coding competence.

## Exact released model, configuration and requests

Use only B1's verified community artifact, revision
0626423882f502d6fe113bd0ddc61970b19d942b and exact SHA above, plus pinned
llama.cpp4fea119de30f6a923992780f6fd5ccb0bee5d47d and previously verified binaries.
Reverify size/hash before loading; assert model metadata and template match B1.
Same32,768context,q8_0K/V,batch128/ubatch32,one slot,two threads,Metal,
flash attention,loopback,no warmup/no prompt cache/no context shift,temperature0,
seed20260927028,effectiveuint32 3081057844,maxoutput128. Preserve native pinned
Klear template; no template edits, thinking/prompt tricks or model substitution.
Record any reasoning channel separately and raw finish reasons.

Exactly THREE sequential generation calls on ONE load, no restart/retry/fallback:
1. A4 original literal request (system Follow the user's formatting instructions
exactly.; user Reply with exactly the text DTR_READY and nothing else.).
2. A4 original fenced-command request, exact original system/user bytes.
3. A5 original8192-token neutral-text request, exact system/user bytes copied
from its first request, fresh ownership/model alias only.
Use original full request fields and decoding contract, no extra fields silently
introduced. Before ANY generation render/tokenize all three with the pinned
loaded Klear template under watchdog protection. Freeze full request/rendered
strings/token IDs/counts/hashes together; require third count8192–8256 and128tokens
headroom. If mismatched, stop before inference and report; no repetition search.
Require each completed response usage to match its frozen prompt token count.
Score calls1/3 literal DTR_READY and call2 exact mswea_bash_command fence/body
printf DTR_READY, separately from infrastructure completion. Never execute output.
Terminal format failure does not trigger retry or stop the remaining calls;
infrastructure/ownership/deadline/resource failure does stop, with rest unattempted.
No24k call is released: use measured8k Klear cost before choosing a larger budget.

## Resource contract and setup tests

Verify B1 and prior owned model PIDs absent and no foreign inference. Use A6R's
once-only static setup<=300sec, followed by one fixed900sec/31-read admission
window immediately at model Popen. Two normal passes>=60sec apart plus immediate
finalcheck;>=75%free,normalpressure,nopeer,>=12GiBdisk. Prelaunch dips may reset
only within this original deadline before ANY Popen. No renewal or second launch.
Model phase<=600sec from prePopen,load/request<=180sec. Keep all loaded watchdog
rules and1-second sampling: adversepressure,free<20%,swapgrowth>512MiB,RSS>11GiB,
foreign inference,disk,ownership/deadline failures stop only owned work.
No peer/cache/Lean changes, extra models, downloads or simultaneous residency.

Publish source before launch with checked command failures. New immutable B2
source/manifests/results, preserving every previous artifact. Before launch test
exactthree-call order/prompts/model substitution restricted to this release,
all bindings frozen before first generation, native-template/count mismatch
stops before calls,first-call infrastructure failure prevents remaining calls
and cleanup occurs,terminal format failure continues without retry,one-Popen
admission/deadline behavior. Reuse prior guard tests; fake tests are not real-model
qualification. Confirm effective q8 allocations from logs before generation.

Publish actual handles/deadlines and raw responses/usage/timings, native template
bindings,allocator values,pressure samples,partial counts and confirmed owned
cleanup. Continue authorized setup/tests/run/publication without tick-by-tick
permission. Product goal state remains separately reported. No transport/VM,
benchmark, primary-target change or CONFIRM released. The lead will use B2 timing
and resource evidence to choose the next exact competence/transport step.

Readiness55%, change0points, range45–65%. Remaining competent fixed-target
comparison/valid inference, final empirical/manuscript synthesis, independent
reproducibility and author-approved submission package.
