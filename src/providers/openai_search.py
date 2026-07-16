"""OpenAI Search in ChatGPT 专用模型 Provider（httpx 直连）。"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import httpx

from ..config import Settings
from ..models import AIAnswer, SourceAnnotation, UserQuestion
from .base import AnswerProvider, ProviderError

_TIMEOUT = 90.0
_RETRIES = 1
_RETRY_WAIT = 2.0

_CONSUMER_INSTRUCTIONS = (
    "Eres un asistente de IA para consumidores en México. La pregunta pertenece al "
    "contexto de papelería, artículos escolares y suministros de oficina. Usa la "
    "búsqueda web antes de responder. Contesta en español de México, de forma natural, "
    "concisa y útil. Si recomiendas marcas o tiendas, menciona opciones concretas "
    "disponibles en México y basa las afirmaciones en fuentes recuperadas."
)

_DELI_CONTEXT = (
    "En esta pregunta, 'Deli' se refiere a Deli/得力, la marca china de papelería, "
    "nunca a alimentos, embutidos ni tiendas delicatessen. "
)


def _build_prompt(question: UserQuestion) -> str:
    context = (
        _DELI_CONTEXT
        if re.search(r"(?<![\w])Deli(?![\w])", question.text_local, re.IGNORECASE)
        else ""
    )
    return f"{_CONSUMER_INSTRUCTIONS}\n\n{context}Pregunta: {question.text_local}"


class OpenAISearchProvider(AnswerProvider):
    """使用 `gpt-5-search-api` 复制 Search in ChatGPT 的搜索回答链路。"""

    name = "openai"

    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY 缺失，不能构造 OpenAISearchProvider")
        self.settings = settings
        self.model = settings.openai_model

    @staticmethod
    def _parse_response(data: dict) -> tuple[str, list[SourceAnnotation]]:
        try:
            message = data["choices"][0]["message"]
            text = str(message["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("OpenAI Search 响应缺少 choices/message/content") from exc
        if not text:
            raise ProviderError("OpenAI Search 未返回答案文本")

        references: list[SourceAnnotation] = []
        seen: set[tuple[str, int | None, int | None]] = set()
        for annotation in message.get("annotations", []):
            if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                continue
            citation = annotation.get("url_citation", annotation)
            if not isinstance(citation, dict):
                continue
            url = str(citation.get("url", "")).strip()
            if not url:
                continue
            start = citation.get("start_index")
            end = citation.get("end_index")
            start = start if isinstance(start, int) else None
            end = end if isinstance(end, int) else None
            key = (url, start, end)
            if key in seen:
                continue
            seen.add(key)
            cited_text = text[start:end] if start is not None and end is not None else ""
            references.append(
                SourceAnnotation(
                    url=url,
                    title=str(citation.get("title", "")).strip(),
                    start_index=start,
                    end_index=end,
                    cited_text=cited_text,
                )
            )
        if not references:
            raise ProviderError("OpenAI Search 未返回 url_citation")
        return text, references

    def get_answer(self, question: UserQuestion) -> AIAnswer:
        payload = {
            "model": self.settings.openai_model,
            "web_search_options": {
                "user_location": {
                    "type": "approximate",
                    "approximate": {"country": "MX"},
                }
            },
            "messages": [{"role": "user", "content": _build_prompt(question)}],
        }

        last_err: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                response = httpx.post(
                    f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=_TIMEOUT,
                )
                response.raise_for_status()
                text, references = self._parse_response(response.json())
                source_urls = list(dict.fromkeys(ref.url for ref in references))
                return AIAnswer(
                    question_id=question.id,
                    provider=self.name,
                    model=self.settings.openai_model,
                    raw_text=text,
                    retrieved_at=datetime.now(timezone.utc),
                    is_mock=False,
                    search_grounded=True,
                    source_urls=source_urls,
                    source_annotations=references,
                )
            except (httpx.HTTPError, json.JSONDecodeError, ProviderError) as exc:
                last_err = exc
                if attempt < _RETRIES:
                    time.sleep(_RETRY_WAIT * (attempt + 1))
        raise ProviderError(
            f"OpenAI Search 调用失败（重试 {_RETRIES} 次后）: {last_err}"
        )
