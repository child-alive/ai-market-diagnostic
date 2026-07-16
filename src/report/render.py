"""⑦ 报告输出：JSON 落盘 + report.html 渲染。

Stage 0: 仅输出 JSON。
Stage 1: 最简 report.html；Stage 3: 视觉升级。
"""
from __future__ import annotations

from pathlib import Path

from ..models import DiagnosticReport


def write_json(report: DiagnosticReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    path.write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    return path
