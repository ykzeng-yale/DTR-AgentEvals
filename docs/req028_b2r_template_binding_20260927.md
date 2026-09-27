# REQ-028B2R: bind the native template to its pinned lexer representation

Lead reviewed a995749:18 mechanics artifact hashes and exact raw/served template
relationship verified independently;43 focused tests pass locally. B2 loaded Klear
healthily, but made zero generation calls and left three unattempted. Driver57073,
model57180 and watchdog57182 are reported absent; owned release recorded.
This is a setup validation defect, not a model-format/competence failure or a
pressure abort. No template or output was changed to get a better model result.

## Source-bound diagnosis

Pinned llama.cpp4fea119de30f6a923992780f6fd5ccb0bee5d47d common/jinja/lexer.cpp
lines53–58 remove one final LF; common/chat.h58–71 parses the lexer result and
stores lexer_res.source, which /props exposes. Lead independently retrieved those
two exact source files and verified hashes:
lexer.cpp3d6774bc2dac477e10ddbee69eff403df36f5925c8512ccf8a249bde5c26dbd7;
chat.h12b3f8a287698b1b5f3f4e020e52162f5026b06596b55946fa865a4a0b3c4abc.
Worker traced common/chat.cpp744–754,765–770,839–840 and server-context.cpp4609–4629
for storage/props; server-context.cpp4930–4943,5060–5069 and server-common.cpp1359–1363
show both apply-template and chat completions use the common template/parser path.
Archive that trace and source hashes with the new setup; no new runner build.

Raw native template3990bytes SHA
f858b0b34b6c89118490c6c087cbbc5df911f56994cc8cb61ee7a619903abcd8;
served3989bytes SHA
f2850fd92c68d5375344b9e09b551e3bbc3124b56f8ca58e468b2c91179bdb51.
Independent byte comparison: raw == served + exactly one LF. The previous check
incorrectly demanded equality of two intentionally different representations.
Do not generalize this observation to arbitrary whitespace-insensitive equivalence.

## Exact new release

B2R repeats only the THREE UNATTEMPTED B2 calls in a new immutable directory.
Read req028_b2_klear_mechanics_20260927.md in full. Same model bytes,binary,template,
q8 cache,32k,batches,decoder,prompts,call order and all resource gates. No model or
prompt edit. Replace the defective props check with BOTH exact pinned hashes above
and explicit raw==served+'\n'; reject any other difference. Require no CR bytes
in this pinned raw template. Do not use rstrip/strip or broad normalization.
Record both originals and the recognized lexer transformation before generation.
Reverify exact source hashes against the pinned archive. The loaded template and
actual renderer remain unchanged; this repairs validation, not execution law.

Before generation, render/tokenize all three actual requests through the same
pinned server and freeze full strings/IDs/counts/hashes. Keep the B2 long-input
8192–8256 requirement and128token headroom; mismatch stops before generation,
no token search. Subsequent response usage must match these frozen bindings.
Native-source and rendered-prompt checks are separate; accepting the normalized
source alone does not establish any generated-token or semantic equivalence.

Test the exact known LF pair passes and raw/internal whitespace changes, extra
trailing LF,spaces,tabs,CRLF and changed served bytes fail; do not weaken existing
count/first-abort/cleanup/three-call order tests. Freeze and publish reviewed source
before starting. Verify old57073/57180/57182 absent. One static setup<=300sec,
one900sec/31-read admission window immediately aroundPopen; no renewal,unchanged
>=75%normal/nopeer/12GiBdisk. One model load,<=600sec model phase,<=180sec/load/request,
independent watchdog with unchanged thresholds. No retry,restart,fallback,new
weights,extra calls,transport/VM,benchmark,CONFIRM or peer/cache/Lean changes.
Preserve B2 as a failed setup record; B2R is separately labeled new evidence.

Continue implementation/tests/source publication/this run/result publication
without waiting for another checkpoint. Report actual handles/deadlines and raw
terminal or partial evidence, including reasoning fields and allocation/resource
samples. Product goal state remains separate from explicitly authorized work.
Community canonical weight/converter provenance remains unresolved. Lead owns
next competence/transport decision after actual serving evidence.

Readiness55%, change0points, range45–65%; competent fixed-target comparison and
valid inference, final synthesis, independent reproducibility/approved package remain.
