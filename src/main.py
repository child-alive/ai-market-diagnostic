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
from .models import DiagnosticReport, EvidenceMetrics, PlatformResult, ReportMeta, RunMode
from .pipeline import analysis, evidence, gaps, question_gen, recommend, site_audit, visibility
from .providers import GeminiSearchProvider, MockProvider, OpenAISearchProvider
from .providers.base import AnswerProvider
from .report import render
from . import storage


_REAL_PROVIDER_NAMES = ("deepseek", "openai", "gemini")


def build_providers(
    settings: Settings,
    requested: list[str] | None = None,
) -> list[AnswerProvider]:
    """构造本次检测平台。

    - 未显式指定：优先保持旧行为（DeepSeek）；若只有其他 Key，选首个可用平台；
    - `auto`：运行全部已配置平台；
    - 显式列表：缺 Key 直接报错，不偷偷降级 Mock。
    """

    if settings.force_mock:
        return [MockProvider()]

    available = {
        "deepseek": bool(settings.deepseek_api_key),
        "openai": bool(settings.openai_api_key),
        "gemini": bool(settings.gemini_api_key),
    }
    if requested == ["auto"]:
        selected = [name for name in _REAL_PROVIDER_NAMES if available[name]]
    elif requested:
        unknown = [name for name in requested if name not in _REAL_PROVIDER_NAMES]
        if unknown:
            raise ValueError(f"未知 Provider: {', '.join(unknown)}")
        missing = [name for name in requested if not available[name]]
        if missing:
            env_names = ", ".join(f"{name.upper()}_API_KEY" for name in missing)
            raise ValueError(f"已选 Provider 缺少配置: {env_names}")
        selected = list(dict.fromkeys(requested))
    elif available["deepseek"]:
        selected = ["deepseek"]
    else:
        selected = [name for name in _REAL_PROVIDER_NAMES if available[name]][:1]

    if not selected:
        return [MockProvider()]

    providers: list[AnswerProvider] = []
    for name in selected:
        if name == "deepseek":
            from .providers.deepseek import DeepSeekProvider

            providers.append(DeepSeekProvider(settings))
        elif name == "openai":
            providers.append(OpenAISearchProvider(settings))
        else:
            providers.append(GeminiSearchProvider(settings))
    return providers


def build_provider(settings: Settings) -> AnswerProvider:
    """向后兼容单 Provider 调用方。"""

    return build_providers(settings)[0]


def _provider_model(provider: AnswerProvider, settings: Settings) -> str:
    configured = {
        "deepseek": settings.deepseek_model,
        "openai": settings.openai_model,
        "gemini": settings.gemini_model,
        "mock": "mock",
    }.get(provider.name, provider.name)
    return str(getattr(provider, "model", configured))


def run_diagnostic(
    settings: Settings,
    top_n: int = visibility.DEFAULT_TOP_N,
    provider_names: list[str] | None = None,
    verify_evidence: bool = False,
    evidence_max_sources: int = 3,
    evidence_max_claims: int = 3,
) -> DiagnosticReport:
    profile = DELI_PROFILE
    providers = build_providers(settings, provider_names)

    questions = question_gen.generate_questions(profile, settings)
    platform_results: list[PlatformResult] = []
    for provider in providers:
        platform_answers = visibility.check_visibility(questions, provider, top_n)
        platform_analyses = analysis.analyze_answers(platform_answers, profile, settings)
        evidence_reviews = []
        evidence_metrics = EvidenceMetrics()
        if verify_evidence:
            evidence_reviews, evidence_metrics = evidence.verify_answers(
                platform_answers,
                max_sources=evidence_max_sources,
                max_claims=evidence_max_claims,
            )
        platform_results.append(
            PlatformResult(
                provider=provider.name,
                model=_provider_model(provider, settings),
                answers=platform_answers,
                analyses=platform_analyses,
                metrics=analysis.aggregate_metrics(
                    platform_analyses, questions, profile
                ),
                evidence_reviews=evidence_reviews,
                evidence_metrics=evidence_metrics,
            )
        )

    # 保留旧报告字段为“主平台”切片，不破坏已验收的缺口/建议规则。
    primary = platform_results[0]
    answers = primary.answers
    analyses = primary.analyses
    metrics = primary.metrics
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
        platform_results=platform_results,
        meta=ReportMeta(
            generated_at=datetime.now(timezone.utc),
            mode=(
                RunMode.MOCK
                if all(result.provider == "mock" for result in platform_results)
                else RunMode.HYBRID
            ),
            run_id=uuid.uuid4().hex[:8],
            model=primary.model,
            web_search_enabled=any(
                answer.search_grounded
                for result in platform_results
                for answer in result.answers
            ),
            providers=[result.provider for result in platform_results],
            models={result.provider: result.model for result in platform_results},
            notes=(
                [f"缺口与建议仍基于主平台 {primary.provider} 的结果。"]
                if len(platform_results) > 1
                else []
            ),
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
    parser.add_argument(
        "--providers",
        help=(
            "回答平台，逗号分隔：deepseek,openai,gemini；"
            "传 auto 运行全部已配置平台（默认保持单平台）"
        ),
    )
    parser.add_argument(
        "--verify-evidence",
        action="store_true",
        help="抓取引用页面并对答案陈述做证据预审（会增加网络请求）",
    )
    parser.add_argument(
        "--evidence-max-sources",
        type=int,
        default=3,
        help="DeepSeek 每条回答最多预审的来源数（默认 3）",
    )
    parser.add_argument(
        "--evidence-max-claims",
        type=int,
        default=3,
        help="每条回答最多预审的陈述数（默认 3）",
    )
    args = parser.parse_args()

    if args.run_id:
        try:
            report = storage.load_report(args.run_id)
        except storage.RunNotFoundError as exc:
            parser.error(str(exc))
        analysis.refresh_report_metrics(report)
        if report.site_audit is not None:
            site_audit.scope_sample_sensitive_claims(report.site_audit)
            issue_details = {
                issue.code: issue.detail for issue in report.site_audit.issues
            }
            for gap in report.gaps:
                if gap.gap_type.value != "signal":
                    continue
                code = gap.title.rsplit(": ", maxsplit=1)[-1]
                if code in issue_details:
                    gap.evidence = [issue_details[code]]
        print(f"[history] run_id={report.meta.run_id} | mode={report.meta.mode.value}")
        json_path = render.write_json(report, DATA_DIR)
        html_path = render.write_html(report, DATA_DIR)
        print(f"[done] 已重渲染历史报告 | 生成时间 {report.meta.generated_at.isoformat()}")
        print(f"[out]  {json_path}")
        print(f"[out]  {html_path}  ← 双击用浏览器打开")
        return

    if args.mock and args.providers:
        parser.error("--mock 不能与 --providers 同时使用")
    if args.evidence_max_sources < 1 or args.evidence_max_claims < 1:
        parser.error("证据预审的 max-sources / max-claims 必须大于 0")
    provider_names = None
    if args.providers:
        provider_names = [name.strip().lower() for name in args.providers.split(",") if name.strip()]
        if not provider_names:
            parser.error("--providers 不能为空")
        if "auto" in provider_names and provider_names != ["auto"]:
            parser.error("auto 不能与具体 Provider 混用")

    settings = Settings(force_mock=args.mock, force_live_audit=args.live_audit)
    print(f"[run] mode={settings.mode.value}")

    try:
        report = run_diagnostic(
            settings,
            top_n=args.top_n,
            provider_names=provider_names,
            verify_evidence=args.verify_evidence,
            evidence_max_sources=args.evidence_max_sources,
            evidence_max_claims=args.evidence_max_claims,
        )
    except ValueError as exc:
        parser.error(str(exc))
    storage.save_report(report)
    json_path = render.write_json(report, DATA_DIR)
    html_path = render.write_html(report, DATA_DIR)

    print(f"[done] 问题 {len(report.questions)} 条 | AI 回答 {len(report.answers)} 条 "
          f"| 缺口 {len(report.gaps)} 项 | 建议 {len(report.recommendations)} 条")
    print(f"[db]   run_id={report.meta.run_id} → {storage.DEFAULT_DB_PATH}")
    print(f"[platforms] {', '.join(report.meta.providers)}")
    if args.verify_evidence:
        summary = ", ".join(
            f"{result.provider} {result.evidence_metrics.supported}/"
            f"{result.evidence_metrics.total_claims} supported"
            for result in report.platform_results
        )
        print(f"[evidence] {summary}")
    print(f"[out]  {json_path}")
    print(f"[out]  {html_path}  ← 双击用浏览器打开")


if __name__ == "__main__":
    main()
