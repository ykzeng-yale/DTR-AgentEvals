"""Prepare a source-pinned initial mini-swe prompt from public Seaborn input."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PUBLIC_PROJECTION_SHA256 = "b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9"
PUBLIC_PROJECTION_SCHEMA = {"instance_id", "base_commit", "problem_statement"}
INSTANCE_ID = "mwaskom__seaborn-3187"
BASE_COMMIT = "22cdfb0c93f8ec78492d87edb810f10cb7f57a31"
MINISWE_CONFIG_SHA256 = "112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f"
SYSTEM_TEMPLATE_SHA256 = "5c9bba45e018c7fbf379c8c1a91cce06deecc26670764ce86810e37523c59d2d"
INSTANCE_TEMPLATE_SHA256 = "cdf5e8dc1972686b90e3e84a0a4b200874ad5aaf1e3d26c26ed1872c1ba2e9b0"
MINISWE_CONFIG = Path(__file__).resolve().parents[2] / "docs/source_snapshots/req030t_miniswe_agent/default.yaml"


@dataclass(frozen=True)
class PinnedAgentTemplates:
    system_template: str
    instance_template: str
    source_sha256: str


@dataclass(frozen=True)
class PreparedSeabornAgentRun:
    task: PublicTaskInput
    agent_config: Mapping[str, object]
    template_source_sha256: str


def _extract_literal_agent_scalar(lines: list[str], key: str) -> str:
    """Extract one YAML literal scalar from the frozen upstream config.

    This intentionally handles only the two known ``agent`` block scalars;
    the complete file hash is checked before this narrow extraction.
    """
    marker = f"  {key}: |"
    matches = [i for i, line in enumerate(lines) if line == marker]
    if len(matches) != 1:
        raise ValueError(f"pinned config must contain exactly one {key} literal")
    start = matches[0] + 1
    block: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith("    "):
            break
        block.append(line[4:] if line.startswith("    ") else "")
    # YAML's default literal-block chomping preserves one final newline and
    # strips trailing blank lines. The upstream source has no trailing blanks.
    while block and block[-1] == "":
        block.pop()
    if not block:
        raise ValueError(f"pinned config has an empty {key} literal")
    return "\n".join(block) + "\n"


def load_pinned_agent_templates(config_bytes: bytes | None = None) -> PinnedAgentTemplates:
    """Load exact system/instance templates from the source-pinned mini-swe YAML."""
    data = MINISWE_CONFIG.read_bytes() if config_bytes is None else config_bytes
    digest = hashlib.sha256(data).hexdigest()
    if digest != MINISWE_CONFIG_SHA256:
        raise ValueError("mini-swe default agent config hash mismatch")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("mini-swe default agent config is not UTF-8") from exc
    lines = text.splitlines()
    # Fail closed if the expected agent section is moved or duplicated.
    if lines.count("agent:") != 1:
        raise ValueError("pinned config agent section mismatch")
    system_template = _extract_literal_agent_scalar(lines, "system_template")
    instance_template = _extract_literal_agent_scalar(lines, "instance_template")
    if hashlib.sha256(system_template.encode("utf-8")).hexdigest() != SYSTEM_TEMPLATE_SHA256:
        raise ValueError("mini-swe system template hash mismatch")
    if hashlib.sha256(instance_template.encode("utf-8")).hexdigest() != INSTANCE_TEMPLATE_SHA256:
        raise ValueError("mini-swe instance template hash mismatch")
    return PinnedAgentTemplates(system_template, instance_template, digest)


def build_seaborn_initial_messages(
    public_projection: bytes,
    *,
    environment: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build the pinned DefaultAgent initial messages from public bytes only.

    ``environment`` is restricted to four non-task metadata keys. Their
    provenance must be bound by the production environment receipt; this
    helper does not attest where the caller obtained them. No evaluator or
    model fields are accepted here.
    This mirrors mini-swe-agent's StrictUndefined Jinja rendering for its
    initial system and instance messages.
    """
    from jinja2 import StrictUndefined, Template

    task = parse_public_projection(public_projection)
    expected = {"system", "release", "version", "machine"}
    if (
        not isinstance(environment, Mapping)
        or set(environment) != expected
        or any(not isinstance(v, str) for v in environment.values())
    ):
        raise ValueError("environment template variables must be exactly system/release/version/machine")
    pinned = load_pinned_agent_templates()
    template_vars = {**environment, "task": task.problem_statement}
    return [
        {
            "role": "system",
            "content": Template(pinned.system_template, undefined=StrictUndefined).render(**template_vars),
        },
        {
            "role": "user",
            "content": Template(pinned.instance_template, undefined=StrictUndefined).render(**template_vars),
        },
    ]


def prepare_seaborn_default_agent(
    public_projection: bytes,
    *,
    environment: Mapping[str, str],
    step_limit: int,
    wall_time_limit_seconds: int,
    cost_limit: float = 0.0,
    max_consecutive_format_errors: int = 3,
) -> PreparedSeabornAgentRun:
    """Prepare only the pinned public task and bounded upstream agent config.

    The returned values can be passed to the pinned ``DefaultAgent`` as
    ``agent_class(model, env, **agent_config).run(task=task.problem_statement)``.
    This prepares no model, environment, evaluator input, or task execution.
    """
    limits = (step_limit, wall_time_limit_seconds, max_consecutive_format_errors)
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in limits):
        raise ValueError("agent step, wall-time, and format-error limits must be positive integers")
    if (
        not isinstance(cost_limit, (int, float))
        or isinstance(cost_limit, bool)
        or not math.isfinite(cost_limit)
        or cost_limit < 0
    ):
        raise ValueError("agent cost limit must be finite and nonnegative")
    # Validate the same restricted environment bindings used by the prompt
    # renderer before returning an agent config.
    expected = {"system", "release", "version", "machine"}
    if (
        not isinstance(environment, Mapping)
        or set(environment) != expected
        or any(not isinstance(v, str) for v in environment.values())
    ):
        raise ValueError("environment template variables must be exactly system/release/version/machine")
    task = parse_public_projection(public_projection)
    templates = load_pinned_agent_templates()
    return PreparedSeabornAgentRun(
        task=task,
        agent_config={
            "system_template": templates.system_template,
            "instance_template": templates.instance_template,
            "step_limit": step_limit,
            "wall_time_limit_seconds": wall_time_limit_seconds,
            "cost_limit": cost_limit,
            "max_consecutive_format_errors": max_consecutive_format_errors,
        },
        template_source_sha256=templates.source_sha256,
    )


@dataclass(frozen=True)
class PublicTaskInput:
    instance_id: str
    base_commit: str
    problem_statement: str
    source_sha256: str


def parse_public_projection(data: bytes) -> PublicTaskInput:
    """Reject any bytes other than the frozen public-only task projection."""
    digest = hashlib.sha256(data).hexdigest()
    if digest != PUBLIC_PROJECTION_SHA256:
        raise ValueError("public task projection hash mismatch")
    payload = json.loads(data)
    if not isinstance(payload, dict) or set(payload) != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError("public task projection schema mismatch")
    if payload["instance_id"] != INSTANCE_ID or payload["base_commit"] != BASE_COMMIT:
        raise ValueError("public task identity mismatch")
    statement = payload["problem_statement"]
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError("public task statement is empty or invalid")
    return PublicTaskInput(INSTANCE_ID, BASE_COMMIT, statement, digest)


def load_public_projection(path: str | Path) -> PublicTaskInput:
    """Read the one pinned public input; never accepts an evaluator bundle path."""
    return parse_public_projection(Path(path).read_bytes())
