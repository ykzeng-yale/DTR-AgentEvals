# Routing literature and reusable experimental components

**21 September 2026; primary sources inspected 20 September.** This condenses the independent audit at project commit `981f7b9872164697ab79e413a50257c011f11e6f`. The recommendation is a fixed-harness comparison of history-aware routing against competent fixed schedules. The primary contrast holds the initial action fixed and varies information available at decision two; initial-only choose-once routing is a separate secondary baseline. Beating always-small with the present learned LSL schedule does not isolate adaptation.

## Closest experimental designs

### BAAR

[Zhang et al., 2602.21227v1](https://arxiv.org/html/2602.21227v1), §§3–6, Appendices A–G: binary per-step selection using a Qwen2.5-1.5B router and GPT-4.1-mini/4.1 executors. ALFWorld/SciWorld/AppWorld train/test sizes are 2420/200, 2120/200, 105/168; horizons 30/40/40. Five boundary-policy executions inform training strata; SFT precedes boundary-guided RL. Controls include fixed extremes, random, cascading, greedy preference, SFT, vanilla RL, prompted routing and First-Large. Three seeds are averaged. Outcomes differ: binary success, mean progress and TGC. Hard budgets cap large calls at 5/10/15; unrestricted Always-Large is reference-only. Ablations remove synthesis, reference advantage or difficulty bonus. First-Large is competitive; fixed penalties transfer imperfectly across caps. Router cost is excluded and latency estimated from throughput. Appendix D promises code after acceptance; no author repository was verified. Search's unrelated `Baar-Core` is not this implementation. Adopt budget-matched controls; avoid interpreting failed profiling runs as proof of impossibility.

### Router-R1

[Zhang, Feng and You, 2506.09033v3](https://arxiv.org/html/2506.09033v3), §§3–5, Appendices A–E: a trained 3B coordinator reasons, queries experts and aggregates, with four routing rounds. Training mixes 7,000 NQ and 7,000 HotpotQA examples. Seven QA datasets contribute up to 500 evaluation examples each, with smaller Bamboogle; five datasets are out of domain. Six expert configurations use NVIDIA NIM. Metrics include EM/F1 and a transformed output-token price score. Main results use zero cost coefficient; separate experiments vary it. Controls include direct/CoT/SFT/RAG/Search-R1, largest-expert, prompt/learned routers, decomposition and FrugalGPT. Descriptor compression and added experts are examined; format failures and latency are acknowledged. Its intervention changes the coordinator and subqueries, so gains cannot be attributed solely to model identity. Adopt coordinator-only and aggregation controls for system-level comparisons; do not transplant its cost proxy as total execution cost.

### RouteLLM

[Ong et al., 2406.18665v4](https://arxiv.org/html/2406.18665v4), §§3–5, Appendices A–F: one strong/weak decision per query. Arena data yield approximately 65,000 filtered comparisons with a 5,000-example validation holdout; augmentations use MMLU validation labels or judged responses. MMLU, MT-Bench and GSM8K undergo contamination screening. The principal pair is GPT-4-1106-preview/Mixtral-8x7B. Random routing, matrix factorization, similarity-weighted and neural classifiers are compared using performance-gap recovery and strong-call curves. Arena-only models can perform near random out of domain; augmentation matters. Model-pair transfer is examined, not guaranteed. Adopt a pretrained initial-only comparator alongside a domain-trained static control. Do not assume its scores are calibrated for our Qwen pair or that strong-call share measures local resource savings.

## Pinned reusable sources

### RouteLLM: local classifier option

Code: [`lm-sys/RouteLLM@0b64fdafe049e596a3f5657c219329f24af24198`](https://github.com/lm-sys/RouteLLM/tree/0b64fdafe049e596a3f5657c219329f24af24198), Apache-2.0.

Checkpoint: [`routellm/bert_gpt4_augmented@86237e3df400762178ea98379477b8296e66d5e4`](https://huggingface.co/routellm/bert_gpt4_augmented/tree/86237e3df400762178ea98379477b8296e66d5e4). The explicit [LICENSE](https://huggingface.co/routellm/bert_gpt4_augmented/blob/86237e3df400762178ea98379477b8296e66d5e4/LICENSE) is Apache-2.0. Metadata show ungated XLM-RoBERTa-base sequence classification, three labels and maximum 512 tokenizer tokens—not DeBERTa. **Weights remain undownloaded, unloaded and unrun.**

The official [BERTRouter](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/routers.py) locally tokenizes, runs the classifier and uses softmax label 0 as the strong score. A minimal pinned Transformers adapter can preserve that mapping without an inference API. Freeze evaluation mode, tokenization/truncation and threshold. The static policy should choose once from the initial prompt and retain that model throughout the episode.

Avoid importing the whole package unnecessarily: [shared utilities](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/similarity_weighted/utils.py) construct `OpenAI()` at import. The [manifest](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/pyproject.toml) includes OpenAI/LiteLLM and `numpy<2` alongside Torch/Transformers; isolate dependencies from our environment.

The [MF model](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/matrix_factorization/model.py) calls `text-embedding-3-small`. Another encoder changes its pretrained projection's coordinate system even at equal dimension: local substitution requires retraining, not merely configuration. A TRAIN-only TF–IDF/value-regression router is our baseline, not RouteLLM replication. Retain the published comparator even if it transfers poorly, alongside the domain-trained control.

### Router-R1: substantial adaptation required

Code: [`ulab-uiuc/Router-R1@801a240e37701577907c32de27a548af4e6c4430`](https://github.com/ulab-uiuc/Router-R1/tree/801a240e37701577907c32de27a548af4e6c4430), Apache-2.0; expert/checkpoint/data licenses require separate review.

Source hooks include `router_r1/llm_agent/generation.py`, `data_process/prompt_pool.py` and `verl/utils/reward_score/qa_em.py`. They implement consultation, not coding repair. [Training](https://github.com/ulab-uiuc/Router-R1/blob/801a240e37701577907c32de27a548af4e6c4430/train.sh) specifies four GPUs, actor/critic PPO, 225 steps and API placeholders. README/requirements specify Python3.9, Torch2.4/CUDA12.1, vLLM<=0.6.3, FlashAttention, Ray/Hydra and Transformers<4.48. This is not an economical CPU-training baseline.

The [expert adapter](https://github.com/ulab-uiuc/Router-R1/blob/801a240e37701577907c32de27a548af4e6c4430/router_r1/llm_agent/route_service.py) changes prompts, hardcodes aliases/prices, caps completions at 512 and defaults seeds to 42. Its cost is output tokens times a per-million-token price without the million denominator; input/coordinator costs are absent. Caught request failures become error observations with zero completion cost. Local endpoints are possible in principle, but these choices require explicit adaptation and validation.

`qa_test_merge.py` and `qa_test_gen.py` prefer the same test split, fall back to dev/train and do not enforce disjoint validation/test IDs; actual overlap was not measured. The standalone `infer_vllm.py` cap also differs from the training loop. Reuse components only with explicit split, prompt, decision-cap and failure-accounting contracts.

## Design changes supported by this audit

- **Feedback before richer learning:** establish development thresholds for zero-check frequency, false visible passes, eligible-stage occupancy and supported action cells. Define prospective unverified-task handling; never use hidden verification for deployed stopping or remove unfavorable original tasks.
- **Isolate adaptation:** compare stage-only, initial-feature and feedback-aware rules within identical executor prompts, models, stopping and budgets. Include development-selected fixed schedules and the local static classifier. Freeze thresholds before evaluation; report attained budgets rather than retuning on test outcomes.
- **Test the repair choice directly:** development first-large-failure prefixes can compare LL, SL and SS continuations. These are local contrasts; fresh root-to-terminal executions remain necessary for whole-policy comparisons.
- **Count full resources:** separate all model calls, input/output/router tokens, tool time and latency; record profiling/training costs separately. A large-call quota is not a monetary cap. Stop explicitly if no action is affordable.
- **Match precision to the contrast:** use development estimates for the declared paired or fixed-task repeated-execution target, not a marginal value SE. Predefine margins, multiplicity and time-interleaved log/reference collection. More seeds do not create independent tasks; noisy profiling is not an oracle ceiling.

## Evidence boundary

Full methods and specified appendices were inspected, plus official source/configuration/license files and Hugging Face metadata. No prospective power calculation for the principal comparisons was found in the inspected papers. None establishes our uncertainty guarantees. API/source access is not execution validation: no third-party code, models, fits or simulations ran. The local classifier still needs loading, score-equivalence, network-disabled operation and resource checks when computation resumes. Primary snapshots and hashes are retained in ignored `work/routing_source_audit_20260920/`; this document records the portable findings rather than requiring those local snapshots.
