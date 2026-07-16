"""DeepSeek V4 Web Search Provider 单元测试（不访问网络）。"""
from __future__ import annotations

from src.config import Settings
from src.models import UserQuestion
from src.providers import deepseek
from src.providers.deepseek import DeepSeekProvider


def make_question() -> UserQuestion:
    return UserQuestion(
        id="q-test",
        text_local="¿Dónde comprar productos Deli en México?",
        text_zh="在墨西哥哪里购买得力产品？",
        tier="regional",
        funnel="BOFU",
        value_score=5,
        value_reason="高购买意图",
    )


def web_search_response() -> dict:
    return {
        "content": [
            {"type": "server_tool_use", "name": "web_search"},
            {
                "type": "web_search_tool_result",
                "content": [
                    {
                        "type": "web_search_result",
                        "title": "Deli official",
                        "url": "https://www.deliworld.com/",
                    },
                    {
                        "type": "web_search_result",
                        "title": "Deli duplicate",
                        "url": "https://www.deliworld.com/",
                    },
                    {
                        "type": "web_search_result",
                        "title": "Amazon México",
                        "url": "https://www.amazon.com.mx/s?k=deli+papeleria",
                    },
                ],
            },
            {"type": "text", "text": "Deli está disponible en México."},
        ]
    }


def test_parse_web_search_response_extracts_text_and_unique_sources() -> None:
    text, sources = DeepSeekProvider._parse_web_search_response(web_search_response())

    assert text == "Deli está disponible en México."
    assert sources == [
        ("Deli official", "https://www.deliworld.com/"),
        ("Amazon México", "https://www.amazon.com.mx/s?k=deli+papeleria"),
    ]


def test_provider_uses_anthropic_web_search_and_records_urls(monkeypatch) -> None:
    request: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return web_search_response()

    def fake_post(url, *, headers, json, timeout):
        request.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(deepseek.httpx, "post", fake_post)
    settings = Settings(
        deepseek_api_key="test-key",
        deepseek_model="deepseek-v4-flash",
        deepseek_web_search=True,
        deepseek_search_max_uses=2,
    )

    answer = DeepSeekProvider(settings).get_answer(make_question())

    assert request["url"] == "https://api.deepseek.com/anthropic/v1/messages"
    assert request["payload"]["model"] == "deepseek-v4-flash"
    assert request["payload"]["tools"][0]["type"] == "web_search_20250305"
    assert request["payload"]["tools"][0]["max_uses"] == 2
    assert "Deli/得力" in request["payload"]["messages"][0]["content"]
    assert answer.provider == "deepseek"
    assert answer.is_mock is False
    assert answer.search_grounded is True
    assert answer.source_urls == [
        "https://www.deliworld.com/",
        "https://www.amazon.com.mx/s?k=deli+papeleria",
    ]
    assert "Fuentes recuperadas por búsqueda web" in answer.raw_text
