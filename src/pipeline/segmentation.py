"""品牌词 / 无品牌词查询分层。

分层优先遵循明确的 brand tier；其余问题只要任一语言文本命中品牌名/别名，
也归入 branded，防止 LLM 将“在哪里买 Deli”误标为 regional 后污染推荐竞争力。
"""
from __future__ import annotations

import re

from ..models import BrandProfile, QueryScope, QuestionTier, UserQuestion


def _contains_term(text: str, term: str) -> bool:
    """拉丁字母用词边界，避免 Deli 误命中 delicioso；中文等直接子串命中。"""

    normalized_text = text.casefold()
    normalized_term = term.strip().casefold()
    if not normalized_term:
        return False
    if any(character.isalpha() and ord(character) < 128 for character in normalized_term):
        return bool(
            re.search(
                rf"(?<![\w]){re.escape(normalized_term)}(?![\w])",
                normalized_text,
            )
        )
    return normalized_term in normalized_text


def question_mentions_brand(question: UserQuestion, profile: BrandProfile) -> bool:
    text = f"{question.text_local}\n{question.text_zh}"
    return any(
        _contains_term(text, term)
        for term in [profile.brand_name, *profile.brand_aliases]
    )


def classify_question_scope(question: UserQuestion, profile: BrandProfile) -> QueryScope:
    if question.tier == QuestionTier.BRAND or question_mentions_brand(question, profile):
        return QueryScope.BRANDED
    return QueryScope.UNBRANDED


def label_question_scopes(
    questions: list[UserQuestion], profile: BrandProfile
) -> list[UserQuestion]:
    for question in questions:
        question.query_scope = classify_question_scope(question, profile)
    return questions
