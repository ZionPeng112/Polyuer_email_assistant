import json

import httpx

from email_assistant.models import LLMImage
from email_assistant.providers.n1n import N1NLLMProvider


def test_n1n_provider_sends_multimodal_payload_when_images_are_present():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"category":"GENERAL"}'}}]},
        )

    provider = N1NLLMProvider("test-key", "vision-model")
    provider._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.n1n.ai/v1",
    )

    provider.analyze(
        system_prompt="system",
        user_prompt="user",
        images=[
            LLMImage(
                source="attachment",
                attachment_id="att-1",
                filename="poster.png",
                content_type="image/png",
                size=3,
                sha256="abc",
                data_url="data:image/png;base64,YWJj",
            )
        ],
    )

    content = requests[0]["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "user"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/png;base64,YWJj"
