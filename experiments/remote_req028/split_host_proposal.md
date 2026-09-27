# REQ-028B source-bound setup proposal (held execution)

Baseline: DTR ddcccd86b93e1dbc5bc79ac753e36e7b06e6ba9b. This is the authorized interface/artifact plan; it releases no benchmark episode, Klear acquisition, conversion, tunnel, or external listener.

## Existing boundaries and source bindings

The existing experiments/v2_agent/pilot_episode.py pins mini-swe-agent 04d809ceab9df28f9adaed044884180159172930 and default YAML SHA256 112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f. Its build_effective_config binds LitellmTextbasedModel to an OpenAI-compatible localhost /v1 endpoint. Full messages are passed through AccountedModel, every physical attempt is logged, and explicit Submitted workspace capture remains the only primary patch submission path. The DockerEnvironment owns the task filesystem; it does not need to reside with the model server. Its strict evaluator and pinned task/image remain on the benchmark host.

Do not blindly reuse pilot defaults (24 calls, 1536 completion tokens, 900-second request timeout, 1800-second episode budget) as the final proposed 32k/48-call configuration. Lead must freeze all these together with task IDs, the common prompt/parser, seed/cache policy and strict evaluator. The four 028A calls qualify only serving mechanics.

Proposed interface: benchmark-host adapter sends complete role/content messages, fixed model alias, context/decoder contract and request ID through an authenticated encrypted tunnel to the mini's loopback server. Both ends retain content hashes, physical attempt IDs, timestamps, tokens, finish reason and transport status. No prompt is regenerated or action redrawn on transport failure; no hidden client retry. Resource/load failures are explicit lifecycle events. Loading, cold prefill, network and queue delay remain inside the declared operational deadline. Frozen task/family splits and all attempted-episode denominators remain unchanged.

No inference tunnel or SSH host configuration was found in the mini's existing configuration check; no SSH listener/forward was observed. GitHub authentication works but does not establish an inference connection. The smallest connectivity decision is the exact already-authorized benchmark host and secure transport direction/endpoint. Do not bind llama-server to 0.0.0.0 or change firewall/credentials by implication. Lead must release a specific transport test before opening a tunnel.

## Stronger-model artifacts and disk

Canonical Klear source: Kwai-Klear/Klear-AgentForge-8B revision fa3d41e92e9ce7a5b4a52a3e7439aa00521f40c9, Apache-2.0. The existing REQ-020 audit lists four BF16 safetensor shards totaling 16,381,516,824 bytes, with immutable per-shard hashes. An unquantized GGUF adds approximately the same amount and Q4_K_M approximately 5,088,494,342 bytes. Simultaneously retaining input, intermediate and quantized output therefore needs approximately 37.85 GB (35.25 GiB) beyond existing assets. That conversion does not fit the mini's current disk envelope and is not authorized.

Preferred proposal: an authorized source-bound conversion elsewhere, using the same pinned llama.cpp converter/quantizer, then transfer only the resulting verified Q4 GGUF to the mini. This requires lead release and exact converter command, dependencies, source/template checksums and output hash. No conversion or transfer has been performed.

A community candidate is metadata-pinned for decision only: mradermacher/Klear-AgentForge-8B-GGUF revision 0626423882f502d6fe113bd0ddc61970b19d942b, Klear-AgentForge-8B.Q4_K_M.gguf, 5,027,783,808 bytes, SHA256 9c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae. Public metadata is saved in results/remote_req028/klear_artifact_metadata_20260927.json. Its exact derivation from the canonical merged fa3d41e9 checkpoint, converter revision and template fidelity are not established by byte identity alone. Do not silently substitute it for the canonical artifact; lead acceptance of provenance is a separate gate.

Holding the existing 2.326-GiB Qwen file plus an approximately 4.739-GiB Klear file requires about 7.065 GiB of weight storage, excluding source/build/archive files. No duplicate final weight copy is needed when renaming a verified partial file. Both files could potentially fit the mini disk with the 12-GiB reserve, subject to a fresh measured gate; acquiring canonical conversion inputs locally cannot.

## Memory and execution law

Single Qwen serving: 2.326 weights + 4.5 f16 KV + provisional 1 compute + zero prompt cache + 3.2 reserve = 11.026 GiB. Single Klear: 4.739 + 4.5 + 1 + 0 + 3.2 = 13.439 GiB. These are provisional component sums, not demonstrated Klear allocations. The 028A model load supplies Qwen measurements only.

If both backends are hosted on the mini they must be serial residents, with confirmed owned release before switching, full messages retained on the benchmark host, and common cold-cache rules for logger and all targets. The benchmark VM remains elsewhere. Initial-S targets do not remove the possible need for L at later decisions or initial-L comparator support. The stronger model may exceed provisional buffers or throughput limits; a successful small-model load does not qualify it.

Required next lead decision: review 028A evidence and its setup-watchdog deviation; select the exact benchmark-host/secure transport plan and exact Klear artifact provenance route. Then release a bounded stronger-model mechanics and transport qualification if justified. Only a later explicit 028C release can select the already-exposed DEVELOPMENT tasks and competence/comparator design. Routing/CONFIRM remains held.

Readiness 55%, unchanged, range 45–65%; competent fixed-target comparison and inference, synthesis, independent reproducibility and final package remain open.
