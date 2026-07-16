"""Gemini Interactions API + Google Search Grounding Provider（httpx 直连）。"""
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
    "contexto de papelería, artículos escolares y suministros de oficina. Usa Google "
    "Search antes de responder. Contesta en español de México, de forma natural, "
    "concisa y útil. Si recomiendas marcas o tiendas, menciona opciones concretas "
    "disponibles en México y basa las afirmaciones en las fuentes recuperadas."
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


class GeminiSearchProvider(AnswerProvider):
    """使用 Gemini Interactions API 的 Google Search Grounding。"""

    name = "gemini"

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY 缺失，不能构造 GeminiSearchProvider")
        self.settings = settings
        self.model = settings.gemini_model

    @staticmethod
    def _parse_response(
        data: dict,
    ) -> tuple[str, list[SourceAnnotation], list[str]]:
        steps = data.get("steps", [])
        if not isinstance(steps, list):
            raise ProviderError("Gemini Grounding 响应缺少 steps 数组")

        text_parts: list[str] = []
        references: list[SourceAnnotation] = []
        queries: list[str] = []
        seen_refs: set[tuple[str, int | None, int | None]] = set()
        text_offset = 0

        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("type") == "google_search_call":
                arguments = step.get("arguments", {})
                if isinstance(arguments, dict):
                    raw_queries = arguments.get("queries", [])
                    if isinstance(raw_queries, list):
                        queries.extend(str(q).strip() for q in raw_queries if str(q).strip())
            if step.get("type") != "model_output":
                continue
            content = step.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                block_text = str(block.get("text", "")).strip()
                if not block_text:
                    continue
                if text_parts:
                    text_offset += 2
                text_parts.append(block_text)
                for annotation in block.get("annotations", []):
                    if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                        continue
                    url = str(annotation.get("url", "")).strip()
                    if not url:
                        continue
                    local_start = annotation.get("start_index")
                    local_end = annotation.get("end_index")
                    local_start = local_start if isinstance(local_start, int) else None
                    local_end = local_end if isinstance(local_end, int) else None
                    start = text_offset + local_start if local_start is not None else None
                    end = text_offset + local_end if local_end is not None else None
                    key = (url, start, end)
                    if key in seen_refs:
                        continue
                    seen_refs.add(key)
                    cited_text = (
                        block_text[local_start:local_end]
                        if local_start is not None and local_end is not None
                        else ""
                    )
                    references.append(
                        SourceAnnotation(
                            url=url,
                            title=str(annotation.get("title", "")).strip(),
                            start_index=start,
                            end_index=end,
                            cited_text=cited_text,
                        )
                    )
                text_offset += len(block_text)

        text = "\n\n".join(text_parts)
        if not text:
            raise ProviderError("Gemini Grounding 未返回答案文本")
        if not references:
            raise ProviderError("Gemini Grounding 未返回 url_citation")
        return text, references, list(dict.fromkeys(queries))

    def get_answer(self, question: UserQuestion) -> AIAnswer:
        payload = {
            "model": self.settings.gemini_model,
            "input": _build_prompt(question),
            "tools": [{"type": "google_search"}],
        }

        last_err: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                response = httpx.post(
                    f"{self.settings.gemini_base_url.rstrip('/')}/interactions",
                    headers={
                        "x-goog-api-key": self.settings.gemini_api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=_TIMEOUT,
                )
                response.raise_for_status()
                text, references, queries = self._parse_response(response.json())
                source_urls = list(dict.fromkeys(ref.url for ref in references))
                return AIAnswer(
                    question_id=question.id,
                    provider=self.name,
                    model=self.settings.gemini_model,
                    raw_text=text,
                    retrieved_at=datetime.now(timezone.utc),
                    is_mock=False,
                    search_grounded=True,
                    source_urls=source_urls,
                    source_annotations=references,
                    search_queries=queries,
                )
            except (httpx.HTTPError, json.JSONDecodeError, ProviderError) as exc:
                last_err = exc
                if attempt < _RETRIES:
                    time.sleep(_RETRY_WAIT * (attempt + 1))
        raise ProviderError(
            f"Gemini Grounding 调用失败（重试 {_RETRIES} 次后）: {last_err}"
        )
