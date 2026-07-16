"""⑦ 报告输出：JSON 落盘 + report.html 渲染。

Stage 1: 最简 report.html（数据完整优先）；Stage 3: 视觉升级。
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..models import DiagnosticReport

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def write_json(report: DiagnosticReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    path.write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    return path


def write_html(report: DiagnosticReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)
    html = env.get_template("report.html.j2").render(r=report)
    path = out_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    return path
