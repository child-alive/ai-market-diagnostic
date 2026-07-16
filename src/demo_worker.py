"""实况演示子进程：固定无品牌词 Prompt Set，逐行输出 JSON 事件。

由 ``src.demo_api`` 启动，不对外接受任意问题文本。独立进程让 API 能在总超时后
真正终止仍在等待的上游请求，避免释放并发锁后后台线程继续消耗额度。
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from typing import TextIO

from .config import DELI_PROFILE, Settings
from .models import UserQuestion
from .pipeline.analysis import aggregate_metrics, heuristic_analyze
from .pipeline.query_fanout import select_parent_questions
from .pipeline.question_gen import generate_questions
from .providers.base import AnswerProvider, ProviderError


def select_live_questions(limit: int) -> list[UserQuestion]:
    """从版本固定的 fixture Prompt Set 选择 3~5 个高价值无品牌词。"""

    seed_settings = Settings(force_mock=True)
    questions = generate_questions(DELI_PROFILE, seed_settings)
    return select_parent_questions(questions, DELI_PROFILE, max_parents=limit)


def _write_event(stream: TextIO, event: dict) -> None:
    stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()


def run_worker(
    settings: Settings,
    question_limit: int,
    provider: AnswerProvider | None = None,
    stream: TextIO = sys.stdout,
) -> int:
    """执行迷你诊断；Provider 可注入以便零额度测试。"""

    if not 3 <= question_limit <= 5:
        _write_event(stream, {"type": "error", "message": "question_limit 必须在 3~5 之间"})
        return 2

    if provider is None:
        if not settings.deepseek_api_key or not settings.deepseek_web_search:
            _write_event(stream, {
                "type": "error",
                "message": "实况服务未配置可用的 DeepSeek Web Search",
            })
            return 2
        from .providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider(settings)

    questions = select_live_questions(question_limit)
    answers = []
    analyses = []
    _write_event(stream, {
        "type": "started",
        "message": f"固定无品牌词 Prompt Set · {len(questions)} 条 · 不回写主报告",
        "total": len(questions),
    })

    for index, question in enumerate(questions, start=1):
        _write_event(stream, {
            "type": "question",
            "question": question.model_dump(mode="json"),
            "completed": index - 1,
            "total": len(questions),
        })
        try:
            # Provider 的降级告警进入 stderr，stdout 永远保持 JSON Lines 协议。
            with contextlib.redirect_stdout(sys.stderr):
                answer = provider.get_answer(question)
            result = heuristic_analyze(answer, DELI_PROFILE)
        except (ProviderError, ValueError, RuntimeError) as exc:
            _write_event(stream, {
                "type": "error",
                "message": f"{question.id} 上游调用失败，请返回回放模式",
            })
            print(f"demo worker error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

        answers.append(answer)
        analyses.append(result)
        _write_event(stream, {
            "type": "result",
            "question": question.model_dump(mode="json"),
            "answer": answer.model_dump(mode="json"),
            "analysis": result.model_dump(mode="json"),
            "completed": index,
            "total": len(questions),
        })

    metrics = aggregate_metrics(analyses, questions, DELI_PROFILE)
    _write_event(stream, {
        "type": "completed",
        "completed": len(answers),
        "total": len(questions),
        "metrics": metrics.model_dump(mode="json"),
    })
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="在线演示的受限 DeepSeek 子进程")
    parser.add_argument("--question-limit", type=int, default=3, choices=range(3, 6))
    args = parser.parse_args()
    raise SystemExit(run_worker(Settings(), args.question_limit))


if __name__ == "__main__":
    main()
