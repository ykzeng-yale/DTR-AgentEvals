"""CPU-only live-path qualification; no model weights or evaluator input."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import platform
import resource
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src"
MODEL_MANIFEST_SHA256 = "27d054c155e7767ca2048d66c900d75131bf9a6c263fdce5180e06ed5fe6bad6"
PUBLIC_SHA256 = "b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9"
DEFAULT_AGENT_SHA256 = "e8ef8aa365942d739c2ec5cb0879f60f377d2dc2de8ec670aaedf3bafb45a4c2"
ACTION_PARSER_SHA256 = "e5997bba3ae3d541ff418317cc8dd9e9e17657de806679ef38ab1ad74e294047"
EXCEPTIONS_SHA256 = "0590393c56bee873c79a691dcb4f15cb39c85f1658598b84bfb295bfde56921d"
REQUIRED_TOKENIZER_FILES = {
    "config.json",
    "merges.txt",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_qualification_release(path: Path, expected_sha256: str) -> tuple[dict, bytes]:
    """Load the run release separately from the Qwen model/tokenizer manifest."""
    release_bytes = path.resolve(strict=True).read_bytes()
    if digest(release_bytes) != expected_sha256:
        raise ValueError("qualification release manifest SHA-256 mismatch")
    release = json.loads(release_bytes)
    if not isinstance(release, dict) or not isinstance(release.get("release_id"), str):
        raise ValueError("qualification release manifest has no release_id")
    return release, release_bytes


def load_pinned_default_agent():
    """Load once without CLI imports, preserving exception identity across episodes."""
    import sys

    packages = {
        "minisweagent": UPSTREAM / "minisweagent",
        "minisweagent.models": UPSTREAM / "minisweagent/models",
        "minisweagent.models.utils": UPSTREAM / "minisweagent/models/utils",
        "minisweagent.agents": UPSTREAM / "minisweagent/agents",
        "minisweagent.utils": UPSTREAM / "minisweagent/utils",
    }
    agent_path = UPSTREAM / "minisweagent/agents/default.py"
    parser_path = UPSTREAM / "minisweagent/models/utils/actions_text.py"
    exceptions_path = UPSTREAM / "minisweagent/exceptions.py"
    pinned_modules = {
        "minisweagent.agents.default": (agent_path, DEFAULT_AGENT_SHA256),
        "minisweagent.models.utils.actions_text": (parser_path, ACTION_PARSER_SHA256),
        "minisweagent.exceptions": (exceptions_path, EXCEPTIONS_SHA256),
    }
    for name, (path, expected) in pinned_modules.items():
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"pinned source mismatch: {name}")

    if any(name in sys.modules for name in pinned_modules):
        # Replacing exceptions while reusing the parser/agent splits class
        # identity: normal Submitted/FormatError/limit exits then become errors.
        for name, (path, _) in pinned_modules.items():
            module = sys.modules.get(name)
            if module is None or Path(getattr(module, "__file__", "")).resolve() != path.resolve():
                raise RuntimeError(f"partial or foreign pinned-agent bootstrap: {name}")
        agent = sys.modules["minisweagent.agents.default"]
        parser = sys.modules["minisweagent.models.utils.actions_text"]
        exceptions = sys.modules["minisweagent.exceptions"]
        if (agent.InterruptAgentFlow is not exceptions.InterruptAgentFlow
                or agent.FormatError is not exceptions.FormatError
                or agent.LimitsExceeded is not exceptions.LimitsExceeded
                or agent.TimeExceeded is not exceptions.TimeExceeded
                or parser.FormatError is not exceptions.FormatError):
            raise RuntimeError("pinned-agent exception class identity mismatch")
        return agent.DefaultAgent

    if any(name == "minisweagent" or name.startswith("minisweagent.") for name in sys.modules):
        raise RuntimeError("foreign or partial minisweagent package already loaded")
    root_package = types.ModuleType("minisweagent")
    root_package.__path__ = [str(packages["minisweagent"])]
    root_package.__version__ = "2.4.6"
    root_package.Model = object
    root_package.Environment = object
    sys.modules["minisweagent"] = root_package
    for name, path in packages.items():
        if name == "minisweagent":
            continue
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    exceptions_name = "minisweagent.exceptions"
    spec = importlib.util.spec_from_file_location(exceptions_name, exceptions_path)
    assert spec and spec.loader
    exceptions = importlib.util.module_from_spec(spec)
    sys.modules[exceptions_name] = exceptions
    spec.loader.exec_module(exceptions)

    class MinimalBaseModel:
        def __init__(self, **kwargs):
            fields = {}
            for parent in reversed(type(self).mro()):
                for field in getattr(parent, "__annotations__", {}):
                    if hasattr(parent, field):
                        fields[field] = getattr(parent, field)
            fields.update(kwargs)
            self.__dict__.update(fields)

        def model_dump(self, *, mode="python"):
            if mode not in {"python", "json"}:
                raise ValueError(f"unsupported model_dump mode: {mode}")
            return {key: str(value) if mode == "json" and isinstance(value, Path) else value
                    for key, value in self.__dict__.items()}

    pydantic_stub = types.ModuleType("pydantic")
    pydantic_stub.BaseModel = MinimalBaseModel
    previous_pydantic = sys.modules.get("pydantic")
    sys.modules["pydantic"] = pydantic_stub
    try:
        importlib.import_module("minisweagent.models.utils.actions_text")
        return importlib.import_module("minisweagent.agents.default").DefaultAgent
    finally:
        # DefaultAgent retains its scoped BaseModel class. Do not replace the
        # process-wide pydantic API used by other runtime dependencies.
        if previous_pydantic is None:
            sys.modules.pop("pydantic", None)
        else:
            sys.modules["pydantic"] = previous_pydantic


def load_runner_components():
    """Bootstrap the pinned parser package before importing its adapter consumer."""
    agent_class = load_pinned_default_agent()
    from experiments.lead_req030.native_hf_text_adapter import NativeHFTextAdapter
    from experiments.lead_req030.seaborn_apptainer_runner import run_pinned_agent, sha256_file

    return agent_class, NativeHFTextAdapter, run_pinned_agent, sha256_file


def main() -> None:
    import torch
    from transformers import AutoTokenizer

    release_manifest, release_manifest_bytes = load_qualification_release(
        Path(os.environ["DTR_RELEASE_MANIFEST"]), os.environ["DTR_RELEASE_SHA256"]
    )
    model_dir = Path(os.environ["DTR_MODEL_DIR"]).resolve(strict=True)
    model_manifest = Path(os.environ["DTR_MODEL_MANIFEST"]).resolve(strict=True)
    started = time.monotonic()
    model_manifest_bytes = model_manifest.read_bytes()
    assert digest(model_manifest_bytes) == MODEL_MANIFEST_SHA256
    model_manifest_data = json.loads(model_manifest_bytes)
    assert model_manifest_data["repo"] == "Qwen/Qwen2.5-Coder-32B-Instruct"
    assert model_manifest_data["revision"] == "381fc969f78efac66bc87ff7ddeadb7e73c218a7"
    manifest_entries = {entry["filename"]: entry for entry in model_manifest_data["files"]}
    assert REQUIRED_TOKENIZER_FILES <= set(manifest_entries)
    tokenizer_receipts = {}
    for name in sorted(REQUIRED_TOKENIZER_FILES):
        entry = manifest_entries[name]
        path = model_dir / name
        data = path.read_bytes()
        assert len(data) == entry["size"], name
        assert digest(data) == entry["sha256"], name
        tokenizer_receipts[name] = {"bytes": len(data), "sha256": digest(data)}

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir), local_files_only=True, trust_remote_code=False
    )
    import transformers
    assert transformers.__version__ == "4.51.3"
    assert not torch.cuda.is_initialized()
    DefaultAgent, NativeHFTextAdapter, run_pinned_agent, sha256_file = load_runner_components()
    from experiments.lead_req030.seaborn_public_input import build_seaborn_initial_messages

    public_path = ROOT / "docs/source_snapshots/req030p_seaborn_public/public_task.json"
    public_bytes = public_path.read_bytes()
    public_sha = digest(public_bytes)
    assert public_sha == PUBLIC_SHA256
    expected_messages = build_seaborn_initial_messages(
        public_bytes,
        environment={
            "system": platform.uname().system,
            "release": platform.uname().release,
            "version": platform.uname().version,
            "machine": platform.uname().machine,
        },
    )
    expected_render = tokenizer.apply_chat_template(
        expected_messages, tokenize=False, add_generation_prompt=True
    )
    from experiments.lead_req030.native_hf_text_adapter import single_sequence_token_ids

    prompt_binding = {
        "messages_sha256": digest(json.dumps(
            expected_messages, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")),
        "rendered_sha256": digest(expected_render.encode("utf-8")),
        # Without return_tensors, Hugging Face returns a flat list for one
        # input. Indexing [0] here silently binds only the first token.
        "input_ids": single_sequence_token_ids(
            tokenizer(expected_render, add_special_tokens=False)
        ),
    }
    assert prompt_binding["input_ids"]

    scripted_outputs = [
        "THOUGHT: inert first action\n\n```mswea_bash_command\nprintf 'REQ030X_TOOL_OK\\n'\n```",
        "THOUGHT: inert terminal action\n\n```mswea_bash_command\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```",
    ]
    scripted_ids = [tokenizer.encode(text, add_special_tokens=False) for text in scripted_outputs]
    for raw, ids in zip(scripted_outputs, scripted_ids, strict=True):
        assert tokenizer.decode(ids, skip_special_tokens=False) == raw

    class ScriptedModel:
        """Authored deterministic output; it has no learned parameters or weights."""

        def __init__(self) -> None:
            self.n_calls = 0

        def generate(self, *, input_ids, **_kwargs):
            assert self.n_calls < len(scripted_ids)
            generated = torch.tensor(
                [scripted_ids[self.n_calls]], dtype=input_ids.dtype, device=input_ids.device
            )
            self.n_calls += 1
            return torch.cat((input_ids, generated), dim=1)

    models = []

    def model_factory(record_event, config):
        model = ScriptedModel()
        models.append(model)
        return NativeHFTextAdapter(
            tokenizer=tokenizer,
            model=model,
            model_id="fixture/static-authored-output-no-weights",
            revision="req030x-fixed-script-v1",
            context_limit=32768,
            max_new_tokens=256,
            record_event=record_event,
            device="cpu",
            **config,
        )

    run_dir = Path(os.environ["DTR_RUN_OUTPUT"]).resolve(strict=True) / "runner"
    outcome = run_pinned_agent(
        agent_class=DefaultAgent,
        model_factory=model_factory,
        public_projection=public_bytes,
        run_directory=run_dir,
        apptainer=os.environ["DTR_APPTAINER"],
        image=os.environ["DTR_TASK_IMAGE"],
        image_sha256=os.environ["DTR_TASK_IMAGE_SHA256"],
        workspace_image=os.environ["DTR_WORKSPACE_IMAGE"],
        workspace_sha256=os.environ["DTR_WORKSPACE_SHA256"],
        supervisor=Path(__file__).with_name("bounded_supervisor.py"),
        supervisor_sha256=os.environ["DTR_SUPERVISOR_SHA256"],
        release_id=release_manifest["release_id"],
        release_sha256=os.environ["DTR_RELEASE_SHA256"],
        step_limit=3,
        wall_time_limit_seconds=180,
        model_context_limit=32768,
        model_max_new_tokens=256,
        tool_timeout_seconds=60,
        output_cap_bytes=4096,
        action_cap_bytes=8192,
    )

    assert len(models) == 1 and models[0].n_calls == 2
    assert outcome["result"]["exit_status"] == "Submitted"
    # The exact frozen terminal command prints only the submission marker;
    # the agent's valid submission body is therefore the empty string.
    assert outcome["result"]["submission"] == ""
    run_dir = Path(outcome["run_directory"])
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    requests = [event for event in events if event.get("event") == "request"]
    responses = [event for event in events if event.get("event") == "response"]
    actions = [event for event in events if event.get("event") == "action_finish"]
    run_identity = next(event for event in events if event.get("event") == "agent_run_start")
    assert len(requests) == len(responses) == len(actions) == 2
    assert run_identity["release_id"] == release_manifest["release_id"]
    assert run_identity["release_sha256"] == digest(release_manifest_bytes)
    assert requests[0]["messages_sha256"] == prompt_binding["messages_sha256"]
    assert requests[0]["rendered_sha256"] == prompt_binding["rendered_sha256"]
    assert requests[0]["input_ids"] == prompt_binding["input_ids"]
    assert [event["reason"] for event in actions] == ["exited", "exited"]
    assert events[-1]["event"] == "agent_run_finish"
    assert events[-1]["trajectory_sha256"] == outcome["trajectory_sha256"]
    assert events[-1]["submission_sha256"] == digest(b"")

    receipt = {
        "status": "passed_narrow_inert_runtime_qualification",
        "interpretation": "real_qwen_tokenizer_and_apptainer; authored fake model output; no weights, generated outcome, tests, or evaluator input",
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "release_id": release_manifest["release_id"],
        "public_projection_sha256": public_sha,
        "model_repo": model_manifest_data["repo"],
        "model_revision": model_manifest_data["revision"],
        "model_license": model_manifest_data["license"],
        "tokenizer_files": tokenizer_receipts,
        "tokenizer_class": type(tokenizer).__name__,
        "tokenizer_eos_token_id": tokenizer.eos_token_id,
        "tokenizer_prompt_binding": prompt_binding,
        "adapter_model_identity": "fixture/static-authored-output-no-weights",
        "physical_fake_calls": models[0].n_calls,
        "tool_actions": len(actions),
        "terminal_submission_sha256": digest(outcome["result"]["submission"].encode()),
        "trajectory_sha256": outcome["trajectory_sha256"],
        "run_directory": str(run_dir),
        "elapsed_seconds": time.monotonic() - started,
        "maxrss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": __import__("sys").version,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
    }
    receipt_path = Path(os.environ["DTR_RUN_OUTPUT"]) / "qualification.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
