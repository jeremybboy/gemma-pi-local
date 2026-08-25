import json

import pytest

from app.agent import (
    AGENT_SYSTEM_MESSAGE,
    DIRECT_SYSTEM_MESSAGE,
    AgentProtocolError,
    choice_message,
    web_search_request,
)


def test_system_identity_matches_local_deployment() -> None:
    for message in (DIRECT_SYSTEM_MESSAGE, AGENT_SYSTEM_MESSAGE):
        content = message["content"]
        assert "running locally through LiteRT-LM" in content
        assert "not Google's hosted Gemini service" in content
        assert "does not run on Google servers" in content
        assert "never substitute a generic hosted-model description" in content


def test_parses_one_structured_web_search_call() -> None:
    message = choice_message(
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": json.dumps({"query": "current release"}),
                                },
                            }
                        ]
                    }
                }
            ]
        }
    )
    request = web_search_request(message)
    assert request is not None
    assert request.call_id == "call_123"
    assert request.query == "current release"


@pytest.mark.parametrize(
    "tool_calls",
    [
        [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "delete_files", "arguments": "{}"},
            }
        ],
        [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"one","extra":true}',
                },
            }
        ],
        [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "web_search", "arguments": '{"query":"one"}'},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "web_search", "arguments": '{"query":"two"}'},
            },
        ],
    ],
)
def test_rejects_unapproved_or_ambiguous_tool_calls(tool_calls: list[dict]) -> None:
    with pytest.raises(AgentProtocolError):
        web_search_request({"tool_calls": tool_calls})
