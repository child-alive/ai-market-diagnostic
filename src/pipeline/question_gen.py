"""① 问题发现：生成目标市场语言的用户问题。

Stage 0: 仅实现 fixtures 种子回退路径。
Stage 1: 接入 DeepSeek 实时生成，失败时回退到本地种子。
"""
from __future__ import annotations

import json

from ..config import FIXTURES_DIR, Settings
from ..models import BrandProfile, UserQuestion


def load_seed_questions() -> list[UserQuestion]:
    data = json.loads((FIXTURES_DIR / "questions_seed.json").read_text(encoding="utf-8"))
    return [UserQuestion(**q) for q in data["questions"]]


def generate_questions(profile: BrandProfile, settings: Settings) -> list[UserQuestion]:
    # TODO(Stage 1): settings.mode == HYBRID 时调用 DeepSeek 生成 20+ 问题
    return load_seed_questions()
