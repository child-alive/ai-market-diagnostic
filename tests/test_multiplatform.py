"""多平台调度与分平台指标测试（不访问网络）。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src import main
from src.config import Settings
from src.models import (
    AIAnswer,
    EvidenceMetrics,
    EvidenceReview,
    EvidenceStatus,
    UserQuestion,
)
from src.providers.base import AnswerProvider
from src.report.render import write_html


class FakeSearchProvider(AnswerProvider):
    def __init__(self, name: str, model: str, answer_text: str):
        self.name = name
        self.model = model
        self.answer_text = answer_text

    def get_answer(self, question: UserQuestion) -> AIAnswer:
        return AIAnswer(
            question_id=question.id,
            provider=self.name,
            model=self.model,
            raw_text=self.answer_text,
            retrieved_at=datetime.now(timezone.utc),
            is_mock=False,
            search_grounded=True,
            source_urls=[f"https://example.com/{self.name}/{question.id}"],
        )


def clean_settings(**kwargs) -> Settings:
    values = {
        "deepseek_api_key": "",
        "openai_api_key": "",
        "gemini_api_key": "",
    }
    values.update(kwargs)
    return Settings(**values)


def test_build_providers_respects_keys_auto_and_explicit_failures() -> None:
    assert [p.name for p in main.build_providers(clean_settings())] == ["mock"]
    assert [
        p.name
        for p in main.build_providers(clean_settings(openai_api_key="openai-test"))
    ] == ["openai"]

    all_keys = clean_settings(
        deepseek_api_key="deepseek-test",
        openai_api_key="openai-test",
        gemini_api_key="gemini-test",
    )
    assert [p.name for p in main.build_providers(all_keys, ["auto"])] == [
        "deepseek",
        "openai",
        "gemini",
    ]
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        main.build_providers(clean_settings(openai_api_key="openai-test"), ["gemini"])


def test_run_diagnostic_keeps_primary_compatibility_and_platform_metrics(
    monkeypatch,
) -> None:
    providers = [
        FakeSearchProvider(
            "openai",
            "gpt-test",
            "Deli es una marca recomendada junto con BIC.",
        ),
        FakeSearchProvider(
            "gemini",
            "gemini-test",
            "Norma y BIC son marcas populares de papelería.",
        ),
    ]
    monkeypatch.setattr(main, "build_providers", lambda settings, names: providers)

    report = main.run_diagnostic(
        clean_settings(force_mock=True),
        top_n=2,
        provider_names=["openai", "gemini"],
    )

    assert report.meta.mode.value == "hybrid"
    assert report.meta.providers == ["openai", "gemini"]
    assert report.meta.models == {"openai": "gpt-test", "gemini": "gemini-test"}
    assert len(report.platform_results) == 2
    assert report.platform_results[0].metrics.visibility_rate == 1.0
    assert report.platform_results[1].metrics.visibility_rate == 0.0
    assert all(a.provider == "openai" for a in report.answers)
    assert all(a.provider == "openai" for a in report.analyses)
    assert report.metrics == report.platform_results[0].metrics
    assert "主平台 openai" in report.meta.notes[0]


def test_report_renders_platform_comparison_and_machine_evidence_warning(
    monkeypatch,
    tmp_path,
) -> None:
    providers = [
        FakeSearchProvider("openai", "gpt-test", "Deli es recomendada junto con BIC."),
        FakeSearchProvider("gemini", "gemini-test", "BIC y Norma son populares."),
    ]
    monkeypatch.setattr(main, "build_providers", lambda settings, names: providers)
    report = main.run_diagnostic(
        clean_settings(force_mock=True),
        top_n=1,
        provider_names=["openai", "gemini"],
    )
    report.platform_results[0].evidence_reviews = [
        EvidenceReview(
            provider="openai",
            question_id=report.answers[0].question_id,
            claim="Deli es recomendada.",
            source_url="https://example.com/evidence",
            source_title="Fuente de prueba",
            evidence_quote="Deli es una marca recomendada para oficinas.",
            status=EvidenceStatus.SUPPORTED,
            support_score=0.75,
        )
    ]
    report.platform_results[0].evidence_metrics = EvidenceMetrics(
        total_claims=1,
        supported=1,
        support_rate=1.0,
    )

    html = write_html(report, tmp_path).read_text(encoding="utf-8")

    assert "多平台横向对比" in html
    assert "OPENAI" in html and "GEMINI" in html
    assert "机器预审 · 需人工复核" in html
    assert 'href="https://example.com/evidence"' in html
    assert "来自 DeepSeek Web Search" not in html
