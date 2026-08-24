#!/usr/bin/env python3
"""Verify that the installed LiteRT-LM server emits OpenAI tool_calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("GEMMA_PI_LITERT_URL", "http://127.0.0.1:9379/v1"),
    )
    parser.add_argument(
        "--model", default=os.getenv("GEMMA_PI_MODEL", "gemma4-e4b")
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def fail(message: str, payload: Any | None = None) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, indent=2, ensure_ascii=False), file=sys.stderr)
    return 2


def main() -> int:
    args = parse_args()
    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You may call web_search when current web information is required. "
                    "Return the tool call instead of guessing."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Use web search to find the current Raspberry Pi OS release. "
                    "Do not answer from memory."
                ),
            },
        ],
        "tools": [WEB_SEARCH_TOOL],
        "tool_choice": "auto",
        "temperature": 0.0,
        "max_completion_tokens": 160,
        "stream": False,
    }
    try:
        response = httpx.post(
            f"{args.base_url.rstrip('/')}/chat/completions",
            json=payload,
            timeout=args.timeout,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return fail(f"LiteRT-LM request failed: {exc}")

    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return fail("response did not contain choices[0].message", body)
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not isinstance(tool_calls, list) or not tool_calls:
        return fail("LiteRT-LM returned no structured tool_calls", message)

    first = tool_calls[0]
    function = first.get("function", {}) if isinstance(first, dict) else {}
    if function.get("name") != "web_search":
        return fail("first tool call was not web_search", first)
    arguments = function.get("arguments")
    try:
        parsed_arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        return fail("tool arguments were not valid JSON", first)
    if not isinstance(parsed_arguments, dict) or not isinstance(
        parsed_arguments.get("query"), str
    ):
        return fail("tool call did not contain a string query", first)

    print("PASS: LiteRT-LM emitted a structured web_search tool call.")
    print(json.dumps(first, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
