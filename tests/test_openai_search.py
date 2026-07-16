"""OpenAI Search Provider 契约测试（不访问网络）。"""
from __future__ import annotations

import pytest

from src.config import Settings
from src.models import UserQuestion
from src.providers import openai_search
from src.providers.openai_search import OpenAISearchProvider


def make_question() -> UserQuestion:
    return UserQuestion(
        id="q-openai",
        text_local="¿Dónde comprar productos Deli en México?",
        text_zh="在墨西哥哪里购买得力产品？",
        tier="regional",
        funnel="BOFU",
        value_score=5,
        value_reason="高购买意图",
    )


def search_response() -> dict:
    text = "Deli está disponible en México y se vende en línea."
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": text,
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "start_index": 0,
                                "end_index": 4,
                                "title": "Deli official",
                                "url": "https://www.deliworld.com/",
                            },
                        },
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "start_index": 31,
                                "end_index": len(text),
                                "title": "Amazon México",
                                "url": "https://www.amazon.com.mx/s?k=deli",
                            },
                        },
                    ],
                }
            }
        ]
    }


def test_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAISearchProvider(Settings(openai_api_key=""))


def test_provider_uses_search_model_and_preserves_inline_citations(monkeypatch) -> None:
    request: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return search_response()

    def fake_post(url, *, headers, json, timeout):
        request.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(openai_search.httpx, "post", fake_post)
    settings = Settings(
        openai_api_key="test-key",
        openai_model="gpt-5-search-api",
    )

    answer = OpenAISearchProvider(settings).get_answer(make_question())

    assert request["url"] == "https://api.openai.com/v1/chat/completions"
    assert request["payload"]["model"] == "gpt-5-search-api"
    assert request["payload"]["web_search_options"]["user_location"] == {
        "type": "approximate",
        "approximate": {"country": "MX"},
    }
    assert "Deli/得力" in request["payload"]["messages"][0]["content"]
    assert answer.provider == "openai"
    assert answer.model == "gpt-5-search-api"
    assert answer.search_grounded is True
    assert answer.source_urls == [
        "https://www.deliworld.com/",
        "https://www.amazon.com.mx/s?k=deli",
    ]
    assert answer.source_annotations[0].cited_text == "Deli"
    assert answer.source_annotations[1].start_index == 31
