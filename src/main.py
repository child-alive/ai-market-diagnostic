"""CLI 入口。

用法：
    python -m src.main --mock            # 全 Mock 模式（无需 key/网络）
    python -m src.main                   # 有 DEEPSEEK_API_KEY 时为 hybrid 模式
    python -m src.main --top-n 10        # 调整可见度检测的问题数
    python -m src.main --run-id abc12345 # 重渲染历史报告
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
from . import storage


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
    parser.add_argument("--live-audit", action="store_true",
                        help="mock 模式下仍对官网做实时诊断（其余环节维持 mock）")
    parser.add_argument("--run-id", help="从 SQLite 读取指定历史运行并重渲染报告")
    args = parser.parse_args()

    if args.run_id:
        try:
            report = storage.load_report(args.run_id)
        except storage.RunNotFoundError as exc:
            parser.error(str(exc))
        print(f"[history] run_id={report.meta.run_id} | mode={report.meta.mode.value}")
        json_path = render.write_json(report, DATA_DIR)
        html_path = render.write_html(report, DATA_DIR)
        print(f"[done] 已重渲染历史报告 | 生成时间 {report.meta.generated_at.isoformat()}")
        print(f"[out]  {json_path}")
        print(f"[out]  {html_path}  ← 双击用浏览器打开")
        return

    settings = Settings(force_mock=args.mock, force_live_audit=args.live_audit)
    print(f"[run] mode={settings.mode.value}")

    report = run_diagnostic(settings, top_n=args.top_n)
    storage.save_report(report)
    json_path = render.write_json(report, DATA_DIR)
    html_path = render.write_html(report, DATA_DIR)

    print(f"[done] 问题 {len(report.questions)} 条 | AI 回答 {len(report.answers)} 条 "
          f"| 缺口 {len(report.gaps)} 项 | 建议 {len(report.recommendations)} 条")
    print(f"[db]   run_id={report.meta.run_id} → {storage.DEFAULT_DB_PATH}")
    print(f"[out]  {json_path}")
    print(f"[out]  {html_path}  ← 双击用浏览器打开")


if __name__ == "__main__":
    main()
