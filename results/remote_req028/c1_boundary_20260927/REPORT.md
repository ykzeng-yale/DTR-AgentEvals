# REQ-028C1: native thinking boundary diagnosis (deterministic only)

Status: DONE, diagnosis and fixtures only; no serving/parser/template fix or changed acceptance rule. Release87803ca. Investigate skill guided source tracing and hypothesis checks; unrelated skill telemetry/configuration writes and implementation steps were omitted to honor the scoped diagnosis-only release.

## Finding

Klear's opening think marker was **generated output**, not a rendered-generation prefix. Both C0 prompts end with the plain assistant role prefix and contain no opening think marker. Klear's verbose log line3171 records first output token151667, the canonical added token for the opening marker. It emits no closing token151668 and ends at token151645, canonical im_end, at log4079 after stopped-by-EOS4078. Qwen starts with token3617 (TH) at log3211, contains no thinking marker and ends at151645 at6587 after EOS6586. Both HTTP finish reasons stop are thus consistent with end-of-turn, not proof of balanced thinking delimiters.

The source and archived runtime parser explain why Klear's unclosed text remained in content. Klear's native template disables its reasoning-rendering branch with the literal and0 condition at39; the generation prefix at80–82 is plain assistant. The differential parser detects reasoning mode NONE (request-era log2882), generates a content-only parser (2917–2919), and records zero thinking-start/end sequences (2925–2926). Qwen's template has the analogous reasoning branch without and0 (43–45); its runtime parser reports TAG_BASED (2918), recognizes thinking delimiters and generates optional reasoning extraction before content (2957–2963). Qwen happened to generate no thinking tags in this response.

The pinned runner extracts reasoning only when both its API reasoning-format setting and the detected template mode permit it. Default source setting is DEEPSEEK with reasoning auto; CLI help labels the format default auto. Neither actual request nor command sets reasoning_format, reasoning_effort, reasoning enablement or template kwargs; LLAMA_ARG environment overrides were filtered by the archived driver. No evidence supports blaming an explicit none override. Template-detected NONE is the directly observed Klear path.

The pinned mini-swe text parser **does admit** exactly one matching fence anywhere in content: regex findall with DOTALL, strip extracted bodies, then reject unless count=1. No think-span logic occurs in that parser. This is intentional source behavior in the narrow sense of implemented extraction semantics, not documentation that executing content inside unclosed reasoning is safe.

**C0 remains unchanged:** Klear parser acceptance=true, boundary=false, interface gate=false. Qwen parser acceptance=true, boundary=true, interface gate=true. No text was stripped, relabeled or selected to turn Klear into a pass; no generated command was executed.

## Source-line/hash evidence

All eight runner files below were verified byte-for-byte against the existing pinned4fea119de30f6a923992780f6fd5ccb0bee5d47d source archive. Full hashes and numbered excerpts are in source_evidence.json; abbreviated hashes here are identifiers, not replacements for the full archive.

| Evidence | Lines | SHA256 prefix | Conclusion |
|---|---:|---|---|
| Klear native template |29–46,80–82|f858b0b34b6c|Reasoning branch disabled; plain generation prefix|
| Qwen native template |33–49,final generation branch|c979e0e71a3e|Reasoning serialization branch available; plain initial prefix|
| common/common.h |417–424,648–651|7cfcc6a57122|Reasoning API enum and defaults|
| common/arg.cpp |3665–3690|6e71ad4f63c7|Reasoning extraction and enablement options|
| tools/server/server-common.cpp |1317–1363|de3a89422f67|Request overrides and native template invocation|
| common/chat.cpp |1325–1346|a226aa0cbf84|Differential template analysis and support detection|
| common/chat-diff-analyzer.cpp |461–503|5acb9907c78a|Compares assistant examples with/without reasoning|
| common/chat-auto-parser-generator.cpp |100–169|9f76ec58eb8e|NONE disables extraction; remaining text becomes content|
| tools/server/server-context.cpp |1450–1472,1952–1961|2f5d65ce6ef0|Auto thinking detection; EOG sets EOS independently of text closure|
| tools/server/server-task.cpp |412–427|0fd5c8df2525|EOS maps to chat finish_reason stop|
| mini-swe models/utils/actions_text.py |15–38|e5997bba3ae3|One-fence regex accepts surrounding/inline thinking|
| mini-swe models/litellm_textbased_model.py |8,28–36|395bc9bc4a06|Default regex and raw message.content input|

The mini-swe source is archived exactly in local_source_evidence.json's b4_parser_source.json entry, with the previously pinned04d809ceab9df28f9adaed044884180159172930 parser/config hashes. Per-arm log lines, first/last generated tokens and unchanged endpoint replay are in arm_comparison.json.

## Native-format interpretation and limits

Supporting evidence: canonical archived tokenizer template equals the community GGUF template byte-for-byte; canonical token mapping explicitly contains think/open151667, close151668 and im_end151645, and model config EOS is151645. The generated opening tag plus ordinary EOS stop, with native reasoning serialization disabled, is consistent with a learned/native convention that differs from C0's closed-span action boundary.

Limits/contradictions to a stronger claim: rendered prompts do not force the opening tag; neither canonical tokenizer metadata nor the31-byte archived canonical README establishes that an unclosed span is an endorsed safe action channel. README contains only license metadata. Community conversion/weight derivation remains unresolved. One observed output cannot establish training intent, universal model behavior, command correctness or causal attribution to weights versus execution configuration. B3/B4 failures remain archived. End-of-turn and parser acceptance alone do not validate action authorization.

An alternative action boundary would require a **new prospective contract and validation**, independently justified before new outputs: precise channel/delimiter handling, adversarial nested/unclosed/multiple-fence cases, refusal rules, provenance and sandbox tests, fixed endpoints and operational budgets. C1 neither selects nor implements that contract. Stripping markers/selecting a fence is not a proven correction. Current Klear qualification remains closed under C0.

## Sandbox/adapter prerequisites, no provisioning

The existing split_host_proposal.md requires the pinned mini-swe04d809c text model/config on the benchmark host, DockerEnvironment owning task filesystem there, exact authorized task/image and strict evaluator, full-message AccountedModel accounting of every physical attempt, and explicit Submitted workspace capture as the primary patch endpoint. The existing pilot defaults are not automatically a released32k/48-call experiment; lead must freeze limits, task IDs, common prompt/parser, seed/cache and evaluator together.

Before transport: lead must identify the exact authorized benchmark host, secure authenticated/encrypted tunnel direction and endpoints to the mini loopback/v1 service. GitHub access is not inference connectivity. No0.0.0.0 bind, credentials/firewall/peer changes or tunnel is inferred. Adapter must retain request/content hashes, attempt IDs, timestamps, token/finish/error/transport records, no hidden retry or regenerated action, explicit load/resource lifecycle failures and all cold-load/network/queue costs within the frozen deadline. Serial residency and confirmed owned release remain mandatory. No container, adapter, transport or host settings were created or changed.

## Execution and reproducibility

One single-thread Python compute worker, CPU limit300seconds, parent50ms sampled own+child RSS with2GiB threshold and300-second wall guard. Observed wrapper duration0.500seconds, eight samples, combined peak81,166,336bytes; worker peak65,339,392bytes; exit0. This is monitored RSS, not an OS hard address-space guarantee. Three deterministic fixtures passed in0.011seconds, replaying both observed cases and the unchanged parser-versus-boundary distinction. Verified all189 C0 archive hashes. No model load, downloads, network service, inference, generated-code execution, repeated simulation or peer changes. Publication git/GitHub is the separately authorized evidence handoff.

Reproduce offline with python3 experiments/remote_req028/c1_diagnose.py in a fresh checkout/output path; exclusive creation prevents overwriting this immutable run. Source and raw diagnostics are owned new paths only. Product goal remains blocked; readiness55%,change0,range45–65%. Lead chooses the next scientific contract. No benchmark or CONFIRM release.
