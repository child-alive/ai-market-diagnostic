"""② AI 可见度检测：对高价值问题逐条获取 AI 回答。"""
from __future__ import annotations

from ..models import AIAnswer, UserQuestion
from ..providers.base import AnswerProvider, ProviderError

DEFAULT_TOP_N = 8


def select_top_questions(questions: list[UserQuestion], top_n: int = DEFAULT_TOP_N) -> list[UserQuestion]:
    """按商业价值分降序取 Top-N；同分时保持种子顺序（稳定排序）。"""
    return sorted(questions, key=lambda q: -q.value_score)[:top_n]


def check_visibility(
    questions: list[UserQuestion],
    provider: AnswerProvider,
    top_n: int = DEFAULT_TOP_N,
) -> list[AIAnswer]:
    answers: list[AIAnswer] = []
    for q in select_top_questions(questions, top_n):
        try:
            answers.append(provider.get_answer(q))
        except ProviderError:
            # 单条失败不阻断整体：跳过并由上层在报告 meta 中记录
            continue
    return answers
