"""DeepSeek 接入（OpenAI 兼容协议，httpx 直连）。

- DeepSeekClient: 通用 chat completion 封装（question_gen / answer_analysis 共用），
  内置 1 次重试与超时控制。
- DeepSeekProvider: AnswerProvider 实现，让 DeepSeek 扮演"消费者 AI 助手"角色
  回答目标市场用户问题（国内网络不可直连 ChatGPT/Gemini 的替代方案，见方案说明）。
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
    "Responde la pregunta del usuario en español de México, de forma natural y útil. "
    "Si la pregunta pide recomendaciones de marcas/tiendas, menciona marcas concretas "
    "disponibles en México en orden de relevancia. Al final agrega una línea "
    "'Fuentes:' con los dominios web que respaldarían tu respuesta."
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
    """用 DeepSeek 扮演 AI 回答引擎。回答为真实 LLM 输出，is_mock=False。"""

    name = "deepseek"

    def __init__(self, settings: Settings):
        self.client = DeepSeekClient(settings)

    def get_answer(self, question: UserQuestion) -> AIAnswer:
        raw_text = self.client.chat(
            [
                {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(question)},
            ],
            temperature=0.7,
        )
        return AIAnswer(
            question_id=question.id,
            provider=self.name,
            raw_text=raw_text,
            retrieved_at=datetime.now(timezone.utc),
            is_mock=False,
        )
