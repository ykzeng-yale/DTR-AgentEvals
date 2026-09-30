"""Unreleased two-decision fixed-schedule integration, with no model loading.

SS/SL/LS/LL select the model for logical queries 1–8 and 9–24. These are
deterministic assigned regimes, not randomized loggers or OPE observations.
The caller must bootstrap the pinned mini-swe package and inject both pinned
models and their single common tokenizer; no state/history is reset at query 9.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

CONTEXT_LIMIT = 16384
MAX_NEW_TOKENS = 1536
LOGICAL_CALL_LIMIT = 24
DECISION_CALLS = (1, 9)
MODEL_PINS = {
    "S": {"repo": "Qwen/Qwen2.5-Coder-7B-Instruct", "revision": "c03e6d358207e414f1eca0bb1891e29f1db0e242"},
    "L": {"repo": "Qwen/Qwen2.5-Coder-14B-Instruct", "revision": "aedcc2d42b622764e023cf882b6652e646b95671"},
}
NATIVE_ADAPTER_SHA256 = "28472dfd9bc40f101bdfc80d1911e183787daad4786d9002398443f0b12c6884"
ACTION_REGEX = r"```mswea_bash_command\s*\n(.*?)\n```"
FORMAT_ERROR_SHA256 = "04fce5694c2695cc0cc4672cd6d7678f398402a99b0b3379fb397f06c00baca8"
OBSERVATION_SHA256 = "4cd54626f03be2dd572eeffbe31d9421d73c167d4feb79dc3c1b4336d0568e31"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FixedScheduleHFAdapter:
    """mini-swe Model protocol; ``n_calls`` is total physical generation attempts."""

    def __init__(self, *, schedule: str, tokenizer: Any, models: Mapping[str, Any],
                 model_info: Mapping[str, Mapping[str, Any]], record_event: Callable[[dict], None],
                 action_regex: str, format_error_template: str, observation_template: str,
                 device: str = "cuda:0") -> None:
        if schedule not in {"SS", "SL", "LS", "LL"}:
            raise ValueError("only frozen schedules SS/SL/LS/LL are permitted")
        if set(models) != {"S", "L"} or set(model_info) != {"S", "L"}:
            raise ValueError("exactly the S and L model slots must be injected")
        if models["S"] is models["L"]:
            raise ValueError("two distinct pinned model instances are required")
        for action, pin in MODEL_PINS.items():
            if any(model_info[action].get(key) != value for key, value in pin.items()):
                raise ValueError("injected model identity differs from frozen pair")
        if (action_regex != ACTION_REGEX or sha(format_error_template.encode()) != FORMAT_ERROR_SHA256
                or sha(observation_template.encode()) != OBSERVATION_SHA256):
            raise ValueError("action/observation/error templates differ from frozen common contract")
        from experiments.lead_req030 import native_hf_text_adapter as native
        if sha(Path(native.__file__).read_bytes()) != NATIVE_ADAPTER_SHA256:
            raise ValueError("native HF adapter source pin mismatch")
        self.schedule = schedule
        self.tokenizer = tokenizer
        self.record_event = record_event
        self.logical_calls = 0
        self._pending: dict[str, Any] | None = None
        self._reservation: dict[str, Any] | None = None
        self._native = native
        self.adapters = {
            action: native.NativeHFTextAdapter(tokenizer=tokenizer, model=models[action],
                model_id=pin["repo"], revision=pin["revision"], context_limit=CONTEXT_LIMIT,
                max_new_tokens=MAX_NEW_TOKENS, action_regex=action_regex,
                format_error_template=format_error_template, observation_template=observation_template,
                record_event=lambda event, selected=action: self._native_event(selected, event), device=device)
            for action, pin in MODEL_PINS.items()
        }
        self.config = {"schedule": schedule, "model_id": "req030ai-fixed-schedule",
            "model_pins": {a: dict(p) for a, p in MODEL_PINS.items()},
            "context_limit": CONTEXT_LIMIT, "max_new_tokens": MAX_NEW_TOKENS,
            "decision_logical_calls": list(DECISION_CALLS), "logical_call_limit": LOGICAL_CALL_LIMIT,
            "elapsed_time_eligibility": "shared episode deadline enforced by the worker",
            "assignment": "deterministic fixed regime; not randomized/OPE logging",
            "action_regex": action_regex, "native_adapter_sha256": NATIVE_ADAPTER_SHA256}

    @property
    def n_calls(self) -> int:
        return sum(adapter.n_calls for adapter in self.adapters.values())

    @property
    def model_call_counts(self) -> dict[str, int]:
        return {action: adapter.n_calls for action, adapter in self.adapters.items()}

    def _selected_action(self) -> str:
        return self.schedule[0 if self.logical_calls <= 8 else 1]

    def _binding(self, messages: list[dict], action: str) -> dict[str, Any]:
        adapter = self.adapters[action]
        if adapter.tokenizer is not self.tokenizer or adapter.context_limit != CONTEXT_LIMIT or adapter.max_new_tokens != MAX_NEW_TOKENS:
            raise RuntimeError("common tokenizer/token budget was changed after construction")
        visible = adapter._visible_messages(messages)
        rendered = adapter.tokenizer.apply_chat_template(visible, tokenize=False, add_generation_prompt=True)
        encoded = adapter.tokenizer(rendered, add_special_tokens=False, return_tensors="pt")
        ids = self._native.single_sequence_token_ids(encoded)
        return {"messages_sha256": sha(json.dumps(visible, ensure_ascii=False, separators=(",", ":")).encode()),
            "rendered_sha256": sha(rendered.encode()), "input_ids": ids, "input_tokens": len(ids),
            "max_new_tokens": MAX_NEW_TOKENS, "context_limit": CONTEXT_LIMIT,
            "reserved_total_tokens": len(ids) + MAX_NEW_TOKENS,
            "remaining_input_token_capacity": CONTEXT_LIMIT - MAX_NEW_TOKENS - len(ids),
            "admitted": len(ids) + MAX_NEW_TOKENS <= CONTEXT_LIMIT}

    def _reserve_both(self, messages: list[dict]) -> None:
        # No model.generate(), tensor-to-GPU transfer or callback to an evaluator.
        bindings = {action: self._binding(messages, action) for action in ("S", "L")}
        if bindings["S"] != bindings["L"]:
            raise RuntimeError("both-action native token bindings differ")
        action = self._selected_action()
        event = {"event": "routing_decision", "schedule": self.schedule,
            "logical_call": self.logical_calls, "decision_index": DECISION_CALLS.index(self.logical_calls) + 1,
            "remaining_logical_calls_including_current": LOGICAL_CALL_LIMIT - self.logical_calls + 1,
            "elapsed_time_eligibility": "shared episode deadline enforced by the worker",
            "model_action": action, "model_id": MODEL_PINS[action]["repo"],
            "revision": MODEL_PINS[action]["revision"], "physical_calls_before": self.n_calls,
            "per_model_physical_calls_before": self.model_call_counts,
            "assignment": "deterministic_fixed_schedule", "probability": 1.0,
            "probability_vector": {"S": float(action == "S"), "L": float(action == "L")},
            "randomized_logger": False, "both_action_reservations": bindings}
        if not all(binding["admitted"] for binding in bindings.values()):
            event["event"] = "routing_reservation_denied"
            # No action was assigned when the joint eligibility check failed.
            for key in ("probability", "probability_vector", "model_action", "model_id", "revision"):
                event.pop(key)
            self.record_event(event)
            raise self._native.ContextBudgetExceeded(input_tokens=bindings["S"]["input_tokens"],
                max_new_tokens=MAX_NEW_TOKENS, context_limit=CONTEXT_LIMIT)
        # Durable decision acceptance is a prerequisite to the native request.
        self.record_event(event)
        self._reservation = bindings[action]

    def _native_event(self, action: str, event: dict[str, Any]) -> None:
        kind = event.get("event")
        if action != self._selected_action():
            raise RuntimeError("native request violates the frozen schedule")
        if kind == "request":
            if self._pending is not None:
                raise RuntimeError("prior native request has no terminal receipt")
            if self._reservation is not None and any(event.get(k) != self._reservation[k]
                    for k in ("messages_sha256", "rendered_sha256", "input_ids", "input_tokens")):
                raise RuntimeError("generation request differs from both-action reservation")
            local_number = self.adapters[action].n_calls + 1
            if event.get("physical_calls") != local_number:
                raise RuntimeError("native per-model physical count mismatch")
            pending = {"physical_calls": self.n_calls + 1, "per_model_physical_calls": local_number,
                       "model_action": action, "logical_call": self.logical_calls}
        elif kind in {"response", "generation_error"}:
            if self._pending is None or self._pending["model_action"] != action:
                raise RuntimeError("terminal native receipt lacks a matching request")
            pending = self._pending
            if self.n_calls != pending["physical_calls"] or self.adapters[action].n_calls != pending["per_model_physical_calls"]:
                raise RuntimeError("actual native generation count differs from receipt")
        else:
            raise RuntimeError("unexpected native event type")
        # Mutating the native binding also keeps returned/FormatError trajectory
        # bindings consistent with the durable event's global call numbering.
        event.update(pending)
        event.update({"schedule": self.schedule, "model_id": MODEL_PINS[action]["repo"],
                      "revision": MODEL_PINS[action]["revision"]})
        self.record_event(event)
        self._pending = pending if kind == "request" else None

    def query(self, messages: list[dict], **kwargs: Any) -> dict:
        if kwargs:
            raise ValueError("per-call overrides are forbidden")
        if self.logical_calls >= LOGICAL_CALL_LIMIT:
            from minisweagent.exceptions import LimitsExceeded
            raise LimitsExceeded({"role": "exit", "content": "logical call limit reached",
                "extra": {"exit_status": "LimitsExceeded", "submission": "", "limit_kind": "logical_calls"}})
        self.logical_calls += 1
        self._reservation = None
        if self.logical_calls in DECISION_CALLS:
            self._reserve_both(messages)
        # Native adapter preserves full role/content history and records parser
        # failures after generation. Unexpected generation errors remain errors.
        return self.adapters[self._selected_action()].query(messages)

    def format_message(self, **kwargs: Any) -> dict:
        return dict(kwargs)

    def format_observation_messages(self, message: dict, outputs: list[dict],
                                    template_vars: dict | None = None) -> list[dict]:
        return self.adapters["S"].format_observation_messages(message, outputs, template_vars)

    def get_template_vars(self, **kwargs: Any) -> dict:
        return {**self.config, **kwargs}

    def serialize(self) -> dict:
        return {"info": {"config": {"model": self.config, "model_type": type(self).__name__},
            "schedule_stats": {"logical_calls": self.logical_calls, "physical_calls": self.n_calls,
                               "per_model_physical_calls": self.model_call_counts}}}
