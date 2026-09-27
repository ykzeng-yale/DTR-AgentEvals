# REQ-028B4 terminal: one serving completion, strict/parser rejection, capped again

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release74ec0e3; source1a8d70214beefe3268f8747a8d08557fac2c81f0; launch evidence5625dea. This06:15UTC checkpoint inspected the existing job and terminal artifacts; it launched no new supervisor, model or request.

## Counts and separate endpoints

- One model load; one logical request attempted; one terminal HTTP200 response; zero infrastructure failures, zero unattempted released requests, zero retries.
- Strict B3call2 full-response format: **0/1**. Literal fence equality: **0/1**.
- Pinned mini-swe-agent parser acceptance: **0/1**. Exactly-one expected-command endpoint: **0/1**.
- **Four** complete matching mswea_bash_command fences. Each extracted body is printf DTR_READY, but multiple actions are rejected by the pinned parser. All four fences lie **inside an unclosed inline think span**, not outside thinking. Character offsets:1742–1784,2729–2771,5275–5317,6187–6229; span0–6965.
- Finish reason **length**;49 input tokens,1536 output tokens,1585 total; zero cached tokens. Both separate reasoning fields are null. Raw content was neither stripped nor executed.
- Response wall78.734768seconds; prompt340.844ms (143.760782tokens/sec); decode78381.717ms (19.583649tokens/sec). Load/health1.082101seconds.

This changed DEVELOPMENT output-budget contract did not repair strict formatting or parser compatibility. No automatic cap increase, repeat, cache search, thinking suppression or reinterpretation of multiple fences is authorized. Serving completion is not task success, repository-repair competence, canonical-model score transfer or benchmark adoption.

## Source binding and retrospective audit

Parser source/config revision04d809ceab9df28f9adaed044884180159172930 is archived byte-exact as JSON strings in parser_source.json. Frozen hashes:
- models/utils/actions_text.py:e5997bba3ae3d541ff418317cc8dd9e9e17657de806679ef38ab1ad74e294047
- models/litellm_textbased_model.py:395bc9bc4a06c18577e73b21c5465f9d22a6d0cc45b006f3d7c9fdaae399e732
- config/default.yaml:112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f

The default YAML inherits the text model's action regex. Verified upstream extraction AST applies re.findall with DOTALL and trims extracted bodies; acceptance requires exactly one action. Independent re.finditer replay agrees on all four bodies. This is a documented extraction/acceptance replay, not execution of the full agent or generated commands. Parser behavior does not protect the thinking boundary; that endpoint is recorded independently.

Before model load, retrospective B3 audit found zero complete matching fences in all three raw responses, and parser rejection in all three. Those descriptive results are separate from B4 and do not rescore B3.

B4 request copied B3call2, changing only max_tokens128→1536 and fresh alias. Rendered bytes and all49 token IDs exactly match B3call2; request usage agrees. Native raw/served template binding and q4_0 allocation verified before generation. Prompt manifest froze06:02:05.134196UTC, before request06:02:05.138406UTC. CLI remained unchanged, including its default n-predict128; explicit request max_tokens1536 controlled this call, confirmed by output usage. No system/prompt/parser/cache alteration.

## Admission, guards and terminal cleanup

Setup05:50:58.186133–05:51:03.216341UTC (5.030208seconds), within300seconds. Original admission window05:51:03.217075–06:06:03.217075UTC was never renewed. First ten scheduled samples were normal/free74 and failed admission. Read11 at06:01:03.927102 and read12 at06:02:03.993871 passed at normal/free75, separated60.066769seconds; final read13 at06:02:04.020544 passed immediately before Popen.

Model phase began06:02:04.020715UTC with deadline06:12:04.020715UTC. Response finished06:03:23.873174UTC; terminal status COMPLETE at06:03:24.614530UTC, about80.594seconds after model phase start. Load/request180-second and global600-second limits were preserved.

All76 watchdog samples: normal pressure1, free34–75%, swap constant233.31MiB (growth0), maximum sampled owned RSS1,517,977,600bytes, minimum disk17,057,316,864bytes, no foreign inference or abort reason. No abort artifact. Effective q4_0 cache:K648MiB+V648MiB=1296MiB. Metal compute148.83MiB and CPU compute3.08MiB are component views, not measured total physical memory.

Coordinated stop journal records one driver request, one durable TERM claim, **exactly one TERM**, no KILL, owned absence confirmed, model returncode0. TERM06:03:23.888299UTC; owned absence06:03:23.997703UTC; parent confirmation06:03:24.604203UTC. No second-interrupt or GGML assertion in raw log. COMPLETE also follows the driver's watchdog-exit0 assertion. Checkpoint ps confirmed supervisor64074, model65440 and watchdog65443 all absent.

## Verification and holds

Verified32 mechanics artifact hashes,50 run-source snapshot hashes,51 launch-source snapshot hashes,allfive runner trace files against previously verified B3 trace,raw response/content/usage against receipt,exact prior request/render/token binding,freeze-before-generation,parser-source manifest hash and deterministic endpoint replay. Launch preflight64 tests passed, including inherited eight real-inert-child cleanup cases. Initial checkpoint verification compared Python tuple spans to their JSON-array representation and raised a type-only assertion; normalized JSON replay then passed without changing any artifact.

Earlier B1 provenance limitations and B2/B2R/B3 unfavorable results remain unchanged. Product goal remains blocked; readiness55%,change0,range45–65%. No transport, VM, benchmark, CONFIRM, new inference, admission renewal or budget extension was performed. Lead retains the next-step decision.
