"""SQLite 历史报告存档测试。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.config import DELI_PROFILE
from src.models import DiagnosticReport, ReportMeta, RunMode
from src.storage import RunNotFoundError, load_report, save_report


def make_report(run_id: str = "test-run") -> DiagnosticReport:
    return DiagnosticReport(
        brand_profile=DELI_PROFILE,
        meta=ReportMeta(
            generated_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
            mode=RunMode.MOCK,
            run_id=run_id,
        ),
    )


def test_storage_round_trip_preserves_complete_report(tmp_path) -> None:
    db_path = tmp_path / "diagnostic.db"
    original = make_report()

    save_report(original, db_path)
    restored = load_report(original.meta.run_id, db_path)

    assert restored == original
    assert db_path.exists()


def test_storage_raises_clear_error_for_unknown_run(tmp_path) -> None:
    db_path = tmp_path / "diagnostic.db"

    with pytest.raises(RunNotFoundError, match="missing-run"):
        load_report("missing-run", db_path)
