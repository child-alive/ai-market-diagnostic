"""④ 官网轻量诊断。

检查项：robots.txt、sitemap、es-MX hreflang、结构化数据(JSON-LD)、
title/meta、西语内容、可抓取性。礼貌抓取：限速 1 req/s，最多 15 页。

降级策略：mock 模式或网络失败时读取 fixtures/site_snapshot/（得力官网真实快照），
结果标注 snapshot_mode=True。
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from ..config import FIXTURES_DIR, Settings
from ..models import BrandProfile, IssueSeverity, RunMode, SiteAuditResult, SiteIssue

MAX_PAGES = 15
RATE_LIMIT_S = 1.0
TIMEOUT = 15.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIMarketDiagnostic/0.1; research prototype)"}

# 西语功能词命中 >=4 视为存在西语内容（功能词几乎不会出现在英语文本中）
_SPANISH_MARKERS = [" para ", " con ", " una ", " según ", " más ", " también ",
                    " nuestros ", " calidad ", " oficina ", " papelería "]
_SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|svg|css|js|pdf|zip|ico|webp|mp4)(\?|$)", re.I)


class _PageSignals:
    def __init__(self) -> None:
        self.hreflangs: set[str] = set()
        self.jsonld_count = 0
        self.has_meta_desc = False
        self.has_title = False
        self.spanish_found = False
        self.internal_links: list[str] = []


def _analyze_html(html: str, base_url: str = "") -> _PageSignals:
    sig = _PageSignals()
    tree = HTMLParser(html)
    for node in tree.css("link[rel='alternate'][hreflang]"):
        sig.hreflangs.add((node.attributes.get("hreflang") or "").lower())
    sig.jsonld_count = len(tree.css("script[type='application/ld+json']"))
    sig.has_title = bool(tree.css_first("title"))
    sig.has_meta_desc = bool(tree.css_first("meta[name='description']"))
    text = " " + (tree.body.text(separator=" ") if tree.body else "") + " "
    sig.spanish_found = sum(m in text.lower() for m in _SPANISH_MARKERS) >= 4
    if base_url:
        host = urlparse(base_url).netloc
        for a in tree.css("a[href]"):
            href = urljoin(base_url, a.attributes.get("href") or "")
            if urlparse(href).netloc == host and not _SKIP_EXT.search(href):
                sig.internal_links.append(href.split("#")[0])
    return sig


def _robots_allows_all(robots_txt: str) -> bool:
    """粗检：User-agent: * 段落中是否存在 'Disallow: /'（整站封禁）。"""
    ua_star = False
    for line in robots_txt.splitlines():
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            ua_star = line.split(":", 1)[1].strip() == "*"
        elif ua_star and line.lower().startswith("disallow:"):
            if line.split(":", 1)[1].strip() == "/":
                return False
    return True


def _build_result(
    *, crawlable: bool, robots_ok: bool, sitemap_found: bool, pages_checked: int,
    signals: _PageSignals, snapshot_mode: bool,
) -> SiteAuditResult:
    has_es_mx = "es-mx" in signals.hreflangs
    has_any_es = has_es_mx or any(h.startswith("es") for h in signals.hreflangs)
    spanish = signals.spanish_found or has_any_es

    issues: list[SiteIssue] = []
    if not crawlable:
        issues.append(SiteIssue(severity=IssueSeverity.HIGH, code="SITE_UNREACHABLE",
                                detail="官网无法访问或响应异常，搜索引擎与 AI 爬虫同样无法抓取"))
    if not robots_ok:
        issues.append(SiteIssue(severity=IssueSeverity.HIGH, code="ROBOTS_BLOCKS_ALL",
                                detail="robots.txt 对所有爬虫整站封禁（Disallow: /）"))
    if not sitemap_found:
        issues.append(SiteIssue(severity=IssueSeverity.MEDIUM, code="NO_SITEMAP",
                                detail="未发现 sitemap.xml，降低搜索引擎/AI 爬虫的页面发现效率"))
    if not has_es_mx:
        hint = f"现有 hreflang: {', '.join(sorted(signals.hreflangs)) or '无'}"
        issues.append(SiteIssue(severity=IssueSeverity.HIGH, code="NO_HREFLANG_ES_MX",
                                detail=f"未声明 es-MX 语言版本，墨西哥用户与本地化 AI 检索无法定位西语内容（{hint}）"))
    if not spanish:
        issues.append(SiteIssue(severity=IssueSeverity.HIGH, code="NO_SPANISH_CONTENT",
                                detail="站内未检测到西班牙语内容，目标市场语言完全缺位"))
    if signals.jsonld_count == 0:
        issues.append(SiteIssue(severity=IssueSeverity.MEDIUM, code="NO_STRUCTURED_DATA",
                                detail="未发现 JSON-LD 结构化数据，AI 难以准确理解品牌/产品实体"))
    if not signals.has_meta_desc:
        issues.append(SiteIssue(severity=IssueSeverity.LOW, code="NO_META_DESCRIPTION",
                                detail="首页缺少 meta description"))

    return SiteAuditResult(
        crawlable=crawlable,
        robots_ok=robots_ok,
        sitemap_found=sitemap_found,
        pages_checked=pages_checked,
        has_es_mx_hreflang=has_es_mx,
        has_structured_data=signals.jsonld_count > 0,
        spanish_content_found=spanish,
        issues=issues,
        snapshot_mode=snapshot_mode,
    )


def _audit_snapshot() -> SiteAuditResult:
    snap_dir = FIXTURES_DIR / "site_snapshot"
    html = (snap_dir / "index.html").read_text(encoding="utf-8", errors="ignore")
    robots = (snap_dir / "robots.txt").read_text(encoding="utf-8", errors="ignore")
    signals = _analyze_html(html)
    return _build_result(
        crawlable=True,
        robots_ok=_robots_allows_all(robots),
        sitemap_found="sitemap:" in robots.lower(),
        pages_checked=1,
        signals=signals,
        snapshot_mode=True,
    )


def _audit_live(url: str) -> SiteAuditResult:
    base = url.rstrip("/")
    with httpx.Client(headers=_HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        robots_ok, sitemap_found = True, False
        try:
            r = client.get(f"{base}/robots.txt")
            if r.status_code == 200:
                robots_ok = _robots_allows_all(r.text)
                sitemap_found = "sitemap:" in r.text.lower()
        except httpx.HTTPError:
            pass
        if not sitemap_found:
            try:
                time.sleep(RATE_LIMIT_S)
                sitemap_found = client.get(f"{base}/sitemap.xml").status_code == 200
            except httpx.HTTPError:
                pass

        time.sleep(RATE_LIMIT_S)
        home = client.get(base)  # 失败则抛异常，由上层降级快照
        home.raise_for_status()
        signals = _analyze_html(home.text, base)
        pages_checked = 1

        # 继续礼貌抓取内部页，汇总全站信号
        seen = {base, base + "/"}
        for link in signals.internal_links:
            if pages_checked >= MAX_PAGES:
                break
            if link in seen:
                continue
            seen.add(link)
            try:
                time.sleep(RATE_LIMIT_S)
                resp = client.get(link)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                    continue
                sub = _analyze_html(resp.text)
                pages_checked += 1
                signals.hreflangs |= sub.hreflangs
                signals.jsonld_count += sub.jsonld_count
                signals.spanish_found = signals.spanish_found or sub.spanish_found
            except httpx.HTTPError:
                continue

    return _build_result(
        crawlable=True, robots_ok=robots_ok, sitemap_found=sitemap_found,
        pages_checked=pages_checked, signals=signals, snapshot_mode=False,
    )


def audit_site(profile: BrandProfile, settings: Settings) -> SiteAuditResult:
    if not profile.website_url or (settings.mode == RunMode.MOCK and not settings.force_live_audit):
        return _audit_snapshot()
    try:
        return _audit_live(profile.website_url)
    except httpx.HTTPError as e:
        print(f"[warn] 官网实时抓取失败，降级快照模式: {e}")
        return _audit_snapshot()
