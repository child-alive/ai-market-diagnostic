"""DeepSeek 接入（OpenAI + Anthropic 兼容协议，httpx 直连）。

- DeepSeekClient: 通用 chat completion 封装（question_gen / answer_analysis 共用），
  内置 1 次重试与超时控制。
- DeepSeekProvider: AnswerProvider 实现，让 DeepSeek 扮演"消费者 AI 助手"角色
  并通过 Anthropic Web Search server tool 获取真实搜索来源。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import httpx

from ..config import Settings
from ..models import AIAnswer, UserQuestion
from .base import AnswerProvider, ProviderError

_TIMEOUT = 90.0
_RETRIES = 1  # 失败后重试次数
_RETRY_WAIT = 2.0


class DeepSeekClient:
    def __init__(self, settings: Settings):
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY 缺失，不应构造 DeepSeekClient（应走 Mock）")
        self.settings = settings

    def chat(
        self,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        payload: dict = {
            "model": self.settings.deepseek_model,
            "messages": messages,
            "temperature": temperature,
            "thinking": {"type": "disabled"},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_err: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                resp = httpx.post(
                    f"{self.settings.deepseek_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
                    json=payload,
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as e:
                last_err = e
                if attempt < _RETRIES:
                    time.sleep(_RETRY_WAIT * (attempt + 1))
        raise ProviderError(f"DeepSeek 调用失败（重试 {_RETRIES} 次后）: {last_err}")

    def chat_json(self, messages: list[dict], temperature: float = 0.2) -> dict:
        """JSON mode 调用并解析；返回 dict，解析失败抛 ProviderError。"""
        text = self.chat(messages, json_mode=True, temperature=temperature)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ProviderError(f"DeepSeek JSON 输出解析失败: {e}; 原文前 200 字: {text[:200]}")


_ANSWER_SYSTEM_PROMPT = (
    "Eres un asistente de IA para consumidores en México, similar a ChatGPT. "
    "Todas las preguntas pertenecen al contexto de papelería, artículos escolares "
    "y suministros de oficina. "
    "Debes usar la búsqueda web al menos una vez antes de responder. "
    "Responde la pregunta del usuario en español de México, de forma natural, concisa y útil. "
    "Si la pregunta pide recomendaciones de marcas/tiendas, menciona marcas concretas "
    "disponibles en México en orden de relevancia. Basa las afirmaciones en los resultados "
    "recuperados y no inventes fuentes ni URLs."
)

_ANSWER_FALLBACK_SYSTEM_PROMPT = (
    "Eres un asistente de IA para consumidores en México. Todas las preguntas "
    "pertenecen al contexto de papelería, artículos escolares y suministros de oficina. "
    "La búsqueda web no está disponible en esta solicitud: responde de forma útil, "
    "pero declara la limitación y no inventes fuentes ni URLs."
)

_DELI_CONTEXT = (
    "Contexto: en esta pregunta, 'Deli' se refiere a Deli/得力, la marca china "
    "de papelería, nunca a alimentos, embutidos ni tiendas delicatessen.\n\n"
)


def _build_user_prompt(question: UserQuestion) -> str:
    """只对原问题已出现 Deli 的问法追加消歧，避免污染通用可见度测量。"""

    if re.search(r"(?<![\w])Deli(?![\w])", question.text_local, re.IGNORECASE):
        return f"{_DELI_CONTEXT}Pregunta: {question.text_local}"
    return question.text_local


class DeepSeekProvider(AnswerProvider):
    """用 DeepSeek + Web Search 扮演 AI 回答引擎。"""

    name = "deepseek"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = DeepSeekClient(settings)

    @staticmethod
    def _parse_web_search_response(data: dict) -> tuple[str, list[tuple[str, str]]]:
        """提取最终文本和 server tool 返回的搜索结果标题/URL。"""

        blocks = data.get("content", [])
        if not isinstance(blocks, list):
            raise ProviderError("DeepSeek Web Search 响应缺少 content 数组")

        text_parts: list[str] = []
        sources: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and block.get("text"):
                text_parts.append(str(block["text"]).strip())
            if block.get("type") != "web_search_tool_result":
                continue
            results = block.get("content", [])
            if not isinstance(results, list):
                continue
            for item in results:
                if not isinstance(item, dict) or item.get("type") != "web_search_result":
                    continue
                url = str(item.get("url", "")).strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = str(item.get("title", "")).strip() or url
                sources.append((title, url))

        if not text_parts:
            raise ProviderError("DeepSeek Web Search 未返回最终文本")
        if not sources:
            raise ProviderError("DeepSeek Web Search 未返回搜索来源 URL")
        return "\n\n".join(text_parts), sources

    def _web_search_answer(self, question: UserQuestion) -> tuple[str, list[str]]:
        payload = {
            "model": self.settings.deepseek_model,
            "max_tokens": 1800,
            "system": _ANSWER_SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": _build_user_prompt(question)},
            ],
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max(1, self.settings.deepseek_search_max_uses),
                    "user_location": {"type": "approximate", "country": "MX"},
                }
            ],
        }

        last_err: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                response = httpx.post(
                    f"{self.settings.deepseek_base_url.rstrip('/')}/anthropic/v1/messages",
                    headers={
                        "x-api-key": self.settings.deepseek_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=_TIMEOUT,
                )
                response.raise_for_status()
                text, sources = self._parse_web_search_response(response.json())
                appendix = "\n".join(f"- {title} — {url}" for title, url in sources)
                return (
                    f"{text}\n\nFuentes recuperadas por búsqueda web:\n{appendix}",
                    [url for _title, url in sources],
                )
            except (httpx.HTTPError, KeyError, json.JSONDecodeError, ProviderError) as exc:
                last_err = exc
                if attempt < _RETRIES:
                    time.sleep(_RETRY_WAIT * (attempt + 1))
        raise ProviderError(
            f"DeepSeek Web Search 调用失败（重试 {_RETRIES} 次后）: {last_err}"
        )

    def get_answer(self, question: UserQuestion) -> AIAnswer:
        source_urls: list[str] = []
        if self.settings.deepseek_web_search:
            try:
                raw_text, source_urls = self._web_search_answer(question)
            except ProviderError as exc:
                print(f"[warn] {question.id} Web Search 失败，降级普通回答: {exc}")
                raw_text = self.client.chat(
                    [
                        {"role": "system", "content": _ANSWER_FALLBACK_SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_prompt(question)},
                    ],
                    temperature=0.7,
                )
        else:
            raw_text = self.client.chat(
                [
                    {"role": "system", "content": _ANSWER_FALLBACK_SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(question)},
                ],
                temperature=0.7,
            )
        return AIAnswer(
            question_id=question.id,
            provider=self.name,
            model=self.settings.deepseek_model,
            raw_text=raw_text,
            retrieved_at=datetime.now(timezone.utc),
            is_mock=False,
            search_grounded=bool(source_urls),
            source_urls=source_urls,
        )
