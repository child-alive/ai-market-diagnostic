"""① 问题发现：生成目标市场语言的用户问题。

hybrid 模式：DeepSeek 实时生成 20+ 问题（三层分类 + 漏斗 + 商业价值分）；
生成失败或 mock 模式：回退本地种子 fixtures/questions_seed.json。
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from ..config import FIXTURES_DIR, Settings
from ..models import BrandProfile, UserQuestion

_GEN_PROMPT = """你是一名 GEO（生成式引擎优化）市场分析师。为以下品牌生成目标市场用户会向 AI 助手提出的问题：

品牌：{brand}（别名：{aliases}）
品类：{category}
目标市场：{market}
语言：{language}
已知竞品：{competitors}

要求：
1. 生成 22 条问题，语言为目标市场语言（西班牙语-墨西哥），并附中文翻译；
2. 三层分类 tier：brand=品牌词（直接问该品牌）、regional=地区排名词（含城市/地区的排名或渠道问题）、category=品类排名词（全国性品类推荐/榜单问题）；三类都要覆盖，category 占比最高；
3. 漏斗 funnel：TOFU（认知）/ MOFU（比较）/ BOFU（决策）；
4. 商业价值 value_score 1~5 分并给一句中文理由 value_reason（考虑搜索量、购买意图、与品牌品类的匹配度）；
5. 必须包含这条题目指定的问题："¿Cuáles son las mejores marcas de papelería en México?"

只输出 JSON，格式：
{{"questions": [{{"id": "q01", "text_local": "...", "text_zh": "...", "tier": "brand|regional|category", "funnel": "TOFU|MOFU|BOFU", "value_score": 1, "value_reason": "..."}}]}}"""


def load_seed_questions() -> list[UserQuestion]:
    data = json.loads((FIXTURES_DIR / "questions_seed.json").read_text(encoding="utf-8"))
    return [UserQuestion(**q) for q in data["questions"]]


def generate_questions(profile: BrandProfile, settings: Settings) -> list[UserQuestion]:
    # 问题生成器目前仍是 DeepSeek；只配置 OpenAI/Gemini 时使用稳定种子。
    if settings.force_mock or not settings.deepseek_api_key:
        return load_seed_questions()

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
        return questions
    except (ProviderError, ValidationError, KeyError, TypeError) as e:
        print(f"[warn] question_gen LLM 生成失败，回退本地种子: {e}")
        return load_seed_questions()
