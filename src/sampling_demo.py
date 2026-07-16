"""DeepSeek 小规模重复采样演示。

固定同一 Prompt Set 重复请求，展示单次 AI 回答的波动；这是提交前方法论
演示，不并入主诊断管道，也不改变主报告的单轮口径。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR, DELI_PROFILE, Settings
from .pipeline.analysis import heuristic_analyze
from .pipeline.question_gen import generate_questions
from .providers.base import ProviderError
from .providers.deepseek import DeepSeekProvider

DEFAULT_QUESTION_IDS = ("q05", "q07", "q08")


def build_summary(records: list[dict], repeats: int) -> dict:
    """将逐题观测聚合为每题比例与每轮波动范围。"""

    question_ids = sorted({record["question_id"] for record in records})
    per_question: list[dict] = []
    for question_id in question_ids:
        items = [record for record in records if record["question_id"] == question_id]
        positions = [
            record["brand_position"]
            for record in items
            if record["brand_position"] is not None
        ]
        per_question.append({
            "question_id": question_id,
            "successful_samples": len(items),
            "mention_rate": round(sum(item["brand_mentioned"] for item in items) / len(items), 4),
            "recommendation_rate": round(
                sum(item["brand_recommended"] for item in items) / len(items), 4
            ),
            "position_range": [min(positions), max(positions)] if positions else None,
            "grounded_samples": sum(item["search_grounded"] for item in items),
        })

    per_round: list[dict] = []
    for round_number in range(1, repeats + 1):
        items = [record for record in records if record["round"] == round_number]
        if not items:
            continue
        per_round.append({
            "round": round_number,
            "successful_questions": len(items),
            "mention_rate": round(sum(item["brand_mentioned"] for item in items) / len(items), 4),
            "recommendation_rate": round(
                sum(item["brand_recommended"] for item in items) / len(items), 4
            ),
        })

    mention_rates = [item["mention_rate"] for item in per_round]
    recommendation_rates = [item["recommendation_rate"] for item in per_round]
    return {
        "per_question": per_question,
        "per_round": per_round,
        "mention_rate_range": [min(mention_rates), max(mention_rates)] if mention_rates else None,
        "recommendation_rate_range": (
            [min(recommendation_rates), max(recommendation_rates)]
            if recommendation_rates else None
        ),
    }


def run_sampling(
    settings: Settings,
    question_ids: list[str],
    repeats: int,
) -> dict:
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY 未配置，无法运行真实重复采样")
    if not settings.deepseek_web_search:
        raise ValueError("重复采样演示要求 DEEPSEEK_WEB_SEARCH=true")

    questions = generate_questions(DELI_PROFILE, Settings(force_mock=True))
    question_by_id = {question.id: question for question in questions}
    missing = [question_id for question_id in question_ids if question_id not in question_by_id]
    if missing:
        raise ValueError(f"未知问题 ID: {', '.join(missing)}")
    selected = [question_by_id[question_id] for question_id in question_ids]
    branded = [
        question.id for question in selected
        if question.query_scope is None or question.query_scope.value != "unbranded"
    ]
    if branded:
        raise ValueError(f"重复采样只允许无品牌词问题: {', '.join(branded)}")

    provider = DeepSeekProvider(settings)
    records: list[dict] = []
    failures: list[dict] = []
    for round_number in range(1, repeats + 1):
        for question in selected:
            try:
                answer = provider.get_answer(question)
            except ProviderError as exc:
                failures.append({
                    "round": round_number,
                    "question_id": question.id,
                    "error": str(exc),
                })
                continue
            analysis = heuristic_analyze(answer, DELI_PROFILE)
            records.append({
                "round": round_number,
                "question_id": question.id,
                "question": question.text_local,
                "answer": answer.model_dump(mode="json"),
                "brand_mentioned": analysis.brand_mentioned,
                "brand_recommended": analysis.brand_recommended,
                "brand_position": analysis.brand_position,
                "search_grounded": answer.search_grounded,
                "source_types": [
                    citation.source_type.value for citation in analysis.citations
                ],
            })

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider.name,
            "model": provider.model,
            "question_ids": question_ids,
            "repeats_requested": repeats,
            "method": "same_prompt_repeated_independent_web_search_calls",
            "limitation": "small methodology demo; not a confidence interval",
        },
        "summary": build_summary(records, repeats),
        "records": records,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek 无品牌词重复采样演示")
    parser.add_argument("--repeats", type=int, default=3, help="每题重复次数（默认 3）")
    parser.add_argument(
        "--question-ids",
        default=",".join(DEFAULT_QUESTION_IDS),
        help="逗号分隔的 fixtures 无品牌词问题 ID",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR / "示例产物" / "repeat_sampling.json",
    )
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error("--repeats 必须至少为 2")
    question_ids = [item.strip() for item in args.question_ids.split(",") if item.strip()]
    if not question_ids:
        parser.error("--question-ids 不能为空")

    try:
        result = run_sampling(Settings(), question_ids, args.repeats)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"[done] 重复采样 {len(result['records'])}/{len(question_ids) * args.repeats} 条"
    )
    print(f"[range] Mention {result['summary']['mention_rate_range']}")
    print(f"[range] Recommendation {result['summary']['recommendation_rate_range']}")
    print(f"[out]  {args.output}")


if __name__ == "__main__":
    main()
