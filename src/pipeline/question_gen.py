"""① 问题发现：生成目标市场语言的用户问题。

hybrid 模式：DeepSeek 实时生成 20+ 问题（三层分类 + 漏斗 + 商业价值分）；
生成失败或 mock 模式：回退本地种子 fixtures/questions_seed.json。
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from ..config import FIXTURES_DIR, Settings
from ..models import BrandProfile, QuestionTier, QueryScope, UserQuestion
from .segmentation import label_question_scopes, question_mentions_brand

_GEN_PROMPT = """你是一名 GEO（生成式引擎优化）市场分析师。为以下品牌生成目标市场用户会向 AI 助手提出的问题：

品牌：{brand}（别名：{aliases}）
品类：{category}
目标市场：{market}
语言：{language}
已知竞品：{competitors}

要求：
1. 生成 22 条问题，语言为目标市场语言（西班牙语-墨西哥），并附中文翻译；
2. 三层分类 tier：brand=品牌词（问题必须明确包含品牌名或别名）、regional=无品牌词的地区排名/渠道问题、category=无品牌词的全国性品类推荐/榜单问题；三类都要覆盖，category 占比最高；
3. 严格隔离查询口径：regional 和 category 的西语原文及中文翻译中，均不得出现 {brand} 或任何别名（{aliases}）；只有 brand 问题可出现这些词；
4. 漏斗 funnel：TOFU（认知）/ MOFU（比较）/ BOFU（决策）；
5. 商业价值 value_score 1~5 分并给一句中文理由 value_reason（考虑搜索量、购买意图、与品牌品类的匹配度）；
6. 必须包含这条题目指定的问题："¿Cuáles son las mejores marcas de papelería en México?"

7. 上述指定问题必须标为 category，且保持无品牌词。

只输出 JSON，格式：
{{"questions": [{{"id": "q01", "text_local": "...", "text_zh": "...", "tier": "brand|regional|category", "funnel": "TOFU|MOFU|BOFU", "value_score": 1, "value_reason": "..."}}]}}"""


def load_seed_questions() -> list[UserQuestion]:
    data = json.loads((FIXTURES_DIR / "questions_seed.json").read_text(encoding="utf-8"))
    return [UserQuestion(**q) for q in data["questions"]]


def _enforce_generated_scope_contract(
    questions: list[UserQuestion], profile: BrandProfile
) -> list[UserQuestion]:
    """LLM 错标时以文本事实为准，不让品牌词泄漏进 unbranded。"""

    label_question_scopes(questions, profile)
    for question in questions:
        mentions_brand = question_mentions_brand(question, profile)
        if mentions_brand and question.tier != QuestionTier.BRAND:
            question.tier = QuestionTier.BRAND
            question.query_scope = QueryScope.BRANDED
        elif question.tier == QuestionTier.BRAND and not mentions_brand:
            # brand tier 本身就是品牌词口径，但新生成内容必须满足更严格的文本约束。
            raise ValueError(f"{question.id} 标为 brand 但文本未包含品牌名/别名")
    return questions


def generate_questions(profile: BrandProfile, settings: Settings) -> list[UserQuestion]:
    # 问题生成器目前仍是 DeepSeek；只配置 OpenAI/Gemini 时使用稳定种子。
    if settings.force_mock or not settings.deepseek_api_key:
        return label_question_scopes(load_seed_questions(), profile)

    from ..providers.base import ProviderError
    from ..providers.deepseek import DeepSeekClient

    prompt = _GEN_PROMPT.format(
        brand=profile.brand_name,
        aliases="、".join(profile.brand_aliases),
        category=profile.category,
        market=profile.market,
        language=profile.language,
        competitors="、".join(profile.seed_competitors),
    )
    try:
        data = DeepSeekClient(settings).chat_json(
            [{"role": "user", "content": prompt}], temperature=0.6
        )
        questions = [UserQuestion(**q) for q in data["questions"]]
        if len(questions) < 15:
            raise ProviderError(f"生成问题数不足: {len(questions)}")
        return _enforce_generated_scope_contract(questions, profile)
    except (ProviderError, ValidationError, KeyError, TypeError, ValueError) as e:
        print(f"[warn] question_gen LLM 生成失败，回退本地种子: {e}")
        return label_question_scopes(load_seed_questions(), profile)
