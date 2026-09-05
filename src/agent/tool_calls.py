"""
Parse leaked tool markup when ChatOpenAI leaves it in message content
instead of AIMessage.tool_calls. Sarvam-105B emits several dialects.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage

_SARVAM_HEAD = re.compile(
    r"<\|tool_call_begin\|>(?:functions\.)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::(?P<idx>\d+))?",
)
_XML_BLOCK = re.compile(
    r"<tool_call>\s*(?:functions\.)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<body>.*?)(?:</tool_call>|$)",
    re.DOTALL | re.IGNORECASE,
)
_XML_ARG = re.compile(
    r"<arg_key>\s*(?P<key>[^<]+?)\s*</arg_key>\s*<arg_value>\s*(?P<val>.*?)(?:</arg_value>|(?=<arg_key>)|$)",
    re.DOTALL | re.IGNORECASE,
)
_JSON_IN_TOOL_CALL = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)


def _next_json_object(text: str, start: int) -> tuple[dict[str, Any] | None, int]:
    brace = text.find("{", start)
    if brace < 0:
        return None, start
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[brace:], start=brace):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[brace : i + 1])
                except json.JSONDecodeError:
                    return None, i + 1
                if isinstance(parsed, dict):
                    return parsed, i + 1
                return None, i + 1
    return None, start


def _coerce_arg(value: str) -> Any:
    text = value.strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def _call(name: str, args: dict[str, Any], idx: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": f"sarvam_{idx}", "type": "tool_call"}


def _from_sarvam_tokens(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _SARVAM_HEAD.finditer(text):
        args, _ = _next_json_object(text, match.end())
        if args is None:
            continue
        calls.append(_call(match.group("name"), args, match.group("idx") or str(len(calls))))
    return calls


def _from_xml_args(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _XML_BLOCK.finditer(text):
        body = match.group("body") or ""
        if body.lstrip().startswith("{"):
            continue
        args = {
            arg.group("key").strip(): _coerce_arg(arg.group("val"))
            for arg in _XML_ARG.finditer(body)
        }
        if not args and "<arg_key>" not in body:
            continue
        calls.append(_call(match.group("name"), args, str(len(calls))))
    return calls


def _from_json_blocks(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _JSON_IN_TOOL_CALL.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        name = payload.get("name") or payload.get("tool")
        raw_args = payload.get("arguments") or payload.get("args") or {}
        if not name or not isinstance(raw_args, dict):
            continue
        calls.append(_call(str(name), raw_args, str(len(calls))))
    return calls


def message_text(content: Any) -> str:
    """Flatten AIMessage.content that may be a string or a list of blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
        return "".join(parts)
    return str(content)


def desk_text_from_tools(tool_results: list[dict[str, Any]]) -> str:
    """Last-resort desk prose from tool JSON when the model returns no text."""
    lines: list[str] = []
    for row in tool_results or []:
        result = row.get("result")
        name = row.get("tool_name", "tool")
        if not isinstance(result, dict):
            continue
        if result.get("error"):
            lines.append(f"{name}: {result['error']}")
            continue
        if "eligible" in result:
            eligible = result.get("eligible") or []
            excluded = result.get("excluded_examples") or result.get("excluded") or []
            lines.append(
                "Eligible: " + (", ".join(eligible) if eligible else "none") + "."
            )
            for item in excluded:
                if isinstance(item, dict):
                    lines.append(f"Excluded {item.get('crew_id')}: {item.get('reason')}")
            continue
        if "legal" in result and isinstance(result.get("legal"), list):
            legal_ids = [item.get("crew_id") for item in result["legal"] if item.get("crew_id")]
            lines.append(
                "Legal covers: " + (", ".join(legal_ids) if legal_ids else "none") + "."
            )
            for item in result.get("excluded") or []:
                issues = item.get("issues") or []
                if issues:
                    lines.append(f"{item.get('crew_id')}: {issues[0]}")
            continue
        if "issues" in result and "legal" in result:
            if result.get("legal"):
                lines.append(result.get("consequence") or result.get("detail") or "Legal.")
            else:
                lines.extend(result.get("issues") or [result.get("detail") or "Not legal."])
            continue
        if isinstance(result.get("by_type"), list):
            for item in result["by_type"]:
                if isinstance(item, dict) and item.get("aircraft_type") is not None:
                    lines.append(f"{item['aircraft_type']}: {item.get('max_seats')} seats.")
            continue
        if "day1" in result or (isinstance(result.get("absence_impact"), dict)):
            impact = result.get("absence_impact") or result
            day1 = impact.get("day1") or impact.get("immediately_uncrewed") or []
            later = impact.get("day2_also_at_risk") or impact.get("subsequent_at_risk") or []
            lines.append("Immediately uncrewed: " + ", ".join(day1) + ".")
            if later:
                lines.append("Later days at risk: " + ", ".join(later) + ".")
            continue
    return "\n".join(lines).strip()


def parse_sarvam_tool_markup(text: str) -> list[dict[str, Any]]:
    """Extract OpenAI-style tool_calls from leaked model markup."""
    if not text:
        return []
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for call in _from_sarvam_tokens(text) + _from_xml_args(text) + _from_json_blocks(text):
        key = (call["name"], json.dumps(call["args"], sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        merged.append(call)
    return merged


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_TAG = re.compile(r"</?think>", re.IGNORECASE)


def strip_model_scratch(content: str) -> str:
    """Drop chain-of-thought and leaked tool markup from desk-visible text."""
    text = _THINK_BLOCK.sub("", content or "")
    text = _THINK_TAG.sub("", text)
    if parse_sarvam_tool_markup(text) or "<tool_call" in text or "<|tool_call" in text:
        return ""
    return text.strip()


def tool_call_signature(name: str, args: dict[str, Any] | None) -> tuple[str, str]:
    return name, json.dumps(args or {}, sort_keys=True, default=str)


def all_calls_already_run(
    tool_calls: list[dict[str, Any]],
    prior_results: list[dict[str, Any]],
) -> bool:
    if not tool_calls or not prior_results:
        return False
    seen = {
        tool_call_signature(row["tool_name"], row.get("args"))
        for row in prior_results
    }
    return all(
        tool_call_signature(tc.get("name", ""), tc.get("args")) in seen
        for tc in tool_calls
    )


def hydrate_tool_calls(message: AIMessage) -> AIMessage:
    """
    If the model already returned structured tool_calls, leave it alone.
    If it dumped markup into content, attach parsed tool_calls and
    clear the leaked tokens so they are not shown as the desk reply.
    """
    content = message_text(getattr(message, "content", None))
    structured = list(getattr(message, "tool_calls", None) or [])
    parsed = parse_sarvam_tool_markup(content) if not structured else []
    tool_calls = structured or parsed
    cleaned = strip_model_scratch(content)

    if tool_calls:
        cleaned = ""
    elif cleaned == content:
        return message

    return AIMessage(
        content=cleaned,
        tool_calls=tool_calls,
        additional_kwargs=getattr(message, "additional_kwargs", {}) or {},
        response_metadata=getattr(message, "response_metadata", {}) or {},
        id=getattr(message, "id", None),
    )
