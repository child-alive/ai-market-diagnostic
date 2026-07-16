"""SQLite 运行存档：保存完整报告 JSON，并按 run_id 读取历史报告。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DATA_DIR
from .models import DiagnosticReport

DEFAULT_DB_PATH = DATA_DIR / "diagnostic.db"

_CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    market TEXT NOT NULL,
    report_json TEXT NOT NULL
)
"""


class RunNotFoundError(LookupError):
    """请求的历史运行不存在。"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def save_report(
    report: DiagnosticReport,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """将一次诊断的完整报告保存到 runs 表。"""

    with _connect(db_path) as connection:
        connection.execute(_CREATE_RUNS_TABLE)
        connection.execute(
            """
            INSERT INTO runs (
                run_id, created_at, mode, brand_name, market, report_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report.meta.run_id,
                report.meta.generated_at.isoformat(),
                report.meta.mode.value,
                report.brand_profile.brand_name,
                report.brand_profile.market,
                report.model_dump_json(),
            ),
        )


def load_report(
    run_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> DiagnosticReport:
    """读取历史报告；run_id 不存在时抛出可识别的业务异常。"""

    if not db_path.exists():
        raise RunNotFoundError(f"未找到运行记录: {run_id}")

    with _connect(db_path) as connection:
        connection.execute(_CREATE_RUNS_TABLE)
        row = connection.execute(
            "SELECT report_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

    if row is None:
        raise RunNotFoundError(f"未找到运行记录: {run_id}")
    return DiagnosticReport.model_validate_json(row["report_json"])
