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
)
from src.pipeline.analysis import (
    _normalize_competitors,
    aggregate_metrics,
    heuristic_analyze,
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
