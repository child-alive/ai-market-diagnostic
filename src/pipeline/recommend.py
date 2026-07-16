"""⑥ 行动建议：P0/P1/P2 优先级清单。

Stage 0: 占位空实现；Stage 1 落地。
"""
from __future__ import annotations

from ..models import ContentGap, Recommendation, SiteAuditResult, VisibilityMetrics


def make_recommendations(
    metrics: VisibilityMetrics | None,
    gaps: list[ContentGap],
    site_audit: SiteAuditResult | None,
) -> list[Recommendation]:
    # TODO(Stage 1)
    return []
