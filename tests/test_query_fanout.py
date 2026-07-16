"""Query Fanout 派生约束、Coverage 与离线集成测试。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src import main
from src.config import DELI_PROFILE, Settings
from src.models import AIAnswer, AnswerAnalysis, FanoutQuery, FanoutType
from src.pipeline.query_fanout import (
    _deterministic_fanouts,
    build_fanout_metrics,
    select_parent_questions,
    validate_fanout_queries,
)
from src.pipeline.question_gen import generate_questions


def test_parent_selection_uses_high_value_unbranded_questions() -> None:
    questions = generate_questions(DELI_PROFILE, Settings(force_mock=True))

    parents = select_parent_questions(questions, DELI_PROFILE, max_parents=2)

    assert [parent.id for parent in parents] == ["q05", "q07"]
    assert all(parent.query_scope.value == "unbranded" for parent in parents)


def test_deterministic_fanouts_cover_three_types_without_brand_leakage() -> None:
    questions = generate_questions(DELI_PROFILE, Settings(force_mock=True))
    parents = select_parent_questions(questions, DELI_PROFILE, max_parents=2)

    fanouts = _deterministic_fanouts(parents, branches_per_parent=3)

    assert len(fanouts) == 6
    assert all(item.is_mock for item in fanouts)
    for parent in parents:
        children = [item for item in fanouts if item.parent_question_id == parent.id]
        assert {item.fanout_type for item in children} == {
            FanoutType.PARAPHRASE,
            FanoutType.SCENARIO,
            FanoutType.FOLLOW_UP,
        }
        assert not any(
            term.casefold() in f"{item.text_local} {item.text_zh}".casefold()
            for item in children
            for term in ["Deli", "得力", "DeliWorld"]
        )


def test_fanout_validation_rejects_brand_leakage() -> None:
    questions = generate_questions(DELI_PROFILE, Settings(force_mock=True))
    parents = select_parent_questions(questions, DELI_PROFILE, max_parents=1)
    raw_items = [
        {"parent_question_id": "q05", "text_local": "¿Deli es la mejor?", "text_zh": "得力最好吗？", "fanout_type": "paraphrase"},
        {"parent_question_id": "q05", "text_local": "Escenario sin marca", "text_zh": "无品牌场景", "fanout_type": "scenario"},
        {"parent_question_id": "q05", "text_local": "Seguimiento sin marca", "text_zh": "无品牌追问", "fanout_type": "follow_up"},
    ]

    with pytest.raises(ValueError, match="泄漏"):
        validate_fanout_queries(raw_items, parents, DELI_PROFILE, 3)


def test_fanout_metrics_report_branch_and_parent_coverage() -> None:
    queries = [
        FanoutQuery(id="fo-q1-1", parent_question_id="q1", text_local="A", text_zh="甲", fanout_type="paraphrase"),
        FanoutQuery(id="fo-q1-2", parent_question_id="q1", text_local="B", text_zh="乙", fanout_type="scenario"),
        FanoutQuery(id="fo-q2-1", parent_question_id="q2", text_local="C", text_zh="丙", fanout_type="follow_up"),
    ]
    answers = [
        AIAnswer(question_id=query.id, provider="deepseek", raw_text="x", retrieved_at=datetime.now(timezone.utc), is_mock=False, search_grounded=True)
        for query in queries
    ]
    analyses = [
        AnswerAnalysis(question_id="fo-q1-1", brand_mentioned=True, brand_recommended=True, recommendation_assessed=True),
        AnswerAnalysis(question_id="fo-q1-2", brand_mentioned=False, recommendation_assessed=True),
        AnswerAnalysis(question_id="fo-q2-1", brand_mentioned=False, recommendation_assessed=True),
    ]

    metrics = build_fanout_metrics(queries, answers, analyses)

    assert metrics.mention_coverage == pytest.approx(0.3333)
    assert metrics.recommendation_coverage == pytest.approx(0.3333)
    assert metrics.parent_fanout_coverage == 0.5
    assert metrics.grounded_rate == 1.0


def test_mock_main_fanout_is_isolated_from_primary_metrics() -> None:
    report = main.run_diagnostic(
        Settings(force_mock=True),
        enable_query_fanout=True,
        fanout_parents=2,
        fanout_branches=3,
    )

    assert len(report.answers) == 8
    assert len(report.fanout_answers) == 6
    assert report.metrics.questions_checked == 8
    assert report.fanout_metrics is not None
    assert report.fanout_metrics.queries_checked == 6
    assert report.meta.notes == ["Query Fanout 使用确定性派生与 Mock 回答。"]
