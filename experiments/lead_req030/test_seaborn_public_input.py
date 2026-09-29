"""Source-only tests for the public-only Seaborn task boundary."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.lead_req030.seaborn_public_input import (
    BASE_COMMIT,
    INSTANCE_ID,
    PUBLIC_PROJECTION_SHA256,
    load_public_projection,
    parse_public_projection,
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


if __name__ == "__main__":
    unittest.main()
