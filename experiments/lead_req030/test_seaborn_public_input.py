"""Source-only tests for the public-only Seaborn task boundary."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from experiments.lead_req030.seaborn_public_input import (
    BASE_COMMIT,
    INSTANCE_ID,
    PUBLIC_PROJECTION_SHA256,
    MINISWE_CONFIG,
    MINISWE_CONFIG_SHA256,
    SYSTEM_TEMPLATE_SHA256,
    INSTANCE_TEMPLATE_SHA256,
    build_seaborn_initial_messages,
    load_pinned_agent_templates,
    load_public_projection,
    parse_public_projection,
    prepare_seaborn_default_agent,
)


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_FILE = ROOT / "docs/source_snapshots/req030p_seaborn_public/public_task.json"


class PublicTaskBoundaryTests(unittest.TestCase):
    def test_pinned_public_projection_parses_without_evaluator_fields(self):
        task = load_public_projection(PUBLIC_FILE)
        self.assertEqual(task.source_sha256, PUBLIC_PROJECTION_SHA256)
        self.assertEqual(task.instance_id, INSTANCE_ID)
        self.assertEqual(task.base_commit, BASE_COMMIT)
        self.assertTrue(task.problem_statement.strip())
        self.assertEqual(set(json.loads(PUBLIC_FILE.read_text())), {"instance_id", "base_commit", "problem_statement"})

    def test_reference_or_status_fields_cannot_be_added(self):
        payload = json.loads(PUBLIC_FILE.read_text())
        payload["reference_patch"] = "must stay evaluator-only"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            parse_public_projection(json.dumps(payload, separators=(",", ":")).encode())

    def test_other_task_or_mutated_public_text_is_rejected(self):
        raw = PUBLIC_FILE.read_bytes()
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            parse_public_projection(raw.replace(b"mwaskom__seaborn-3187", b"other__task-1"))
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            parse_public_projection(raw + b" ")

    def test_source_pinned_upstream_templates_are_used_for_initial_messages(self):
        raw = PUBLIC_FILE.read_bytes()
        task = load_public_projection(PUBLIC_FILE)
        env = {"system": "Linux", "release": "6.8", "version": "#1", "machine": "x86_64"}
        messages = build_seaborn_initial_messages(raw, environment=env)
        templates = load_pinned_agent_templates()
        self.assertEqual(templates.source_sha256, MINISWE_CONFIG_SHA256)
        self.assertEqual(hashlib.sha256(MINISWE_CONFIG.read_bytes()).hexdigest(), MINISWE_CONFIG_SHA256)
        self.assertEqual(hashlib.sha256(templates.system_template.encode()).hexdigest(), SYSTEM_TEMPLATE_SHA256)
        self.assertEqual(hashlib.sha256(templates.instance_template.encode()).hexdigest(), INSTANCE_TEMPLATE_SHA256)
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertIn("You are a helpful assistant", messages[0]["content"])
        self.assertIn(task.problem_statement, messages[1]["content"])
        self.assertIn("mwaskom__seaborn-3187", task.instance_id)
        self.assertEqual(
            [hashlib.sha256(m["content"].encode()).hexdigest() for m in messages],
            [
                "6ff414b4a6e65033ce9f016b606c86a07eed98fccb2bfba4b84fda1b86a96ca6",
                "658d84032978f03716677f56ffcdb33b80dcc0add9361dc34e05cb08f98077c6",
            ],
        )
        self.assertNotIn("reference", "\n".join(m["content"] for m in messages).lower())

    def test_prompt_builder_fails_closed_on_config_or_environment_drift(self):
        config = MINISWE_CONFIG.read_bytes()
        with self.assertRaisesRegex(ValueError, "config hash mismatch"):
            load_pinned_agent_templates(config + b"# changed\n")
        with self.assertRaisesRegex(ValueError, "exactly system/release/version/machine"):
            build_seaborn_initial_messages(
                PUBLIC_FILE.read_bytes(),
                environment={"system": "Linux", "release": "6.8", "version": "#1", "machine": "x86_64", "reference_patch": "secret"},
            )
        with self.assertRaisesRegex(ValueError, "positive integers"):
            prepare_seaborn_default_agent(
                PUBLIC_FILE.read_bytes(),
                environment={"system": "Linux", "release": "6.8", "version": "#1", "machine": "x86_64"},
                step_limit=0,
                wall_time_limit_seconds=30,
            )
        with self.assertRaisesRegex(ValueError, "positive integers"):
            prepare_seaborn_default_agent(
                PUBLIC_FILE.read_bytes(),
                environment={"system": "Linux", "release": "6.8", "version": "#1", "machine": "x86_64"},
                step_limit=1.5,
                wall_time_limit_seconds=30,
            )


if __name__ == "__main__":
    unittest.main()
