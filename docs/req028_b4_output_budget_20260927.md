# REQ-028B4: one command-interface output-budget diagnostic

## Lead review and diagnosis

B3 70b39a6 completed three HTTP200 responses under guards:33/115,49/128 and
8192/128 prompt/output tokens; wall5.953,6.676,57.111seconds. Exactformat0/3;
all contain inline thinking, lasttwo finish_reason=length. No separate reasoning
field. Lead independently verified39 artifact hashes,allthree raw responses and
rendered/token bindings;58 focused tests pass,including8inert cleanup cases.
Normal model cleanup journal has exactly one TERM,no KILL,exit0; owned61372/
61917/61920 reported absent. Prior pressure/teardown failures remain archived.

The strict128-token diagnostic budget truncated the command response, so it
cannot distinguish inability to emit the command from an insufficient output
allowance. Call1 actually stopped after115tokens with extra text: this is evidence
against assuming a larger budget alone repairs strict literal compliance.
The existing pilot_episode.py already declares MAX_TOKENS=1536; selecting that
pre-existing budget is an interface diagnostic, not favorable-result endpoint tuning.
The benchmark parser searches for a fenced action and permits surrounding text;
strict whole-response equality is a separate, harder diagnostic. Neither passing
a fence check nor stripping thinking establishes repository-repair competence.

## Exact one-call release

Authorize ONE new Klear generation request copied byte-for-byte from B3 call2
(the original fenced printf DTR_READY request), changing only max_tokens128->1536
and fresh model/ownership alias. Same model artifact,runner,native template,
32k,q4_0K/V,batch128/ubatch32,two threads,temperature0,seed20260927028,cache disabled,
no warmup/contextshift. No cacheconfiguration changes or further search. The prior
q4 candidate stands as tested; this varies only the prospective output cap.
No system prompt change,thinking suppression,reasoning postprocessing or alternate
prompt. Copy,verify and freeze raw/rendered/token bindings before generation;
assert same rendered/token hashes as B3call2 with exact raw/served template binding.
Response prompt usage must match49tokens. Preserve all returned content/reasoning
fields and finish reason. No retry or second call,regardless of outcome.

Predeclare separate descriptive endpoints:
1. Same strict full fenced-response equality/format rule as B3call2;retain raw text.
2. Source-bound existing mini-swe-agent text action parsing: exactly one complete
mswea_bash_command fence and extracted body printf DTR_READY. Use the pinned
04d809ceab9df28f9adaed044884180159172930 parser/config source or a documented exact
replay of its extraction rules; archive source hashes and compare with independent
regex replay. Existing config regex is ```mswea_bash_command\s*\n(.*?)\n``` with DOTALL.
Do not change parser semantics or delete thinking text to achieve compatibility.
Report both the complete fence count and whether the fence occurs inside/outside
any inline thinking span; parser acceptance alone is not a reasoning-boundary check.
3. Whether completion stopped or hit1536tokens;input/output counts,times,raw errors,
resource/cleanup status. If capped again,no automatic budget increase or repeat.

This is a changed DEVELOPMENT output-budget contract, not retrospective rescoring
of B3 or adoption of a benchmark configuration. No correctness outcome or routing
contrast is measured. No generated command is ever executed.

## Gates and implementation acceptance

Verify prior owned PIDs61372/61917/61920 absent. Use B3 coordinated stop and all
unchanged guards: once-only setup300sec,one900sec/31read admissionwindow immediately
aroundPopen,two passes>=60sec plus finalcheck,>=75%normal/nopeer/12GiBdisk. One
load,model phase600sec,load/request180sec,independent1sec pressure/free20%/swap512MiB/
RSS11GiB/disk/ownership/peer/deadline stops. No renewal/restart/retry/fallback.
Nominal1536tokens at observed~20tokens/sec is~77sec decode,not a runtime guarantee;
actual180sec request limit applies even if incomplete. Preserve unfavorable results.

Before launch source/tests must be published. New immutable paths; tests establish
request differs only inmax_tokens/alias,one-call count,no retry,normal/abort cleanup,
exact binding,parser cases for zero/one/multiple fences and surrounding/inline
thinking. First analyze archived B3 outputs deterministically (no completed fences)
and keep that retrospective result separate from B4. No model loading if parser
source cannot be bound. Continue setup/tests/run/publication without extra ticks.
No new weights,24kcall,Qwenrepeat,transport/VM,benchmark,CONFIRM,peer/cache/Lean changes.
Lead chooses next competence/transport step after this bounded interface evidence.

Readiness55%,change0points,range45–65%; competent fixed-target comparison/valid
inference,final synthesis,independent reproducibility/approved package remain.
