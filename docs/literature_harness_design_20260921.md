# Harness-grounded prospective design

**Status:** primary literature and official source inspected on 20 September 2026; proposal only. No packages, weights or images installed; no model, benchmark, candidate-code or Monte Carlo execution. The lead owns adoption and final protocol choices. The [main protocol](experiment_protocol_v2.md) controls the operational endpoint, routing eligibility and failure handling; shorthand here does not supersede that design.

## Recommendation and scientific question

Use **mini-swe-agent + a qualified SWE-bench Verified subset** for substantive repository repair. Ask whether realized tool feedback improves model allocation beyond the initial issue and fixed schedules, and whether randomized logs estimate frozen policies' fresh-execution values. [SWE-bench](https://arxiv.org/html/2310.06770v3) supplies repository issues and executable repair/regression tests. Its original evaluation is not identical to the current harness. [BrowserGym/AgentLab](https://arxiv.org/html/2412.05467v4) supplies a useful browser-interaction alternative, including action-error feedback, but benchmark-specific verifiers still need qualification. Neither paper establishes our proposed models' capability or a new DTR identification result.

## Pinned sources and license scope

| Component | Inspected revision | License |
|---|---|---|
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent/tree/04d809ceab9df28f9adaed044884180159172930) | `04d809ceab9df28f9adaed044884180159172930` | MIT software |
| [SWE-bench](https://github.com/SWE-bench/SWE-bench/tree/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e) | `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e` | MIT harness |
| [BrowserGym](https://github.com/ServiceNow/BrowserGym/tree/9e779f087de9a65668b6974d11f9ce9816026e96) | `9e779f087de9a65668b6974d11f9ce9816026e96` | Apache-2.0 |
| [AgentLab](https://github.com/ServiceNow/AgentLab/tree/cbc35a9bc0facaf731bc858c5825edbe757c719f) | `cbc35a9bc0facaf731bc858c5825edbe757c719f` | Apache-2.0 |
| [MiniWoB++](https://github.com/Farama-Foundation/miniwob-plusplus/tree/7fd85d71a4b60325c6585396ec4f48377d049838) | `7fd85d71a4b60325c6585396ec4f48377d049838` | MIT |
| [SWE-bench Verified dataset](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/tree/c104f840cc67f8b6eec6f759ebc8b2693d585d4a) | `c104f840cc67f8b6eec6f759ebc8b2693d585d4a` | API license field absent |
| [Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct/tree/c03e6d358207e414f1eca0bb1891e29f1db0e242) | `c03e6d358207e414f1eca0bb1891e29f1db0e242` | Apache-2.0 |
| [Qwen2.5-Coder-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct/tree/aedcc2d42b622764e023cf882b6652e646b95671) | `aedcc2d42b622764e023cf882b6652e646b95671` | Apache-2.0 |

Software licenses do not relicense dataset text, upstream task repositories, model weights or dependencies. Record each selected repository's license and resolve dataset redistribution scope separately. Converted/quantized weights require their own digest and recipe. Source pins are not complete dependency locks.

## Hooks, feedback and verification

The routing hook is [`DefaultAgent.query`](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L130): switch the backend while preserving messages and the same workspace. Shell outputs, exit codes and exceptions become observations. Submission, limits and formatting failures terminate execution; none proves correctness. Public tests/reproduction scripts may inform routing. Hidden test patches, reference solutions and terminal grading logs must remain outside the agent history.

[Transport retries](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/utils/retry.py#L19) default to ten attempts. Hold assignment fixed and count physical requests across all retry layers. A common fenced-command parser can avoid native-tool compatibility assumptions, but its prompt must match that parser. Missing local-model prices can record zero cost; measure tokens and time separately.

The [SWE evaluator](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/run_evaluation.py#L229) executes submitted patches separately. [Full resolution](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L309) requires fail-to-pass and pass-to-pass criteria. Require **nonempty FAIL_TO_PASS**, a failing no-change control, passing reference-patch control and unambiguous required-test mapping. Empty PASS_TO_PASS is not an automatic exclusion: disclose that regression preservation is untested for that issue. Empty sets pass vacuously in the grader; it also documents truncated test-ID ambiguities. Success remains test-suite-relative.

Reports are cached by run/model/instance; each policy/seed needs a distinct immutable evaluation identity. The runner may use mutable x86_64 image tags. Pin actual image digests and verify architecture. Current evaluator containers request `SYS_ADMIN`; use dedicated disposable workers, not personal workspaces.

## Minimal development experiment and acceptance

Candidate backends are the pinned 7B/14B code models above, served locally with common precision conventions, prompts, decoding, context truncation and action permissions. Proposed starting limits: 16,384 context tokens, 1,536 output tokens, 24 logical calls. Choose A1 at start and A2 immediately before call 9 if still active; retain A2 thereafter. Absorb terminated episodes without exclusion. The 8/24 split requires development qualification.

Pilot: **20 development issues × SS/SL/LS/LL × one execution = 80 trajectories**, randomized execution order. Maximum 1,920 logical calls; at two physical attempts per call, maximum 3,840 requests and 5,898,240 requested output tokens, plus input processing and evaluation. No paid endpoint fallback. Worker calibration must establish an affordable cap first.

Proceed only after evaluator controls pass, some terminal successes and failures occur, useful feedback varies, and sufficient trajectories reach decision two. Pragmatic failure flags: zero successes across schedules, over 10% infrastructure failures, or fewer than half reaching call 9. These are development criteria, not significance tests; routing improvement is not an acceptance requirement. Revise failed settings only on development tasks, never select confirmatory issues because routing helps.

Then randomize each eligible routing decision with known probability 1/2 in training logs. Freeze SS, SL, LS, LL, a prompt-only continuation router and a comparably constrained history router. Include constant actions in the learned class. Fit/tune outside confirmation. The focal routers can share initial S, differing only in access to realized feedback. Deterministic-policy weights are bounded by 4 because there are at most two routing decisions, not 24.

Primary endpoint is terminal success; report actual compute separately and freeze any utility/cost constraint prospectively. Evaluate frozen policies through fresh execution on disjoint issues, interleaving policies and preserving all exits. Set confirmatory size from desired precision and measured resources before collection. Repeated seeds share task clusters; issue splitting alone does not imply repository generalization. A router collapsing to a fixed schedule is valid negative evidence for adaptivity.

## Browser alternative and resources

AgentLab's [`GenericAgent.get_action`](https://github.com/ServiceNow/AgentLab/blob/cbc35a9bc0facaf731bc858c5825edbe757c719f/src/agentlab/agents/generic_agent/generic_agent.py#L97) is the corresponding hook; preserve plan/memory/history. Parser retries and provider retries can multiply calls. BrowserGym returns action errors, task termination and wrapper-dependent truncation.

For a separately labeled synthetic pilot, inspect MiniWoB book-flight and email reply/forward workflows. Their task code uses binary terminal outcomes, whereas the [adapter](https://github.com/ServiceNow/BrowserGym/blob/9e779f087de9a65668b6974d11f9ce9816026e96/browsergym/miniwob/src/browsergym/miniwob/base.py#L179) binarizes any positive reward, potentially accepting partial credit elsewhere. Use terminal full-success predicates, trusted positive/negative controls, strict single-action element operations and no arbitrary Python/JavaScript. Hide evaluator internals; ordinary UI feedback remains available.

mini/SWE require Python ≥3.10 plus Docker and inference dependencies. AgentLab requires Python ≥3.11,<3.13 and includes Torch/Ray/Dask; BrowserGym pins Playwright 1.44 and requires Chromium. Existing Python 3.14 is not assumed compatible. GPU memory, model residency/reloading, throughput, image storage, CPU/RAM and runtime locks remain unmeasured. No execution or GPU-fit promise follows from this source review.
