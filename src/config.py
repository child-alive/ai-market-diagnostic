"""配置加载与运行模式判定。

模式规则（PLAN.md §8）：
- 显式 --mock → mock
- 任一 AI 平台 Key 已配置 → hybrid（只调用选中的 Provider）
- 无 key → mock（全链路 fixtures，保证评审者零配置可跑）
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .models import BrandProfile, RunMode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
FIXTURES_DIR = PROJECT_ROOT / "fixtures"

load_dotenv(PROJECT_ROOT / ".env")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


@dataclass
class Settings:
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "").strip()
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    deepseek_model: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    )
    deepseek_web_search: bool = field(
        default_factory=lambda: _env_flag("DEEPSEEK_WEB_SEARCH", True)
    )
    deepseek_search_max_uses: int = field(
        default_factory=lambda: int(os.getenv("DEEPSEEK_SEARCH_MAX_USES", "3"))
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip()
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5-search-api")
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip()
    )
    gemini_base_url: str = field(
        default_factory=lambda: os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        )
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    )
    force_mock: bool = False
    force_live_audit: bool = False  # mock 模式下仍对官网做实时诊断（其余环节维持 mock）

    @property
    def mode(self) -> RunMode:
        if self.force_mock or not (
            self.deepseek_api_key or self.openai_api_key or self.gemini_api_key
        ):
            return RunMode.MOCK
        return RunMode.HYBRID


# 演示用例（题目给定）：得力 × 墨西哥
DELI_PROFILE = BrandProfile(
    brand_name="Deli",
    brand_aliases=["得力", "Deli Group", "DeliWorld"],
    category="文具/办公/学生用品 (papelería, artículos de oficina y escolares)",
    market="墨西哥 (México)",
    language="es-MX",
    website_url="https://www.deliworld.com",
    seed_competitors=["BIC", "Norma", "Scribe", "Pelikan", "Faber-Castell", "Barrilito"],
)
