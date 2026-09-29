"""Load only the frozen public Seaborn issue projection for an agent run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


PUBLIC_PROJECTION_SHA256 = "b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9"
PUBLIC_PROJECTION_SCHEMA = {"instance_id", "base_commit", "problem_statement"}
INSTANCE_ID = "mwaskom__seaborn-3187"
BASE_COMMIT = "22cdfb0c93f8ec78492d87edb810f10cb7f57a31"


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
