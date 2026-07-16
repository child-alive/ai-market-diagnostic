"""③ 回答结构化分析 + 指标聚合。

Stage 0: 占位实现（空分析 + 零值指标）。
Stage 1: DeepSeek JSON-mode 结构化抽取；mock 模式用词典启发式抽取。
"""
from __future__ import annotations

from ..config import Settings
from ..models import AIAnswer, AnswerAnalysis, BrandProfile, VisibilityMetrics


def analyze_answers(
    answers: list[AIAnswer], profile: BrandProfile, settings: Settings
) -> list[AnswerAnalysis]:
    # TODO(Stage 1): 结构化抽取品牌提及/竞品/引用/情感
    return [
        AnswerAnalysis(question_id=a.question_id, brand_mentioned=False, parse_degraded=True)
        for a in answers
    ]


def aggregate_metrics(analyses: list[AnswerAnalysis]) -> VisibilityMetrics:
    # TODO(Stage 1): 真正的 Visibility / SOV / Avg Position / Citation / Sentiment 聚合
    return VisibilityMetrics(
        visibility_rate=0.0,
        sov=0.0,
        avg_position=None,
        citation_rate=0.0,
        sentiment_summary={},
        competitor_ranking=[],
        questions_checked=len(analyses),
    )
