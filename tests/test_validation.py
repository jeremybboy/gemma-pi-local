import pytest

from app.main import validate_messages


def test_accepts_text_message() -> None:
    validate_messages([{"role": "user", "content": "hello"}])


def test_accepts_image_audio_and_text() -> None:
    validate_messages(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,aGVsbG8="},
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {"format": "wav", "data": "aGVsbG8="},
                    },
                    {"type": "text", "text": "Use both files."},
                ],
            }
        ]
    )


@pytest.mark.parametrize(
    ("messages", "expected"),
    [
        (
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/image.png"},
                        }
                    ],
                }
            ],
            "inline PNG",
        ),
        (
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"format": "mp3", "data": "aGVsbG8="},
                        }
                    ],
                }
            ],
            "WAV",
        ),
        ([{"role": "tool", "content": "unsafe"}], "Unsupported message role"),
    ],
)
def test_rejects_unsupported_content(messages: list[dict], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        validate_messages(messages)


def test_rejects_duplicate_images() -> None:
    image = {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,aGVsbG8="},
    }
    with pytest.raises(ValueError, match="at most one image"):
        validate_messages([{"role": "user", "content": [image, image]}])
