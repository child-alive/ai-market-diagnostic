"""回答启发式解析与 GEO 指标聚合的单元测试。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.config import DELI_PROFILE
from src.models import (
    AIAnswer,
    AnswerAnalysis,
    Citation,
    CompetitorMention,
    Sentiment,
    UserQuestion,
    VisibilityMetrics,
)
from src.pipeline.analysis import (
    _normalize_competitors,
    aggregate_metrics,
    heuristic_analyze,
)
from src.pipeline.question_gen import _GEN_PROMPT, _enforce_generated_scope_contract
from src.pipeline.segmentation import (
    classify_question_scope,
    label_question_scopes,
    question_mentions_brand,
)
from src.providers.deepseek import _build_user_prompt


def make_answer(text: str, question_id: str = "test") -> AIAnswer:
    return AIAnswer(
        question_id=question_id,
        provider="mock",
        raw_text=text,
        retrieved_at=datetime.now(timezone.utc),
        is_mock=True,
    )


def make_question(text: str) -> UserQuestion:
    return UserQuestion(
        id="test",
        text_local=text,
        text_zh="测试问题",
        tier="category",
        funnel="TOFU",
        value_score=5,
        value_reason="测试",
    )


def test_deepseek_prompt_only_disambiguates_questions_that_name_deli() -> None:
    generic = _build_user_prompt(
        make_question("¿Cuáles son las mejores marcas de papelería en México?")
    )
    branded = _build_user_prompt(
        make_question("¿Dónde comprar productos Deli en México?")
    )

    assert generic == "¿Cuáles son las mejores marcas de papelería en México?"
    assert "Deli/得力" not in generic
    assert "Deli/得力" in branded
    assert branded.endswith("¿Dónde comprar productos Deli en México?")


def test_heuristic_recognizes_brand_alias_as_target_brand() -> None:
    result = heuristic_analyze(
        make_answer("DeliWorld ofrece papelería para oficinas en México."),
        DELI_PROFILE,
    )

    assert result.brand_mentioned is True
    assert result.brand_position == 1
    assert "DeliWorld" in result.evidence_quote


def test_heuristic_calculates_brand_and_competitor_positions() -> None:
    result = heuristic_analyze(
        make_answer("Norma es popular. Deli es económica. BIC tiene amplia distribución."),
        DELI_PROFILE,
    )

    assert result.brand_position == 2
    assert [(c.name, c.position) for c in result.competitors] == [
        ("Norma", 1),
        ("BIC", 3),
    ]


def test_heuristic_excludes_retailers_from_competitors() -> None:
    result = heuristic_analyze(
        make_answer("Office Depot y Amazon venden Deli, BIC y productos escolares."),
        DELI_PROFILE,
    )

    assert [c.name for c in result.competitors] == ["BIC"]
    assert result.brand_position == 1


def test_heuristic_extracts_and_deduplicates_citation_domains() -> None:
    result = heuristic_analyze(
        make_answer(
            "Fuentes: Amazon.COM.MX/producto, amazon.com.mx/otra y gob.mx/profeco."
        ),
        DELI_PROFILE,
    )

    assert [c.domain for c in result.citations] == ["amazon.com.mx", "gob.mx"]


def test_heuristic_prefers_web_search_urls_as_grounded_citations() -> None:
    answer = make_answer("Deli aparece en fake.example.com.")
    answer.search_grounded = True
    answer.source_urls = [
        "https://www.deliworld.com/about/",
        "https://www.amazon.com.mx/s?k=deli",
    ]

    result = heuristic_analyze(answer, DELI_PROFILE)

    assert [(c.domain, c.url) for c in result.citations] == [
        ("www.deliworld.com", "https://www.deliworld.com/about/"),
        ("www.amazon.com.mx", "https://www.amazon.com.mx/s?k=deli"),
    ]

    answer.search_grounded = False
    answer.source_urls = []
    answer.is_mock = False
    ungrounded = heuristic_analyze(answer, DELI_PROFILE)
    assert ungrounded.citations == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Deli tiene buena reputación y es una opción recomendable.", Sentiment.POSITIVE),
        ("Deli todavía es limitada y menos conocida que BIC.", Sentiment.NEGATIVE),
    ],
)
def test_heuristic_classifies_brand_sentiment(
    text: str,
    expected: Sentiment,
) -> None:
    result = heuristic_analyze(make_answer(text), DELI_PROFILE)

    assert result.sentiment == expected


def test_heuristic_uses_word_boundaries_for_short_brand_name() -> None:
    result = heuristic_analyze(
        make_answer("Es un diseño delicioso para estudiantes."),
        DELI_PROFILE,
    )

    assert result.brand_mentioned is False
    assert result.brand_position is None
    assert result.sentiment == Sentiment.NEUTRAL


def test_normalize_competitors_canonicalizes_deduplicates_and_filters_retailers() -> None:
    competitors = [
        CompetitorMention(name="Bic", position=1),
        CompetitorMention(name="BIC", position=2),
        CompetitorMention(name="Office Depot", position=3),
        CompetitorMention(name="Miquelrius", position=4),
    ]

    result = _normalize_competitors(competitors, DELI_PROFILE)

    assert [(item.name, item.position) for item in result] == [
        ("BIC", 1),
        ("Miquelrius", 4),
    ]


def test_aggregate_metrics_handles_empty_input() -> None:
    metrics = aggregate_metrics([])

    assert metrics.visibility_rate == 0
    assert metrics.sov == 0
    assert metrics.citation_rate == 0
    assert metrics.avg_position is None
    assert metrics.questions_checked == 0
    assert metrics.competitor_ranking == []


def test_aggregate_metrics_matches_documented_formulas() -> None:
    analyses = [
        AnswerAnalysis(
            question_id="q1",
            brand_mentioned=True,
            brand_position=2,
            competitors=[
                CompetitorMention(name="BIC", position=1),
                CompetitorMention(name="Norma", position=3),
            ],
            citations=[Citation(domain="uno.mx")],
            sentiment=Sentiment.POSITIVE,
        ),
        AnswerAnalysis(
            question_id="q2",
            brand_mentioned=False,
            competitors=[CompetitorMention(name="BIC", position=1)],
            sentiment=Sentiment.NEUTRAL,
        ),
        AnswerAnalysis(
            question_id="q3",
            brand_mentioned=True,
            brand_position=1,
            competitors=[CompetitorMention(name="Scribe", position=2)],
            citations=[Citation(domain="dos.mx")],
            sentiment=Sentiment.NEGATIVE,
        ),
    ]

    metrics = aggregate_metrics(analyses)

    assert metrics.visibility_rate == pytest.approx(0.6667)
    assert metrics.sov == pytest.approx(0.3333)
    assert metrics.avg_position == pytest.approx(1.5)
    assert metrics.citation_rate == pytest.approx(0.6667)
    assert metrics.sentiment_summary == {"pos": 1, "neu": 1, "neg": 1}
    assert metrics.questions_checked == 3


def test_aggregate_metrics_sorts_competitors_and_averages_positions() -> None:
    analyses = [
        AnswerAnalysis(
            question_id="q1",
            brand_mentioned=False,
            competitors=[
                CompetitorMention(name="BIC", position=3),
                CompetitorMention(name="Norma", position=1),
            ],
        ),
        AnswerAnalysis(
            question_id="q2",
            brand_mentioned=False,
            competitors=[
                CompetitorMention(name="BIC", position=1),
                CompetitorMention(name="Scribe", position=2),
            ],
        ),
    ]

    ranking = aggregate_metrics(analyses).competitor_ranking

    assert [item.name for item in ranking] == ["BIC", "Norma", "Scribe"]
    assert ranking[0].mention_count == 2
    assert ranking[0].avg_position == pytest.approx(2.0)
    assert ranking[0].sov == pytest.approx(0.5)


def test_query_scope_uses_tier_or_brand_term_without_substring_false_positive() -> None:
    regional_with_brand = make_question("¿Dónde comprar productos Deli en México?")
    regional_with_brand.tier = "regional"
    generic = make_question("¿Cuáles son las mejores marcas de papelería?")
    delicious = make_question("Busco un diseño delicioso para estudiantes")

    assert question_mentions_brand(regional_with_brand, DELI_PROFILE) is True
    assert classify_question_scope(regional_with_brand, DELI_PROFILE).value == "branded"
    assert classify_question_scope(generic, DELI_PROFILE).value == "unbranded"
    assert question_mentions_brand(delicious, DELI_PROFILE) is False


def test_aggregate_metrics_keeps_branded_and_unbranded_independent() -> None:
    questions = [
        UserQuestion(
            id="branded",
            text_local="¿Deli es una buena marca?",
            text_zh="得力是好品牌吗？",
            tier="brand",
            funnel="MOFU",
            value_score=4,
            value_reason="认知",
        ),
        UserQuestion(
            id="unbranded",
            text_local="¿Cuáles son las mejores marcas de papelería?",
            text_zh="最好的文具品牌有哪些？",
            tier="category",
            funnel="MOFU",
            value_score=5,
            value_reason="推荐",
        ),
    ]
    analyses = [
        AnswerAnalysis(
            question_id="branded",
            brand_mentioned=True,
            brand_position=1,
            citations=[Citation(domain="brand.example")],
            sentiment=Sentiment.POSITIVE,
        ),
        AnswerAnalysis(
            question_id="unbranded",
            brand_mentioned=False,
            competitors=[CompetitorMention(name="BIC", position=1)],
            citations=[Citation(domain="category.example")],
            sentiment=Sentiment.NEUTRAL,
        ),
    ]

    metrics = aggregate_metrics(analyses, questions, DELI_PROFILE)

    assert metrics.visibility_rate == 0.5  # 顶层旧口径仅为向后兼容
    assert metrics.branded.visibility_rate == 1.0
    assert metrics.branded.avg_position == 1.0
    assert metrics.unbranded.visibility_rate == 0.0
    assert metrics.unbranded.avg_position is None
    assert metrics.unbranded.questions_checked == 1
    assert [question.query_scope.value for question in questions] == [
        "branded",
        "unbranded",
    ]


def test_old_visibility_json_loads_with_empty_segment_defaults() -> None:
    metrics = VisibilityMetrics.model_validate(
        {
            "visibility_rate": 0.5,
            "sov": 0.2,
            "citation_rate": 1.0,
            "questions_checked": 8,
        }
    )

    assert metrics.visibility_rate == 0.5
    assert metrics.branded.questions_checked == 0
    assert metrics.unbranded.visibility_rate == 0.0


def test_question_generation_prompt_forbids_brand_leakage_into_unbranded_queries() -> None:
    prompt = _GEN_PROMPT.format(
        brand=DELI_PROFILE.brand_name,
        aliases="、".join(DELI_PROFILE.brand_aliases),
        category=DELI_PROFILE.category,
        market=DELI_PROFILE.market,
        language=DELI_PROFILE.language,
        competitors="、".join(DELI_PROFILE.seed_competitors),
    )

    assert "regional 和 category" in prompt
    assert "均不得出现 Deli 或任何别名" in prompt
    questions = label_question_scopes([make_question("哪个文具品牌最好？")], DELI_PROFILE)
    assert questions[0].query_scope.value == "unbranded"


def test_generated_question_mislabel_is_reclassified_before_aggregation() -> None:
    mislabeled = make_question("¿Dónde comprar Deli en Ciudad de México?")
    mislabeled.tier = "regional"

    corrected = _enforce_generated_scope_contract([mislabeled], DELI_PROFILE)[0]

    assert corrected.tier.value == "brand"
    assert corrected.query_scope.value == "branded"
