"""CLI 入口。

用法：
    python -m src.main --mock            # 全 Mock 模式（无需 key/网络）
    python -m src.main                   # 有 DEEPSEEK_API_KEY 时为 hybrid 模式
    python -m src.main --top-n 10        # 调整可见度检测的问题数
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone

from .config import DATA_DIR, DELI_PROFILE, Settings
from .models import DiagnosticReport, ReportMeta, RunMode
from .pipeline import analysis, gaps, question_gen, recommend, site_audit, visibility
from .providers import MockProvider
from .providers.base import AnswerProvider
from .report import render


def build_provider(settings: Settings) -> AnswerProvider:
    if settings.mode == RunMode.HYBRID:
        from .providers.deepseek import DeepSeekProvider

        return DeepSeekProvider(settings)
    return MockProvider()


def run_diagnostic(settings: Settings, top_n: int = visibility.DEFAULT_TOP_N) -> DiagnosticReport:
    profile = DELI_PROFILE
    provider = build_provider(settings)

    questions = question_gen.generate_questions(profile, settings)
    answers = visibility.check_visibility(questions, provider, top_n)
    analyses = analysis.analyze_answers(answers, profile, settings)
    metrics = analysis.aggregate_metrics(analyses)
    audit = site_audit.audit_site(profile, settings)
    gap_list = gaps.find_gaps(questions, analyses, audit)
    recs = recommend.make_recommendations(metrics, gap_list, audit)

    return DiagnosticReport(
        brand_profile=profile,
        questions=questions,
        answers=answers,
        analyses=analyses,
        metrics=metrics,
        site_audit=audit,
        gaps=gap_list,
        recommendations=recs,
        meta=ReportMeta(
            generated_at=datetime.now(timezone.utc),
            mode=settings.mode,
            run_id=uuid.uuid4().hex[:8],
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 海外市场诊断智能体")
    parser.add_argument("--mock", action="store_true", help="强制全 Mock 模式")
    parser.add_argument("--top-n", type=int, default=visibility.DEFAULT_TOP_N,
                        help="可见度检测的问题数（默认 8）")
    args = parser.parse_args()

    settings = Settings(force_mock=args.mock)
    print(f"[run] mode={settings.mode.value}")

    report = run_diagnostic(settings, top_n=args.top_n)
    json_path = render.write_json(report, DATA_DIR)

    print(f"[done] 问题 {len(report.questions)} 条 | AI 回答 {len(report.answers)} 条 "
          f"| 缺口 {len(report.gaps)} 项 | 建议 {len(report.recommendations)} 条")
    print(f"[out]  {json_path}")


if __name__ == "__main__":
    main()
