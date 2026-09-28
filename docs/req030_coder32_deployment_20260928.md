# REQ030B: canonical coding-model deployment on Bouchet

## Decision and scope

After actual B200/PyTorch2.9.1/CUDA12.8 qualification, deploy a canonical coding-specialized model that fits the newly available memory. The user explicitly requests progression to remaining experiments. This release authorizes one acquisition and one dependent batch inference job, not the full benchmark or a retry on exposed failed tasks. A larger coding model is a prospective comparator candidate, not an established competent comparator. The fixed primary H/P target and CONFIRM remain held.

Qwen/Qwen2.5-Coder-32B-Instruct, revision **381fc969f78efac66bc87ff7ddeadb7e73c218a7**, Apache-2.0. Official model card: https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct . The model manifest pins23 files by byte size and SHA256, including14 safetensor shards, native tokenizer/template, config and license. Total65,539,411,204 bytes. No community converter/provenance substitution. No trust_remote_code. This CUDA/BF16/Transformers kernel differs from earlier Metal/GGUF; do not pool or claim causal precision/backend effects.

## Frozen implementation and budget

Sources `experiments/lead_req030/coder_*`, test `test_coder_prepare.py`. Nineteen exact PyPI wheel URLs/hashes/versions, including Transformers4.51.3, Accelerate1.6.0, Tokenizers0.21.1. Torch and base Python dependencies supplied by existing Yale module PyTorch2.9.1-foss-2024a-CUDA-12.8.0. No dependency resolution during installation; wheels install with no-index/no-deps into run-local packages, not a shared environment. Smoke import before weight acquisition. Model acquisition is bounded by exact total bytes, socket timeouts and2200sec monotonic deadline; no retries/resume. Reserve80GiB project storage for weights/runtime/artifacts. Existing group project quota49/4096GiB at last dated snapshot comfortably accommodates this; filesystem availability checked separately before stage.

Unique directory `req030-coder32-deploy-20260928-a`, pi_gt353. Both accounts user-authorized. Latest identical1hour/oneB200/8CPU/128GiB test-only estimates favored GT (Sept27 21:37:55ET) over FL (Sept28 11:19:55ET); these are predictions, not reservations. Existing other user jobs left untouched. Actual GPU duration below is shorter.

Preparation: day partition,4CPU/16GiB/40min, no GPU;2300sec process timeout with15sec kill fallback. Inference: afterok dependency, oneB200/8CPU/128GiB/30min,1700sec process timeout with15sec fallback. Slurm independently bounds all owned processes. `--kill-on-invalid-dep=yes` prevents an orphaned dependent job after preparation fails. Exclusive claim files reject accidental execution twice. Remote script SHA checks before work. Shell exit receipts preserve failures; Slurm accounting remains authoritative if hard kill prevents receipt. No model services/listeners, generated-command execution, container, evaluator, hidden tests or reference inputs.

One model load, BF16, SDPA, native template, seed20260928030, greedy generation, max256 output per request,32768context. Exactly two authored deployment requests: short context-manager description, and fixed inert padding ending in integer731. No benchmark task is present. Save full rendered text/token IDs before each generation, full output IDs/raw text, finish reason, latency and peak allocated GPU memory. Never execute generated text. Outputs and logs expected below4MiB; finite token caps prevent unbounded generated output. Preserve length-stop as observed, never silently rerun.

## Acceptance and next scientific action

Five downloader identity/size/deadline regression tests passed, Python compile and shell syntax checks passed. Before real submission validate exact staged scripts with Slurm test-only. Submit each stage once; record job IDs and reconcile ambiguous responses before any action.

On terminal review verify all model/wheel receipts against pins, native input binding, exactly two physical generations, memory/latency, raw EOS/length and content; deployment success is not task competence. Then freeze the next pre-outcome development task(s), qualified sandbox/evaluator and model comparison kernel before task inference. Do not replay Astropy/Django/Matplotlib failures or forward evaluator feedback to this model. If acquisition/runtime fails, diagnose retained evidence, not an unlimited retry or new model search.

Readiness55%,Δ0,range45–65%; remaining competent comparisons/valid inference, manuscript synthesis and independent reproducibility/author-approved package. This release resolves a capacity/runtime gate only.
