"""④ 官网轻量诊断。

Stage 0: 占位（快照模式空结果）。
Stage 2: robots/sitemap/hreflang/JSON-LD/西语内容检查，失败降级本地快照。
"""
from __future__ import annotations

from ..config import Settings
from ..models import BrandProfile, SiteAuditResult


def audit_site(profile: BrandProfile, settings: Settings) -> SiteAuditResult:
    # TODO(Stage 2): 真实抓取与检查
    return SiteAuditResult(snapshot_mode=True)
