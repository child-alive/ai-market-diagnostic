"""⑤ 内容缺口分析：综合问题、可见度分析与站点诊断，输出缺口清单。

Stage 0: 占位空实现；Stage 1 落地。
"""
from __future__ import annotations

from ..models import AnswerAnalysis, ContentGap, SiteAuditResult, UserQuestion


def find_gaps(
    questions: list[UserQuestion],
    analyses: list[AnswerAnalysis],
    site_audit: SiteAuditResult | None,
) -> list[ContentGap]:
    # TODO(Stage 1): 未命中问题 → 主题缺口; Stage 2: site_audit 证据接入
    return []
