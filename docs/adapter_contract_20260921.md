# v2 routing/logging adapter contract (DTR-REQ-002)

**Status, 21 September 2026 (worker).** This is a design map only. Nothing listed here is installed, implemented or executed: no package, image, weight, container, model, evaluator or fixture runner. Upstream sources were read at the pinned commits by streaming raw files. Every line cited below was re-read at its pinned revision, and all of them matched. The [v2 protocol](experiment_protocol_v2.md) governs the design, and the lead owns every open parameter. Planned fixtures: [`experiments/v2_adapter/fixtures_planned.json`](../experiments/v2_adapter/fixtures_planned.json).

| Layer | Planned | Implemented | Tested |
|---|---|---|---|
| Hook/field map against pinned sources (this file) | yes | n/a (design) | lines re-read at pins |
| Ledger schema and rules (sections 3–4) | yes | no | no |
| Deterministic fixtures, 30 (A01–A12, H01–H13, R01–R05) | specified | no | no |
| mini-swe-agent / SWE-bench / RouteLLM installation | no | no | no |

## 1. Pinned sources, licenses, dependencies

| Component | Pin | License (as recorded upstream) | Dependency facts read at the pin |
|---|---|---|---|
| mini-swe-agent | `04d809c` (v2.4.6) | MIT (`license = {file = "LICENSE.md"}`, classifier) | `requires-python >=3.10`; litellm `>=1.75.5,!=1.82.7,!=1.82.8`, tenacity, pydantic>=2, datasets, openai `!=1.100.0,!=1.100.1` |
| SWE-bench harness | `02e7a74` | MIT (`license = {file = "LICENSE"}`) | `requires-python >=3.10`; docker, datasets, `huggingface_hub>=1.20`, `ghapi<2`, modal, unidiff, tenacity and others |
| SWE-bench Verified data | lead pin `princeton-nlp/SWE-bench_Verified@c104f84` | license field absent | 13 features; **lacks `image`, `log_parser`, `eval_type`, `eval_script`** (see hazard H-1) |
| RouteLLM | `0b64fdaf` | Apache-2.0 (LICENSE; no `license` field in pyproject) | no `requires-python`; **`numpy<2`**; torch, transformers unpinned; also openai, litellm, datasets |
| Router checkpoint | `routellm/bert_gpt4_augmented@86237e3` | Apache-2.0 LICENSE file; no model card | XLMRobertaForSequenceClassification, 3 labels, float32, `model_max_length` 512, ungated |

These source pins are not dependency locks. A lock file for each component must be resolved in an isolated environment before any run, and has not been produced (planned). Selected repositories' own licenses and dataset redistribution scope remain to be recorded (protocol requirement).

## 2. Routing hook: where the adapter sits

The adapter is a **`RoutingModel` implementing mini-swe-agent's Model protocol** ([`__init__.py` L48](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/__init__.py#L48), `query(messages) -> dict`). It is passed to an unmodified `DefaultAgent`. No upstream loop code is copied.

- `DefaultAgent.query` checks the step and cost limits ([L132–139](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L132)) and the wall-time limit (L140–147). It then does `self.n_calls += 1` and `message = self.model.query(self.messages)` (L148–149). So `RoutingModel.query` runs **after** every upstream limit check and receives the exact model-visible history.
- **Logical call index** = the number of `RoutingModel.query` invocations. This equals `agent.n_calls`, because L148–149 are consecutive.
- **Decision 1** fires on invocation 1; **decision 2** fires on invocation K2 (proposed 9) only if the episode reached it. Each assignment is persisted before the backend is touched. The backend is then held for its calls.
- **Budget-ineligible termination** raises a subclass of `LimitsExceeded` carrying an `exit`-role message and `exit_status` `BudgetIneligible`. `run` catches `InterruptAgentFlow`, appends the message and breaks on the exit role (L115–116, L122–124). No draw is made. Upstream has already counted the call in `n_calls`; the ledger records zero requests for it.
- **Physical attempts:** each backend subclasses `LitellmTextbasedModel` and overrides `_query`. `LitellmModel.query` retries only `_query` inside tenacity ([L81–84](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/litellm_model.py#L81)), so one ledger row is written per physical attempt, before sending. The upstream default is 10 attempts ([retry.py L21](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/utils/retry.py#L21), env `MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT`). Set it to P_max, and disable the litellm and OpenAI-client internal retries. Those layers are outside the pins and unverified, so fixture H06 checks the count server-side.
- **Parser:** use the text-based model's single-action regex ([`litellm_textbased_model.py` L8](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/litellm_textbased_model.py#L8); zero or several actions raise `FormatError`, [`actions_text.py` L24–27](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/utils/actions_text.py#L24)). The default SWE-bench config instead uses tool calls with `parallel_tool_calls: true` ([`swebench.yaml` L183](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/config/benchmarks/swebench.yaml#L183)), which allows several actions per call. A text-based SWE-bench prompt config matching this parser still has to be identified at the pin; not verified.
- **Format errors consume logical calls.** `n_calls` rises before parsing, and `FormatError` feeds back a message ([default.py L100–114](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L100)). K2 therefore counts them, identically under every policy.
- **Cost:** local models have no litellm price, and cost calculation raises unless `cost_tracking: ignore_errors` ([litellm_model.py L36, L113–116](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/litellm_model.py#L113)). Plan: `ignore_errors`, `cost_limit: 0` (disabled), `step_limit: H`. Tokens and time are recorded separately.

## 3. Ledger fields (persisted, append-only)

| Record | Fields |
|---|---|
| Episode header | design_id, instance_id, repo, split, policy, replicate, invocation_id, adapter_version, upstream pins, backend pins (weights digest, quant recipe, server version), image digest and architecture, K2, H, P_max, reservation parameters, seed stream id, start_utc |
| Assignment (k = 1, 2) | episode key, k, logical_call_index, prehistory_sha256 (canonical JSON of the messages passed to `query`), remaining budget (calls, tokens, requests), reserve() result per backend, eligible, probability, uniform draw, action, persisted_utc. **Written before any request.** |
| Physical attempt | episode key, logical_call_index, backend, attempt_index (all layers), sent_utc, outcome (ok / exception class), prompt and completion tokens, latency |
| Step | logical_call_index, backend, response sha256, parsed action or FormatError, observation returncode and exception_info (from the environment's `execute`, [docker.py L125–136](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py#L125)) |
| Terminal | exit_status (Submitted / LimitsExceeded / TimeExceeded / RepeatedFormatError / BudgetIneligible / uncaught exception class, as the upstream runner records it, [swebench.py L154–159](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/run/benchmarks/swebench.py#L154)), plus the ledger's exit_class. Classes: submitted, limits_exceeded, time_exceeded, repeated_format_error, budget_ineligible_terminated, infrastructure_retry_exhausted (tenacity re-raises the transport error after P_max), context_window_exceeded, other_uncaught. Also: submission sha256, empty_submission flag, n logical calls, n physical requests |
| Evaluation | evaluation_id, run_id, model_name_or_path, patch sha256, attempt (at most 2), evaluator report path, status (resolved / unresolved / unknown_evaluator_failure / not_evaluated_empty), F2P/P2P counts |

A **submission** is an explicit `Submitted` exit: first output line `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` with returncode 0 ([docker.py L142–149](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py#L142)). Every other exit carries `submission: ""` and scores 0 on the primary endpoint without evaluation. There is no salvage.

## 4. Evaluator mapping (SWE-bench `02e7a74`)

- **Identity and caching:** reports are cached at `logs/evaluation/<run_id>/<model_name_or_path>/<instance_id>/report.json`, and an existing report is returned unchanged ([run_evaluation.py L253–273](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/run_evaluation.py#L253)). Predictions are keyed by instance_id, so one file holds one patch per instance. Plan: one evaluator invocation per evaluation identity, with `run_id = <design>-<instance>-<policy>-r<replicate>-<invocation>-<patch sha256[:12]>` in a fresh log root.
- **Outcomes:**
  - Full resolution requires `f2p == 1 and p2p == 1` ([grading.py L321–322](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L321)). An empty test list scores 1 vacuously (L293–294), so qualification requires non-empty FAIL_TO_PASS.
  - Empty patches are filtered into `empty_patch_ids` (run_evaluation L627–639).
  - A timeout appends a message and raises `EvaluationError` (L375–381). Errors write no `report.json` and land in `error_ids`. The contract maps these to **unknown_evaluator_failure**, not unresolved, with at most one retry on the identical patch.
  - The run summary goes to `logs/evaluation/<run_id>/results.json` ([reporting.py L170–172](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/reporting.py#L170)).

## 5. RouteLLM initial-only baseline (secondary)

These facts are verified at `0b64fdaf`:
- The score is float32 `1 - np.sum(softmax(logits)[-2:])`, i.e. the label-0 probability computed upstream's way ([routers.py L117–130](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/routers.py#L117)). Tokenization uses `padding=True, truncation=True` with no `max_length`. Logits are taken with `.numpy()`, so on CPU.
- The router routes strong iff `score >= threshold` (L42). Thresholds outside [0, 1] are rejected ([controller.py L88](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/controller.py#L88)).
- The controller routes on `messages[-1]["content"]` (L110).
- The default config names the checkpoint without a revision (L26).
- Importing `routellm.routers` builds an `OpenAI()` client at import time ([similarity_weighted/utils.py L11](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/similarity_weighted/utils.py#L11)).

Planned adapter:
- It does **not** import `routellm`. It re-states those six scoring lines against Transformers, loads the checkpoint at revision `86237e3` offline in eval mode on CPU, and records tokenizer truncation side and length.
- It scores the pre-call-1 `messages[-1]["content"]` once per episode and keeps that backend for all calls.
- It calibrates the threshold on development data only (protocol §4), not on the upstream Arena thresholds dataset.
- Label meaning ("label 0 = strong wins outright; ties count against strong") comes only from an upstream code comment.

## 6. Hazards for the lead (facts; decisions are yours)

- **H-1 (blocking; the lead chooses the fix):** the evaluator requires instance fields `image`, `log_parser`, `eval_type` and `eval_script` ([utils.py L255–270](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/utils.py#L255)). Its loader neither enriches instances nor pins a revision (L137–187). The pinned `princeton-nlp/SWE-bench_Verified@c104f84` card declares none of the four. Reading the source, the pinned pair would fail at `make_test_spec`; this has not been executed.
  - Option (a): re-pin the dataset to `SWE-bench/SWE-bench_Verified`. Current revision `78f471bf`, modified 2026-08-16, 500 test rows, all four fields, license field absent.
  - Option (b): re-pin the evaluator to a revision that builds test specs from repo constants.
- **H-2:** mini-swe-agent's runner derives its workspace image from `image_name`/`docker_image`, falling back to a mutable `sweb.eval.x86_64.<id>:latest` tag ([swebench.py L70–75](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/run/benchmarks/swebench.py#L70)). It never reads `image`. The adapter must pass one digest-pinned image to both agent and evaluator (fixture H11).
- **H-3 (runtime; this host):** arm64 macOS, no container runtime (no Docker, Colima or Podman), 32 GB unified memory, repo venv Python 3.12.13. The images are x86_64, and the evaluator needs Docker; the lead's audit notes it requests SYS_ADMIN. Execution here would need a container runtime plus emulation, or a separate x86_64 worker. I will not install system software; that is the user's decision.
- **H-4:** mini-swe-agent does not truncate history. `ContextWindowExceededError` aborts without retry (litellm_model L54) and ends the episode as an uncaught-exception exit. At a 16,384-token context this exit class may be common. It needs a declared endpoint treatment (proposed: a limit exit, in the denominator, primary 0) and a pre-action context check inside reserve().
- **H-5:** `numpy<2` in RouteLLM conflicts with this repo's numpy 2.5.3. This is one more reason for the narrow adapter.

## 7. Open parameters (lead)

- K2 and H (proposed 9 and 24).
- P_max across all layers.
- The reserve() rule and its numbers, including the context check.
- Wall-time limit.
- Evaluator timeout (upstream default 1,800 s) and retry allowance.
- Dataset/evaluator re-pin (H-1).
- Text-based prompt config.
- RouteLLM threshold calibration set.
