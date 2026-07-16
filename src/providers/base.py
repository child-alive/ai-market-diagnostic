"""AnswerProvider 抽象：扮演"AI 回答引擎"的角色。

接入新平台（ChatGPT / Gemini / Perplexity...）只需新增一个实现类，
pipeline 代码不感知具体平台。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import AIAnswer, UserQuestion


class AnswerProvider(ABC):
    """给定一条用户问题，返回该平台的 AI 回答。"""

    name: str = "base"

    @abstractmethod
    def get_answer(self, question: UserQuestion) -> AIAnswer:
        """获取 AI 回答。实现方负责重试与错误处理，失败时抛出 ProviderError。"""


class ProviderError(RuntimeError):
    """Provider 获取回答失败（重试耗尽后抛出）。"""
