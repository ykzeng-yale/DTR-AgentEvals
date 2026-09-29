"""Native Hugging Face adapter for the pinned mini-swe-agent text-action API.

This module deliberately does not load a model or create an environment. The
caller must inject an already source-pinned tokenizer/model and the qualified
environment. It is suitable for inert interface tests; live use requires a
separate exact source approval and run release.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from typing import Any, Callable

from minisweagent.models.utils.actions_text import (
    format_observation_messages,
    parse_regex_actions,
)


def single_sequence_token_ids(encoded: Mapping[str, Any]) -> list[int]:
    """Normalize HF tokenizer list/tensor output to one complete token sequence."""
    if "input_ids" not in encoded:
        raise TypeError("tokenizer output has no input_ids")
    ids = encoded["input_ids"]
    if hasattr(ids, "tolist"):
        ids = ids.tolist()
    elif hasattr(ids, "shape") and len(ids.shape) == 2:
        if ids.shape[0] != 1:
            raise ValueError("only a single tokenizer sequence is supported")
        ids = ids[0].tolist()
    if not isinstance(ids, (list, tuple)) or not ids:
        raise TypeError("input_ids must be a non-empty list or tensor")
    if isinstance(ids[0], (list, tuple)):
        if len(ids) != 1:
            raise ValueError("only a single tokenizer sequence is supported")
        ids = ids[0]
    if not ids or any(type(token_id) is not int for token_id in ids):
        raise TypeError("input_ids must contain integer token IDs")
    return list(ids)


class NativeHFTextAdapter:
    """Implement the mini-swe-agent Model protocol with one native HF call/query."""

    def __init__(
        self,
        *,
        tokenizer: Any,
        model: Any,
        model_id: str,
        revision: str,
        context_limit: int,
        max_new_tokens: int,
        action_regex: str,
        format_error_template: str,
        observation_template: str,
        record_event: Callable[[dict[str, Any]], None],
        device: str = "cuda",
    ) -> None:
        if context_limit <= 0 or max_new_tokens <= 0 or max_new_tokens >= context_limit:
            raise ValueError("invalid context/output token limits")
        self.tokenizer = tokenizer
        self.model = model
        self.model_id = model_id
        self.revision = revision
        self.context_limit = context_limit
        self.max_new_tokens = max_new_tokens
        self.action_regex = action_regex
        self.format_error_template = format_error_template
        self.observation_template = observation_template
        self.record_event = record_event
        self.device = device
        self.n_calls = 0
        self.config = {
            "model_id": model_id,
            "revision": revision,
            "context_limit": context_limit,
            "max_new_tokens": max_new_tokens,
            "action_regex": action_regex,
        }

    @staticmethod
    def _visible_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Pass only ordered role/content text to the tokenizer; reject hidden fields."""
        visible: list[dict[str, str]] = []
        for message in messages:
            role, content = message.get("role"), message.get("content")
            if role not in {"system", "user", "assistant"} or not isinstance(content, str):
                raise ValueError("only system/user/assistant text messages are accepted")
            visible.append({"role": role, "content": content})
        if not visible or visible[0]["role"] != "system":
            raise ValueError("conversation must begin with the frozen system prompt")
        return visible

    def format_message(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Render with the model's native chat template and perform exactly one call."""
        if kwargs:
            raise ValueError("per-call overrides are forbidden; freeze decoding at construction")
        visible = self._visible_messages(messages)
        rendered = self.tokenizer.apply_chat_template(
            visible,
            tokenize=False,
            add_generation_prompt=True,
        )
        # This exact render-then-tokenize path is the one independently replayed
        # against the deployed Qwen bindings; add_special_tokens=False prevents
        # a second BOS/control-token insertion after the chat template.
        encoded = self.tokenizer(rendered, add_special_tokens=False, return_tensors="pt")
        if not isinstance(encoded, Mapping) or "input_ids" not in encoded:
            raise TypeError("native chat template must return a dict containing input_ids")
        input_ids = encoded["input_ids"]
        input_count = int(input_ids.shape[-1])
        if input_count + self.max_new_tokens > self.context_limit:
            raise ValueError(
                f"context budget exceeded: {input_count}+{self.max_new_tokens}>{self.context_limit}"
            )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        request_binding = {
            "event": "request",
            "model_id": self.model_id,
            "revision": self.revision,
            "messages_sha256": hashlib.sha256(
                json.dumps(visible, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "rendered_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            "rendered": rendered,
            "input_ids": single_sequence_token_ids(encoded),
            "input_tokens": input_count,
            "physical_calls": self.n_calls + 1,
        }
        # The durable caller must accept the request record before generation;
        # failure to persist prevents an untraceable model call.
        self.record_event(request_binding)
        started = time.monotonic()
        self.n_calls += 1
        try:
            output = self.model.generate(
                **encoded,
                do_sample=False,
                max_new_tokens=self.max_new_tokens,
                use_cache=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        except Exception as exc:
            self.record_event({
                "event": "generation_error",
                "physical_calls": self.n_calls,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "elapsed_seconds": time.monotonic() - started,
            })
            raise
        elapsed = time.monotonic() - started
        output_ids = output[0, input_count:]
        output_token_ids = output_ids.tolist()
        raw = self.tokenizer.decode(output_token_ids, skip_special_tokens=False)
        binding = {
            **request_binding,
            "event": "response",
            "output_ids": output_token_ids,
            "output_tokens": len(output_token_ids),
            "finish_reason": "eos" if output_token_ids and output_token_ids[-1] == self.tokenizer.eos_token_id else "length_or_stop",
            "elapsed_seconds": elapsed,
        }
        self.record_event(binding)
        try:
            actions = parse_regex_actions(
                raw,
                action_regex=self.action_regex,
                format_error_template=self.format_error_template,
            )
        except Exception as exc:
            # mini-swe-agent's FormatError is a recoverable agent observation;
            # retain exact raw output and token binding in that observation.
            if not hasattr(exc, "messages") or not exc.messages:
                raise
            exc.messages[0].setdefault("extra", {}).update(
                {"native_binding": binding, "raw_model_output": raw}
            )
            raise
        return {
            "role": "assistant",
            "content": raw,
            "extra": {"actions": actions, "native_binding": binding},
        }

    def format_observation_messages(
        self,
        message: dict[str, Any],
        outputs: list[dict[str, Any]],
        template_vars: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return format_observation_messages(
            outputs,
            observation_template=self.observation_template,
            template_vars=template_vars,
        )

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return {**self.config, **kwargs}

    def serialize(self) -> dict[str, Any]:
        return {"info": {"config": {"model": self.config, "model_type": type(self).__name__}}}
