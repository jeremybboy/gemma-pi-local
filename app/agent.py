"""Strict Gemma tool protocol for the single web-search capability."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


TOOL_CALL_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the current public web when the answer requires recent or "
            "externally verified information."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A concise standalone web search query.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}

AGENT_SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You have one optional tool named web_search. Call it only when the user "
        "asks for current, recent, or externally verified public-web information. "
        "For timeless knowledge, reasoning, and attached-media analysis, answer "
        "directly without a tool. Never invent a tool result. After a tool result "
        "is supplied, answer from the provided snippets, state uncertainty where "
        "needed, and cite web-supported claims with source numbers such as [1]."
    ),
}


class AgentProtocolError(ValueError):
    """Raised when LiteRT-LM returns an unsafe or malformed tool message."""


@dataclass(frozen=True)
class WebSearchRequest:
    """Validated model request for exactly one web search."""

    call_id: str
    query: str
    raw_call: dict[str, Any]


def choice_message(payload: Any) -> dict[str, Any]:
    """Extract the first OpenAI-compatible assistant message."""

    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AgentProtocolError(
            "LiteRT-LM response did not contain choices[0].message"
        ) from exc
    if not isinstance(message, dict):
        raise AgentProtocolError("LiteRT-LM assistant message was not an object")
    return message


def message_text(message: dict[str, Any]) -> str | None:
    """Return bounded plain text from a direct assistant response."""

    content = message.get("content")
    if content is None:
        return None
    if not isinstance(content, str):
        raise AgentProtocolError("LiteRT-LM direct response was not plain text")
    return content


def web_search_request(message: dict[str, Any]) -> WebSearchRequest | None:
    """Validate zero or one OpenAI-compatible web_search tool call."""

    tool_calls = message.get("tool_calls")
    if tool_calls is None or tool_calls == []:
        return None
    if not isinstance(tool_calls, list) or not tool_calls:
        raise AgentProtocolError("LiteRT-LM tool_calls was not a non-empty list")
    if len(tool_calls) != 1:
        raise AgentProtocolError("Only one tool call is allowed per turn")

    raw_call = tool_calls[0]
    if not isinstance(raw_call, dict) or raw_call.get("type") != "function":
        raise AgentProtocolError("Tool call was not a function call")
    call_id = raw_call.get("id")
    if not isinstance(call_id, str) or not TOOL_CALL_ID_PATTERN.fullmatch(call_id):
        raise AgentProtocolError("Tool call id was missing or invalid")
    function = raw_call.get("function")
    if not isinstance(function, dict) or function.get("name") != "web_search":
        raise AgentProtocolError("Only web_search may be called")

    arguments = function.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise AgentProtocolError("web_search arguments were not valid JSON") from exc
    if not isinstance(arguments, dict) or set(arguments) != {"query"}:
        raise AgentProtocolError("web_search requires exactly one query argument")
    query = arguments.get("query")
    if not isinstance(query, str):
        raise AgentProtocolError("web_search query was not a string")
    return WebSearchRequest(call_id=call_id, query=query, raw_call=raw_call)


def assistant_tool_message(
    message: dict[str, Any], request: WebSearchRequest
) -> dict[str, Any]:
    """Build the minimal trusted assistant tool-call message for pass two."""

    return {
        "role": "assistant",
        "content": message.get("content") if isinstance(message.get("content"), str) else None,
        "tool_calls": [request.raw_call],
    }
