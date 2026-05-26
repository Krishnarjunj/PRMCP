"""prmcp.shadow_agent — OpenAI-backed validator for synthesized MCP tools.

Sits between `synth_tool.render_tool()` and `open_pr.open_pr()` inside
`run.py`: each candidate tool's source is shown to an OpenAI chat model
via function-calling. The model returns `{valid, invalid}` plus a reason;
only `valid` tools proceed to a PR.

Behavior:

- Module-level cache keyed by `tool_name`.
- 3-call budget per process. Trip → `BudgetExceeded`. Tests use
  `reset_budget()` between cases.
- `PRMCP_INJECT_429=1` fires once per process: the first live call
  raises `RetryableRateLimit` internally, sleeps 1s, then succeeds.
  This is the failure-mode beat surfaced in the trace stream.
- Real-error retry: `_call_with_retries` wraps `_call_openai` with 2
  retries + exponential backoff on transient OpenAI status codes
  (`RateLimitError`, `InternalServerError`, `APIConnectionError`,
  `APITimeoutError`). Non-retryable errors propagate immediately.
- Schema shim normalises MCP-style JSON Schema for OpenAI's function
  calling: strip `oneOf`/`anyOf`/`allOf` at any depth, promote
  `integer` → `number`, default `type: object` when `properties` exist
  without an explicit type, drop `$schema`/`$id`/`additionalProperties`.
- Lazy SDK import — `openai.OpenAI` is only constructed when `validate`
  runs, so unit tests can monkey-patch the network surface.
"""
from __future__ import annotations

import copy
import json as _json
import logging
import os
import time
from typing import Any

BUDGET_LIMIT = 3
_RETRY_SLEEP_SECONDS = 1.0
_MAX_RETRIES = 2

_logger = logging.getLogger(__name__)

_cache: dict[str, dict[str, Any]] = {}
_call_count: int = 0
_429_fired: bool = False

_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = ()
try:
    import openai as _openai_for_retries

    _RETRYABLE_EXCEPTIONS = (
        _openai_for_retries.RateLimitError,
        _openai_for_retries.APIConnectionError,
        _openai_for_retries.APITimeoutError,
        _openai_for_retries.InternalServerError,
    )
except Exception:  # noqa: BLE001
    pass


class BudgetExceeded(RuntimeError):
    """Process exhausted its shadow-agent call budget."""


class RetryableRateLimit(RuntimeError):
    """Internal signal — simulates a 429 in demo mode."""


def reset_budget() -> None:
    """Clear the cache, call counter, and 429-injection latch."""
    global _cache, _call_count, _429_fired
    _cache = {}
    _call_count = 0
    _429_fired = False


_COMBINATORS = ("oneOf", "anyOf", "allOf")
_DROP_FIELDS = ("$schema", "$id", "$ref", "examples", "additionalProperties")


def _sanitize(node: Any) -> Any:
    if isinstance(node, dict):
        for k in _COMBINATORS:
            node.pop(k, None)
        for k in _DROP_FIELDS:
            node.pop(k, None)
        if node.get("type") == "integer":
            node["type"] = "number"
        if "properties" in node and "type" not in node:
            node["type"] = "object"
        for v in node.values():
            _sanitize(v)
    elif isinstance(node, list):
        for v in node:
            _sanitize(v)
    return node


def shim_to_function_declaration(tool_name: str, schema: dict) -> dict:
    """Convert an MCP-style JSON Schema dict → OpenAI tool function spec."""
    params = _sanitize(copy.deepcopy(schema)) if schema else {"type": "object"}
    if not isinstance(params, dict):
        params = {"type": "object"}
    if "type" not in params:
        params["type"] = "object"
    return {
        "name": tool_name,
        "description": f"SDK tool wrapper for {tool_name}",
        "parameters": params,
    }


_VALIDATE_TOOL_DECL = {
    "name": "validate_tool",
    "description": (
        "Record your verdict on whether the generated MCP tool wrapper is a "
        "correct invocation of the target SDK."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["valid", "invalid"],
                "description": "valid iff the wrapper is a correct SDK call",
            },
            "reason": {
                "type": "string",
                "description": "One-sentence explanation",
            },
        },
        "required": ["verdict", "reason"],
    },
}


def _system_prompt(sdk_label: str) -> str:
    return (
        f"You are validating a generated MCP tool wrapper for the {sdk_label}. "
        "Reply by calling the validate_tool function with (verdict, reason). "
        "verdict ∈ {valid, invalid}."
    )


def _make_client(base_url: str | None):
    """Construct the live `openai.OpenAI` client. Reads `OPENAI_API_KEY`."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY must be set to invoke the shadow agent."
        )
    from openai import OpenAI

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def _maybe_inject_429() -> None:
    """Demo failure-mode beat: simulate a 429 on the first live call."""
    global _429_fired
    if _429_fired or os.environ.get("PRMCP_INJECT_429") != "1":
        return
    _429_fired = True
    try:
        raise RetryableRateLimit("simulated 429")
    except RetryableRateLimit as e:
        print(
            f"[shadow_agent] ⚠ 429 RateLimit (simulated) — sleeping "
            f"{_RETRY_SLEEP_SECONDS}s then retrying",
            flush=True,
        )
        _logger.warning(
            "shadow_agent: %s; sleeping %ss then retrying",
            e,
            _RETRY_SLEEP_SECONDS,
        )
        time.sleep(_RETRY_SLEEP_SECONDS)


def _call_with_retries(
    client: Any,
    *,
    tool_source: str,
    tool_name: str,
    schema: dict,
    model: str,
    sdk_label: str,
    max_retries: int = _MAX_RETRIES,
) -> Any:
    delay = _RETRY_SLEEP_SECONDS
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return _call_openai(
                client,
                tool_source=tool_source,
                tool_name=tool_name,
                schema=schema,
                model=model,
                sdk_label=sdk_label,
            )
        except _RETRYABLE_EXCEPTIONS as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            print(
                f"[shadow_agent] ⚠ transient {type(e).__name__} on attempt "
                f"{attempt + 1}/{max_retries + 1} — backing off {delay}s",
                flush=True,
            )
            _logger.warning(
                "shadow_agent transient error (attempt %s): %s; backoff %ss",
                attempt + 1,
                e,
                delay,
            )
            time.sleep(delay)
            delay *= 2
    assert last_exc is not None
    raise last_exc


def _call_openai(
    client: Any,
    *,
    tool_source: str,
    tool_name: str,
    schema: dict,
    model: str,
    sdk_label: str,
) -> Any:
    """Single OpenAI round-trip; unit tests monkey-patch this directly."""
    tool_decl = shim_to_function_declaration(tool_name, schema)
    tools = [
        {"type": "function", "function": _VALIDATE_TOOL_DECL},
        {"type": "function", "function": tool_decl},
    ]
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt(sdk_label)},
            {
                "role": "user",
                "content": (
                    f"Tool name: {tool_name}\n\nTool source:\n```python\n"
                    f"{tool_source}\n```"
                ),
            },
        ],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "validate_tool"}},
        temperature=0,
    )


def _extract_verdict(response: Any) -> tuple[str, str]:
    try:
        call = response.choices[0].message.tool_calls[0].function
        args = _json.loads(call.arguments)
        return args["verdict"], args["reason"]
    except Exception as e:  # noqa: BLE001
        return "invalid", f"shadow_agent: malformed response ({type(e).__name__})"


def validate(
    tool_source: str,
    tool_name: str,
    schema: dict,
    *,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
    sdk_label: str = "target SDK",
) -> dict:
    """Validate `tool_source` via OpenAI function-calling.

    Returns `{"verdict": "valid"|"invalid", "reason": str, "raw": Any}`.
    Cache key is `tool_name`; re-validating the same name returns the
    prior verdict. The 3-call budget caps live OpenAI calls per process —
    cache hits are free.
    """
    global _call_count

    if tool_name in _cache:
        return _cache[tool_name]

    if _call_count >= BUDGET_LIMIT:
        raise BudgetExceeded(
            f"shadow_agent budget of {BUDGET_LIMIT} model calls already "
            "spent for this process. Call reset_budget() in tests."
        )

    client = _make_client(base_url)
    _maybe_inject_429()
    response = _call_with_retries(
        client,
        tool_source=tool_source,
        tool_name=tool_name,
        schema=schema,
        model=model,
        sdk_label=sdk_label,
    )
    _call_count += 1

    verdict, reason = _extract_verdict(response)
    result = {"verdict": verdict, "reason": reason, "raw": response}
    _cache[tool_name] = result
    return result
