"""Gemini Google Search Grounding Provider 契约测试（不访问网络）。"""
from __future__ import annotations

import pytest

from src.config import Settings
from src.models import UserQuestion
from src.providers import gemini_search
from src.providers.gemini_search import GeminiSearchProvider


def make_question() -> UserQuestion:
    return UserQuestion(
        id="q-gemini",
        text_local="¿Cuáles son las mejores marcas de papelería en México?",
        text_zh="墨西哥最好的文具品牌有哪些？",
        tier="category",
        funnel="TOFU",
        value_score=5,
        value_reason="高搜索量",
    )


def grounding_response() -> dict:
    first = "Deli está disponible en México."
    second = "También se vende en línea."
    return {
        "steps": [
            {
                "type": "google_search_call",
                "arguments": {
                    "queries": [
                        "mejores marcas de papelería México",
                        "Deli papelería México",
                    ]
                },
            },
            {"type": "google_search_result", "result": []},
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": first,
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": "https://www.deliworld.com/",
                                "title": "Deli official",
                                "start_index": 0,
                                "end_index": 4,
                            }
                        ],
                    },
                    {
                        "type": "text",
                        "text": second,
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": "https://www.amazon.com.mx/s?k=deli",
                                "title": "Amazon México",
                                "start_index": 0,
                                "end_index": 7,
                            }
                        ],
                    },
                ],
            },
        ]
    }


def test_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiSearchProvider(Settings(gemini_api_key=""))


def test_provider_uses_interactions_search_and_maps_text_spans(monkeypatch) -> None:
    request: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return grounding_response()

    def fake_post(url, *, headers, json, timeout):
        request.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(gemini_search.httpx, "post", fake_post)
    settings = Settings(
        gemini_api_key="test-key",
        gemini_model="gemini-3.5-flash",
    )

    answer = GeminiSearchProvider(settings).get_answer(make_question())

    assert request["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/interactions"
    )
    assert request["payload"]["model"] == "gemini-3.5-flash"
    assert request["payload"]["tools"] == [{"type": "google_search"}]
    assert answer.provider == "gemini"
    assert answer.search_grounded is True
    assert answer.search_queries == [
        "mejores marcas de papelería México",
        "Deli papelería México",
    ]
    assert answer.raw_text == (
        "Deli está disponible en México.\n\nTambién se vende en línea."
    )
    assert answer.source_annotations[0].cited_text == "Deli"
    assert answer.source_annotations[1].cited_text == "También"
    assert answer.source_annotations[1].start_index == (
        len("Deli está disponible en México.") + 2
    )
