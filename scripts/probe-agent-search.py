#!/usr/bin/env python3
"""Exercise local-only and agentic-search turns through the real web gateway."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

import httpx


CITATION_PATTERN = re.compile(r"\[\d+\]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="gemma4-e4b")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=600.0)
    return parser.parse_args()


def run_turn(
    client: httpx.Client,
    base_url: str,
    model: str,
    prompt: str,
) -> tuple[str, dict[str, Any] | None]:
    answer = ""
    search_event: dict[str, Any] | None = None
    with client.stream(
        "POST",
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 384,
        },
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            payload = json.loads(data)
            if payload.get("type") == "search":
                search_event = payload
                continue
            delta = payload.get("choices", [{}])[0].get("delta", {}).get("content")
            if isinstance(delta, str):
                answer += delta
    return answer.strip(), search_event


def fail(message: str) -> int:
    print(f"INTEGRATION FAIL: {message}", file=sys.stderr)
    return 2


def main() -> int:
    args = parse_args()
    if not 1 <= args.cycles <= 3:
        return fail("--cycles must be between 1 and 3")

    try:
        with httpx.Client(timeout=args.timeout) as client:
            for cycle in range(1, args.cycles + 1):
                print(f"=== INTEGRATION CYCLE {cycle}/{args.cycles}: LOCAL ===")
                local_answer, local_search = run_turn(
                    client,
                    args.base_url,
                    args.model,
                    "Calculate 17 multiplied by 19. Explain briefly without web search.",
                )
                if local_search is not None:
                    return fail("timeless arithmetic unexpectedly triggered web search")
                if not local_answer:
                    return fail("local turn returned no text")
                print(local_answer[:500])

                print(f"=== INTEGRATION CYCLE {cycle}/{args.cycles}: SEARCH ===")
                search_answer, search_event = run_turn(
                    client,
                    args.base_url,
                    args.model,
                    "Search the web for the current Raspberry Pi OS release and cite sources.",
                )
                if search_event is None:
                    return fail("current-information turn did not trigger web search")
                sources = search_event.get("sources")
                if not isinstance(sources, list) or not sources:
                    return fail("search event contained no source links")
                if not search_answer:
                    return fail("search turn returned no text")
                if not CITATION_PATTERN.search(search_answer):
                    return fail("search answer did not contain a numbered citation")
                print(f"query: {search_event.get('query')}")
                print(f"sources: {len(sources)}")
                print(search_answer[:1_000])
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        return fail(f"gateway request failed: {exc}")

    print(
        f"INTEGRATION PASS: {args.cycles} local turn(s) and "
        f"{args.cycles} agentic-search turn(s) worked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
