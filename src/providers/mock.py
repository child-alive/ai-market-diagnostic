"""MockProvider：回放 fixtures/answers/*.json，保证演示可复现、离线可运行。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..models import AIAnswer, UserQuestion
from .base import AnswerProvider

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "answers"

_GENERIC_ANSWER = (
    "Existen varias marcas y tiendas reconocidas en México para esta categoría, "
    "como BIC, Norma, Scribe y las cadenas Office Depot y Lumen. "
    "La mejor opción depende del presupuesto y del uso específico.\n\n"
    "Fuentes: mercadolibre.com.mx"
)


class MockProvider(AnswerProvider):
    name = "mock"
    model = "mock"

    def __init__(self, fixtures_dir: Path | None = None):
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR

    def get_answer(self, question: UserQuestion) -> AIAnswer:
        path = self.fixtures_dir / f"{question.id}.json"
        if path.exists():
            raw_text = json.loads(path.read_text(encoding="utf-8"))["raw_text"]
        else:
            # 未准备 fixture 的问题给通用兜底回答，避免演示中断
            raw_text = _GENERIC_ANSWER
        return AIAnswer(
            question_id=question.id,
            provider=self.name,
            model="mock",
            raw_text=raw_text,
            retrieved_at=datetime.now(timezone.utc),
            is_mock=True,
        )
