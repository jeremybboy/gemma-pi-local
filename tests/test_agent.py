import json

import pytest

from app.agent import AgentProtocolError, choice_message, web_search_request


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
