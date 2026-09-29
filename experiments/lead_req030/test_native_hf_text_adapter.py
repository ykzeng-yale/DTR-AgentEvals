"""Inert contract tests against the exact pinned mini-swe action parser."""

from __future__ import annotations

import importlib
import importlib.util
import hashlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src"
SUPERVISOR = Path(__file__).with_name("bounded_supervisor.py").resolve()


def load_pinned_parser_without_global_startup() -> None:
    """Load upstream parser modules while avoiding unrelated CLI/global config startup."""
    packages = {
        "minisweagent": UPSTREAM / "minisweagent",
        "minisweagent.models": UPSTREAM / "minisweagent/models",
        "minisweagent.models.utils": UPSTREAM / "minisweagent/models/utils",
    }
    parser_path = UPSTREAM / "minisweagent/models/utils/actions_text.py"
    parser_sha = hashlib.sha256(parser_path.read_bytes()).hexdigest()
    assert parser_sha == "e5997bba3ae3d541ff418317cc8dd9e9e17657de806679ef38ab1ad74e294047"
    default_agent_path = UPSTREAM / "minisweagent/agents/default.py"
    assert hashlib.sha256(default_agent_path.read_bytes()).hexdigest() == (
        "e8ef8aa365942d739c2ec5cb0879f60f377d2dc2de8ec670aaedf3bafb45a4c2"
    )
    for name, path in packages.items():
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    exceptions_name = "minisweagent.exceptions"
    spec = importlib.util.spec_from_file_location(exceptions_name, UPSTREAM / "minisweagent/exceptions.py")
    assert spec and spec.loader
    exceptions = importlib.util.module_from_spec(spec)
    sys.modules[exceptions_name] = exceptions
    spec.loader.exec_module(exceptions)
    importlib.import_module("minisweagent.models.utils.actions_text")

    # Stub only package startup/type dependencies unavailable in this lean
    # checkout; execute the pinned DefaultAgent source itself below.
    root_package = sys.modules["minisweagent"]
    root_package.__version__ = "2.4.6"
    root_package.Model = object
    root_package.Environment = object
    for name, path in {
        "minisweagent.agents": UPSTREAM / "minisweagent/agents",
        "minisweagent.utils": UPSTREAM / "minisweagent/utils",
    }.items():
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    pydantic_stub = types.ModuleType("pydantic")

    class MinimalBaseModel:
        def __init__(self, **kwargs):
            fields = {}
            for parent in reversed(type(self).mro()):
                for field in getattr(parent, "__annotations__", {}):
                    if hasattr(parent, field):
                        fields[field] = getattr(parent, field)
            fields.update(kwargs)
            self.__dict__.update(fields)

        def model_dump(self, **_kwargs):
            return dict(self.__dict__)

    pydantic_stub.BaseModel = MinimalBaseModel
    sys.modules["pydantic"] = pydantic_stub
    importlib.import_module("minisweagent.agents.default")


load_pinned_parser_without_global_startup()
from experiments.lead_req030.native_hf_text_adapter import NativeHFTextAdapter  # noqa: E402
from experiments.lead_req030.seaborn_apptainer_runner import run_pinned_agent, sha256_file  # noqa: E402
from experiments.lead_req030.seaborn_public_input import (  # noqa: E402
    FORMAT_ERROR_TEMPLATE_SHA256,
    OBSERVATION_TEMPLATE_SHA256,
    SEABORN_ACTION_REGEX,
    SEABORN_ACTION_REGEX_SHA256,
    build_seaborn_initial_messages,
    prepare_seaborn_default_agent,
)
from minisweagent.exceptions import FormatError  # noqa: E402
from minisweagent.exceptions import Submitted  # noqa: E402
from minisweagent.agents.default import DefaultAgent  # noqa: E402


class FakeTensor:
    def __init__(self, rows: list[list[int]]):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]))

    def to(self, _device: str) -> "FakeTensor":
        return self

    def __getitem__(self, key):
        if isinstance(key, int):
            return FakeSlice(self.rows[key])
        row, col = key
        return FakeSlice(self.rows[row][col])


class FakeSlice:
    def __init__(self, values: list[int]):
        self.values = values

    def tolist(self) -> list[int]:
        return self.values


class FakeTokenizer:
    eos_token_id = 2

    def __init__(self, response: str, input_ids: list[int] | None = None):
        self.response = response
        self.input_ids = input_ids or [11, 12, 13]
        self.seen_messages = None

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, **kwargs):
        self.seen_messages = messages
        self.assert_generation = add_generation_prompt
        if tokenize:
            raise AssertionError("adapter must use the independently replayed render-then-tokenize path")
        return "|".join(f"{m['role']}:{m['content']}" for m in messages) + "|assistant:"

    def __call__(self, rendered, *, add_special_tokens, return_tensors):
        assert add_special_tokens is False
        assert return_tensors == "pt"
        assert rendered.endswith("|assistant:")
        return {"input_ids": FakeTensor([self.input_ids])}

    def decode(self, ids, *, skip_special_tokens):
        assert skip_special_tokens is False
        return self.response


class FakeModel:
    def __init__(self, output_ids: list[int] | None = None):
        self.output_ids = output_ids or [42, 2]
        self.calls = 0
        self.kwargs = None

    def generate(self, *, input_ids, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return FakeTensor([input_ids.rows[0] + self.output_ids])


def make_adapter(
    response: str,
    *,
    context_limit: int = 64,
    input_ids: list[int] | None = None,
    format_error_template: str = "Expected exactly one action; found {{actions|length}}.",
    observation_template: str = "<returncode>{{ output.returncode }}</returncode>\n{{ output.output }}",
    action_regex: str = r"```mswea_bash_command\s*\n(.*?)\n```",
):
    tokenizer = FakeTokenizer(response, input_ids)
    model = FakeModel()
    events = []
    adapter = NativeHFTextAdapter(
        tokenizer=tokenizer,
        model=model,
        model_id="fixture/model",
        revision="fixture-revision",
        context_limit=context_limit,
        max_new_tokens=8,
        action_regex=action_regex,
        format_error_template=format_error_template,
        observation_template=observation_template,
        record_event=events.append,
    )
    return adapter, tokenizer, model, events


class NativeHFTextAdapterTests(unittest.TestCase):
    def test_native_template_binding_one_action_and_fixed_decoding(self):
        raw = "THOUGHT: inspect\n\n```mswea_bash_command\nls\n```"
        adapter, tokenizer, model, events = make_adapter(raw)
        result = adapter.query([
            {"role": "system", "content": "frozen system"},
            {"role": "user", "content": "public task"},
            {"role": "assistant", "content": "prior response", "extra": {"private": "must drop"}},
        ])
        self.assertEqual(result["extra"]["actions"], [{"command": "ls"}])
        self.assertEqual(tokenizer.seen_messages[-1], {"role": "assistant", "content": "prior response"})
        self.assertNotIn("private", repr(tokenizer.seen_messages))
        binding = result["extra"]["native_binding"]
        self.assertEqual(binding["input_ids"], [11, 12, 13])
        self.assertEqual(binding["output_ids"], [42, 2])
        self.assertEqual(binding["input_tokens"], 3)
        self.assertEqual(binding["physical_calls"], 1)
        self.assertEqual(model.calls, 1)
        self.assertEqual(model.kwargs["do_sample"], False)
        self.assertEqual(model.kwargs["max_new_tokens"], 8)
        self.assertEqual(model.kwargs["pad_token_id"], tokenizer.eos_token_id)
        self.assertEqual([event["event"] for event in events], ["request", "response"])
        self.assertEqual(events[0]["rendered_sha256"], binding["rendered_sha256"])

    def test_pinned_parser_rejects_zero_or_multiple_actions_and_binds_raw_output(self):
        for response in ("no action", "```mswea_bash_command\na\n```\n```mswea_bash_command\nb\n```"):
            adapter, _, model, events = make_adapter(response)
            with self.assertRaises(FormatError) as caught:
                adapter.query([{"role": "system", "content": "frozen"}, {"role": "user", "content": "task"}])
            self.assertEqual(model.calls, 1)
            self.assertEqual(caught.exception.messages[0]["extra"]["raw_model_output"], response)
            self.assertEqual(caught.exception.messages[0]["extra"]["native_binding"]["physical_calls"], 1)
            self.assertEqual([event["event"] for event in events], ["request", "response"])

    def test_context_overflow_and_unsupported_roles_or_types_fail_before_generation(self):
        adapter, _, model, events = make_adapter("```mswea_bash_command\ntrue\n```", context_limit=10)
        with self.assertRaisesRegex(ValueError, "context budget exceeded"):
            adapter.query([{"role": "system", "content": "frozen"}, {"role": "user", "content": "task"}])
        self.assertEqual(model.calls, 0)
        self.assertEqual(events, [])
        for bad in (
            [{"role": "system", "content": "frozen"}, {"role": "tool", "content": "hidden"}],
            [{"role": "system", "content": "frozen"}, {"role": "user", "content": [{"text": "not text"}]}],
            [{"role": "user", "content": "no system"}],
        ):
            with self.assertRaises(ValueError):
                adapter.query(bad)
        self.assertEqual(model.calls, 0)

    def test_observation_uses_pinned_formatter_shape(self):
        adapter, _, _, _ = make_adapter("```mswea_bash_command\nls\n```")
        observed = adapter.format_observation_messages({}, [{"returncode": 0, "output": "file.py"}])
        self.assertEqual(observed[0]["role"], "user")
        self.assertIn("<returncode>0</returncode>", observed[0]["content"])
        self.assertIn("file.py", observed[0]["content"])

    def test_serialization_is_source_bound(self):
        serialized = make_adapter("```mswea_bash_command\nls\n```")[0].serialize()
        self.assertEqual(serialized["info"]["config"]["model"]["revision"], "fixture-revision")

    def test_generation_error_is_recorded_and_failed_request_persistence_blocks_call(self):
        adapter, _, model, events = make_adapter("unused")

        def fail_generation(**_kwargs):
            raise RuntimeError("fixture OOM")

        model.generate = fail_generation
        with self.assertRaisesRegex(RuntimeError, "fixture OOM"):
            adapter.query([{"role": "system", "content": "frozen"}, {"role": "user", "content": "task"}])
        self.assertEqual([event["event"] for event in events], ["request", "generation_error"])
        self.assertEqual(events[-1]["physical_calls"], 1)

        blocked_model = FakeModel()

        def reject_record(_event):
            raise OSError("fixture receipt failure")

        blocked = NativeHFTextAdapter(
            tokenizer=FakeTokenizer("```mswea_bash_command\nls\n```"),
            model=blocked_model,
            model_id="fixture/model",
            revision="fixture-revision",
            context_limit=64,
            max_new_tokens=8,
            action_regex=r"```mswea_bash_command\s*\n(.*?)\n```",
            format_error_template="Expected one action",
            observation_template="{{ output.output }}",
            record_event=reject_record,
        )
        with self.assertRaisesRegex(OSError, "receipt failure"):
            blocked.query([{"role": "system", "content": "frozen"}, {"role": "user", "content": "task"}])
        self.assertEqual(blocked_model.calls, 0)

    def test_pinned_default_agent_loop_runs_one_tool_action_to_submission(self):
        raw = "THOUGHT: finish\n\n```mswea_bash_command\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```"
        public_bytes = (ROOT / "docs/source_snapshots/req030p_seaborn_public/public_task.json").read_bytes()

        class FakeEnvironment:
            def __init__(self):
                self.commands = []

            def get_template_vars(self):
                return {"system": "Linux", "release": "fixture", "version": "1", "machine": "fixture"}

            def execute(self, action, cwd=""):
                self.commands.append(action["command"])
                if action["command"] == "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT":
                    raise Submitted({
                        "role": "exit",
                        "content": "patch diff",
                        "extra": {"exit_status": "Submitted", "submission": "patch diff"},
                    })
                return {"output": "unexpected command", "returncode": 1}

            def serialize(self):
                return {"info": {"config": {"environment_type": "inert fixture"}}}

        env = FakeEnvironment()
        prepared = prepare_seaborn_default_agent(
            public_bytes,
            environment=env.get_template_vars(),
            step_limit=1,
            wall_time_limit_seconds=30,
            max_consecutive_format_errors=3,
            cost_limit=0.0,
        )
        self.assertEqual(
            hashlib.sha256(prepared.model_config["observation_template"].encode()).hexdigest(),
            OBSERVATION_TEMPLATE_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(prepared.model_config["format_error_template"].encode()).hexdigest(),
            FORMAT_ERROR_TEMPLATE_SHA256,
        )
        self.assertEqual(prepared.model_config["action_regex"], SEABORN_ACTION_REGEX)
        self.assertEqual(hashlib.sha256(SEABORN_ACTION_REGEX.encode()).hexdigest(), SEABORN_ACTION_REGEX_SHA256)
        adapter, tokenizer, model, events = make_adapter(
            raw,
            observation_template=prepared.model_config["observation_template"],
            format_error_template=prepared.model_config["format_error_template"],
            action_regex=prepared.model_config["action_regex"],
        )
        agent = DefaultAgent(adapter, env, **prepared.agent_config)
        result = agent.run(task=prepared.task.problem_statement)
        self.assertEqual(result["exit_status"], "Submitted")
        self.assertEqual(result["submission"], "patch diff")
        self.assertEqual(env.commands, ["echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"])
        self.assertEqual(model.calls, 1)
        self.assertEqual([event["event"] for event in events], ["request", "response"])
        self.assertEqual(agent.n_calls, 1)
        self.assertEqual(
            tokenizer.seen_messages,
            build_seaborn_initial_messages(public_bytes, environment=env.get_template_vars()),
        )
        self.assertEqual(prepared.template_source_sha256, "112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f")
        self.assertEqual(agent.config.step_limit, 1)
        self.assertEqual(agent.config.wall_time_limit_seconds, 30)
        observation = adapter.format_observation_messages(
            {},
            [{"output": "fixture output", "returncode": 0, "exception_info": None, "extra": {}}],
        )
        self.assertEqual(observation[0]["content"], "<returncode>0</returncode>\n<output>\nfixture output</output>")
        malformed_adapter, _, _, _ = make_adapter(
            "no action",
            action_regex=prepared.model_config["action_regex"],
            observation_template=prepared.model_config["observation_template"],
            format_error_template=prepared.model_config["format_error_template"],
        )
        with self.assertRaises(FormatError) as caught:
            malformed_adapter.query(tokenizer.seen_messages)
        self.assertIn("Expected exactly 1 action", caught.exception.messages[0]["content"])


class SeabornEndToEndRunnerTests(unittest.TestCase):
    """The fake Apptainer records argv and emits canned bytes; it runs no command."""

    def test_pinned_agent_receipts_preflight_and_terminal_submission(self):
        import json
        import os
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image, workspace, capture = root / "task.sif", root / "workspace.img", root / "argv.jsonl"
            image.write_bytes(b"pinned fake image")
            workspace.write_bytes(b"pinned fake workspace")
            fake_apptainer = root / "apptainer"
            fake_apptainer.write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,sys\n"
                "args=sys.argv[1:]\n"
                "with open(os.environ['FAKE_APPTAINER_ARGV'],'a') as f: f.write(json.dumps(args)+'\\n')\n"
                "if args == ['--version']:\n"
                " print('Apptainer fixture 1.0')\n"
                " raise SystemExit(0)\n"
                "command=args[-1]\n"
                "if 'DTR_PREFLIGHT' in command:\n"
                " print('DTR_PREFLIGHT\\t38ac1837e18294d23d95a8e89f26f003c66d4fd5\\t22cdfb0c93f8ec78492d87edb810f10cb7f57a31\\t8b530ce017437324b9e3a39af220965bf0e71558\\t8b530ce017437324b9e3a39af220965bf0e71558\\t100000000\\t128000000')\n"
                "else:\n"
                " print('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\\ninert-fixture-submission')\n"
            )
            fake_apptainer.chmod(0o700)
            response = "THOUGHT: submit inert fixture\n\n```mswea_bash_command\necho FIXED_INERT_ACTION\n```"

            def model_factory(record_event, config):
                return NativeHFTextAdapter(
                    tokenizer=FakeTokenizer(response), model=FakeModel(),
                    model_id="fixture/Qwen", revision="fixture-revision",
                    context_limit=64, max_new_tokens=8, record_event=record_event, **config,
                )

            args = dict(
                agent_class=DefaultAgent, model_factory=model_factory,
                public_projection=(ROOT / "docs/source_snapshots/req030p_seaborn_public/public_task.json").read_bytes(),
                run_directory=root / "run-a", apptainer=str(fake_apptainer),
                image=image, image_sha256=sha256_file(image),
                workspace_image=workspace, workspace_sha256=sha256_file(workspace),
                supervisor=SUPERVISOR, supervisor_sha256=sha256_file(SUPERVISOR),
                release_id="req030-inert-runner-test-a", release_sha256="a" * 64,
                step_limit=2, wall_time_limit_seconds=30, model_context_limit=64,
                model_max_new_tokens=8, tool_timeout_seconds=5,
                output_cap_bytes=4096, action_cap_bytes=8192,
            )
            with patch.dict(os.environ, {"FAKE_APPTAINER_ARGV": str(capture)}):
                import experiments.lead_req030.seaborn_apptainer_runner as runner_module
                real_readlink = os.readlink
                def fixture_readlink(path, *readlink_args, **readlink_kwargs):
                    if os.fspath(path) == "/proc/self/ns/net":
                        return "net:[inert-host-fixture]"
                    return real_readlink(path, *readlink_args, **readlink_kwargs)
                with patch.object(runner_module.os, "readlink", side_effect=fixture_readlink):
                    outcome = run_pinned_agent(**args)
            self.assertEqual(outcome["result"]["exit_status"], "Submitted")
            self.assertEqual(outcome["result"]["submission"], "inert-fixture-submission\n")
            run_dir = Path(outcome["run_directory"])
            self.assertEqual(run_dir.stat().st_mode & 0o777, 0o700)
            self.assertEqual((run_dir / "events.jsonl").stat().st_mode & 0o777, 0o600)
            trajectory = json.loads((run_dir / "trajectory.json").read_text())
            self.assertEqual(trajectory["info"]["model_stats"]["api_calls"], 1)
            self.assertEqual(trajectory["messages"][-1]["extra"]["exit_status"], "Submitted")
            events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
            names = [event["event"] for event in events]
            self.assertLess(names.index("workspace_preflight_accepted"), names.index("agent_run_start"))
            self.assertLess(names.index("agent_run_start"), names.index("request"))
            self.assertLess(names.index("request"), names.index("action_start"))
            self.assertLess(names.index("action_finish"), names.index("terminal_submission"))
            self.assertEqual(events[-1]["event"], "agent_run_finish")
            self.assertEqual(events[-1]["physical_model_calls"], 1)
            self.assertEqual(events[-1]["trajectory_sha256"], outcome["trajectory_sha256"])
            invocations = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(invocations), 3)
            self.assertEqual(invocations[0], ["--version"])
            preflight_script = invocations[1][-1]
            self.assertIn("/proc/self/ns/net", preflight_script)
            self.assertIn("git status --porcelain --untracked-files=all", preflight_script)
            self.assertIn("DTR_ROOT_WRITE_TEST", preflight_script)
            self.assertIn('git rev-parse "${expected_base}^{tree}"', preflight_script)
            import subprocess
            syntax = subprocess.run(["bash", "-n"], input=preflight_script, text=True, capture_output=True)
            self.assertEqual(syntax.returncode, 0, syntax.stderr)
            action_argv = invocations[-1]
            for required in ("--containall", "--cleanenv", "--no-home", "--net", "none", "--pwd", "/testbed"):
                self.assertIn(required, action_argv)
            self.assertIn("hostfs,bind-paths", action_argv)
            self.assertTrue(any(value.endswith(":/testbed:image-src=/") for value in action_argv))
            self.assertEqual(action_argv[-3:], ["/bin/bash", "-lc", "echo FIXED_INERT_ACTION"])
            self.assertEqual(events[2]["apptainer_version"], "Apptainer fixture 1.0")
            self.assertNotIn("reference", repr(invocations).lower())

    def test_failed_preflight_prevents_model_factory(self):
        import json
        import os
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image, workspace = root / "task.sif", root / "workspace.img"
            image.write_bytes(b"pinned fake image")
            workspace.write_bytes(b"pinned fake workspace")
            fake_apptainer = root / "apptainer-fail"
            fake_apptainer.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "print('Apptainer fixture 1.0' if sys.argv[1:] == ['--version'] else 'preflight rejected')\n"
                "raise SystemExit(0 if sys.argv[1:] == ['--version'] else 1)\n"
            )
            fake_apptainer.chmod(0o700)
            called = []

            def model_factory(*_args):
                called.append(True)
                raise AssertionError("model factory must not run before preflight acceptance")

            args = dict(
                agent_class=DefaultAgent, model_factory=model_factory,
                public_projection=(ROOT / "docs/source_snapshots/req030p_seaborn_public/public_task.json").read_bytes(),
                run_directory=root / "run-fail", apptainer=str(fake_apptainer),
                image=image, image_sha256=sha256_file(image),
                workspace_image=workspace, workspace_sha256=sha256_file(workspace),
                supervisor=SUPERVISOR, supervisor_sha256=sha256_file(SUPERVISOR),
                release_id="req030-inert-preflight-failure-a", release_sha256="b" * 64,
                step_limit=2, wall_time_limit_seconds=30, model_context_limit=64,
                model_max_new_tokens=8, tool_timeout_seconds=5,
                output_cap_bytes=4096, action_cap_bytes=8192,
            )
            import experiments.lead_req030.seaborn_apptainer_runner as runner_module
            real_readlink = os.readlink
            def fixture_readlink(path, *readlink_args, **readlink_kwargs):
                if os.fspath(path) == "/proc/self/ns/net":
                    return "net:[inert-host-fixture]"
                return real_readlink(path, *readlink_args, **readlink_kwargs)
            with patch.object(runner_module.os, "readlink", side_effect=fixture_readlink):
                with self.assertRaisesRegex(RuntimeError, "workspace preflight failed"):
                    run_pinned_agent(**args)
            self.assertEqual(called, [])
            events = [json.loads(line) for line in (root / "run-fail" / "events.jsonl").read_text().splitlines()]
            self.assertNotIn("agent_run_start", [event["event"] for event in events])

    def test_no_tool_command_before_workspace_preflight(self):
        import os
        import tempfile
        from unittest.mock import patch
        from experiments.lead_req030.seaborn_apptainer_runner import ApptainerToolEnvironment, DurableEventLog

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image, workspace = root / "task.sif", root / "workspace.img"
            image.write_bytes(b"image")
            workspace.write_bytes(b"workspace")
            run_dir = root / "run"
            run_dir.mkdir(mode=0o700)
            journal = DurableEventLog(run_dir)
            try:
                import experiments.lead_req030.seaborn_apptainer_runner as runner_module
                real_readlink = os.readlink
                def fixture_readlink(path, *readlink_args, **readlink_kwargs):
                    if os.fspath(path) == "/proc/self/ns/net":
                        return "net:[inert-host-fixture]"
                    return real_readlink(path, *readlink_args, **readlink_kwargs)
                with patch.object(runner_module.os, "readlink", side_effect=fixture_readlink):
                    env = ApptainerToolEnvironment(
                        apptainer=os.sys.executable, image=image, image_sha256=sha256_file(image),
                        workspace_image=workspace, workspace_sha256=sha256_file(workspace),
                        supervisor=SUPERVISOR, supervisor_sha256=sha256_file(SUPERVISOR), run_dir=run_dir,
                        event_log=journal, tool_timeout_seconds=5, output_cap_bytes=1024, action_cap_bytes=1024,
                        expected_base_commit="22cdfb0c93f8ec78492d87edb810f10cb7f57a31",
                    )
                    with self.assertRaisesRegex(RuntimeError, "before isolated workspace preflight"):
                        env.execute({"command": "echo inert"})
            finally:
                journal.close()

    def test_runner_supervisor_receipts_timeout_and_output_cap(self):
        import os
        import tempfile
        from unittest.mock import patch
        from experiments.lead_req030.seaborn_apptainer_runner import ApptainerToolEnvironment, DurableEventLog

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image, workspace = root / "task.sif", root / "workspace.img"
            image.write_bytes(b"pinned fake image")
            workspace.write_bytes(b"pinned fake workspace")
            fake_apptainer = root / "apptainer-faults"
            fake_apptainer.write_text(
                "#!/usr/bin/env python3\n"
                "import os,sys,time\n"
                "args=sys.argv[1:]\n"
                "if args == ['--version']:\n print('Apptainer fixture 1.0'); raise SystemExit(0)\n"
                "command=args[-1]\n"
                "if 'DTR_PREFLIGHT' in command:\n"
                " print('DTR_PREFLIGHT\\t38ac1837e18294d23d95a8e89f26f003c66d4fd5\\t22cdfb0c93f8ec78492d87edb810f10cb7f57a31\\t8b530ce017437324b9e3a39af220965bf0e71558\\t8b530ce017437324b9e3a39af220965bf0e71558\\t100000000\\t128000000')\n"
                "elif command == 'TIMEOUT_FIXTURE':\n time.sleep(10)\n"
                "elif command == 'OVERFLOW_FIXTURE':\n os.write(1,b'x'*8192); time.sleep(10)\n"
            )
            fake_apptainer.chmod(0o700)
            run_dir = root / "run-faults"
            run_dir.mkdir(mode=0o700)
            journal = DurableEventLog(run_dir)
            import experiments.lead_req030.seaborn_apptainer_runner as runner_module
            real_readlink = os.readlink
            def fixture_readlink(path, *readlink_args, **readlink_kwargs):
                if os.fspath(path) == "/proc/self/ns/net":
                    return "net:[inert-host-fixture]"
                return real_readlink(path, *readlink_args, **readlink_kwargs)
            with patch.object(runner_module.os, "readlink", side_effect=fixture_readlink):
                env = ApptainerToolEnvironment(
                    apptainer=str(fake_apptainer), image=image, image_sha256=sha256_file(image),
                    workspace_image=workspace, workspace_sha256=sha256_file(workspace),
                    supervisor=SUPERVISOR, supervisor_sha256=sha256_file(SUPERVISOR), run_dir=run_dir,
                    event_log=journal, tool_timeout_seconds=2, output_cap_bytes=1024, action_cap_bytes=1024,
                    expected_base_commit="22cdfb0c93f8ec78492d87edb810f10cb7f57a31",
                )
                try:
                    env.preflight()
                    timed = env.execute({"command": "TIMEOUT_FIXTURE"})
                    self.assertEqual(timed["exception_info"], "deadline")
                    self.assertEqual(timed["extra"]["supervisor"]["reason"], "deadline")
                    overflow = env.execute({"command": "OVERFLOW_FIXTURE"})
                    self.assertEqual(overflow["exception_info"], "output_limit")
                    self.assertEqual(overflow["extra"]["supervisor"]["retained_bytes"], 1024)
                    self.assertEqual((run_dir / "action-0002.out").stat().st_size, 1024)
                    env.seal_workspace()
                finally:
                    env.close()
                    journal.close()


if __name__ == "__main__":
    unittest.main()
