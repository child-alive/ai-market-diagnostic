"""④ 官网轻量诊断。

检查项：robots.txt、AI crawler 分项、llms.txt、sitemap、es-MX hreflang、
结构化数据(JSON-LD)、原始 HTML 可读性、FAQ/直接回答结构、title/meta、
西语内容与可抓取性。礼貌抓取：限速 1 req/s，最多 15 页。

降级策略：mock 模式或网络失败时读取 fixtures/site_snapshot/（得力官网真实快照），
结果标注 snapshot_mode=True。
"""
from __future__ import annotations

import re
import time
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from ..config import FIXTURES_DIR, Settings
from ..models import (
    AICrawlerAccess,
    BrandProfile,
    CrawlerPurpose,
    IssueSeverity,
    RunMode,
    SiteAuditResult,
    SiteIssue,
)

MAX_PAGES = 15
RATE_LIMIT_S = 1.0
TIMEOUT = 15.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIMarketDiagnostic/0.1; research prototype)"}

# 西语功能词命中 >=4 视为存在西语内容（功能词几乎不会出现在英语文本中）
_SPANISH_MARKERS = [" para ", " con ", " una ", " según ", " más ", " también ",
                    " nuestros ", " calidad ", " oficina ", " papelería "]
_SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|svg|css|js|pdf|zip|ico|webp|mp4)(\?|$)", re.I)
_AI_CRAWLERS = [
    ("GPTBot", CrawlerPurpose.TRAINING),
    # Google-Extended 是 robots.txt product token：同时控制 Gemini 训练与
    # Gemini Apps / Vertex AI 的部分 Grounding，不是一个独立 HTTP user-agent。
    ("Google-Extended", CrawlerPurpose.BOTH),
    ("ClaudeBot", CrawlerPurpose.TRAINING),
    ("Bytespider", CrawlerPurpose.TRAINING),
    ("CCBot", CrawlerPurpose.TRAINING),
    ("OAI-SearchBot", CrawlerPurpose.RETRIEVAL),
    ("ChatGPT-User", CrawlerPurpose.RETRIEVAL),
    ("PerplexityBot", CrawlerPurpose.RETRIEVAL),
]


class _PageSignals:
    def __init__(self) -> None:
        self.hreflangs: set[str] = set()
        self.jsonld_count = 0
        self.has_meta_desc = False
        self.has_title = False
        self.spanish_found = False
        self.internal_links: list[str] = []
        self.raw_html_text_chars = 0
        self.brand_in_raw_html = False
        self.likely_js_dependent = False
        self.direct_answer_content_found = False
        self.faq_content_found = False


def _text_mentions_term(text: str, term: str) -> bool:
    normalized_term = term.strip().casefold()
    if not normalized_term:
        return False
    if any(character.isalpha() and ord(character) < 128 for character in normalized_term):
        return bool(
            re.search(
                rf"(?<![\w]){re.escape(normalized_term)}(?![\w])",
                text.casefold(),
            )
        )
    return normalized_term in text.casefold()


def _analyze_html(
    html: str,
    base_url: str = "",
    brand_terms: list[str] | None = None,
) -> _PageSignals:
    sig = _PageSignals()
    tree = HTMLParser(html)
    for node in tree.css("link[rel='alternate'][hreflang]"):
        sig.hreflangs.add((node.attributes.get("hreflang") or "").lower())
    sig.jsonld_count = len(tree.css("script[type='application/ld+json']"))
    sig.has_title = bool(tree.css_first("title"))
    sig.has_meta_desc = bool(tree.css_first("meta[name='description']"))
    text = " " + (tree.body.text(separator=" ") if tree.body else "") + " "
    sig.spanish_found = sum(m in text.lower() for m in _SPANISH_MARKERS) >= 4
    content_node = tree.css_first("main") or tree.css_first("article") or tree.body
    content_text = " ".join(
        (content_node.text(separator=" ") if content_node else "").split()
    )
    sig.raw_html_text_chars = len(content_text)
    sig.brand_in_raw_html = any(
        _text_mentions_term(content_text, term) for term in (brand_terms or [])
    )
    sig.likely_js_dependent = (
        sig.raw_html_text_chars < 300
        or bool(brand_terms and not sig.brand_in_raw_html)
    )
    paragraphs = [
        " ".join(node.text(separator=" ").split())
        for node in tree.css("p")
    ]
    sig.direct_answer_content_found = any(
        100 <= len(paragraph) <= 1200 and len(paragraph.split()) >= 15
        for paragraph in paragraphs
    )
    headings = " ".join(
        node.text(separator=" ") for node in tree.css("h1, h2, h3, h4")
    ).casefold()
    sig.faq_content_found = (
        "faqpage" in html.casefold()
        or bool(tree.css("details"))
        or any(marker in headings for marker in ("faq", "preguntas frecuentes", "常见问题"))
    )
    if base_url:
        host = urlparse(base_url).netloc
        for a in tree.css("a[href]"):
            href = urljoin(base_url, a.attributes.get("href") or "")
            if urlparse(href).netloc == host and not _SKIP_EXT.search(href):
                sig.internal_links.append(href.split("#")[0])
    return sig


def _audit_ai_crawlers(robots_txt: str) -> list[AICrawlerAccess]:
    parser = robotparser.RobotFileParser()
    parser.parse(robots_txt.splitlines())
    declared_agents = {
        line.split(":", 1)[1].strip().casefold()
        for line in robots_txt.splitlines()
        if line.strip().casefold().startswith("user-agent:")
    }
    has_wildcard = "*" in declared_agents
    results: list[AICrawlerAccess] = []
    for user_agent, purpose in _AI_CRAWLERS:
        key = user_agent.casefold()
        results.append(
            AICrawlerAccess(
                user_agent=user_agent,
                purpose=purpose,
                allowed=parser.can_fetch(user_agent, "/") if robots_txt.strip() else True,
                rule_source=(
                    "specific"
                    if key in declared_agents
                    else "wildcard"
                    if has_wildcard
                    else "no_rule"
                ),
            )
        )
    return results


def _plain_text_resource_exists(response: httpx.Response) -> bool:
    if response.status_code != 200 or not response.text.strip():
        return False
    prefix = response.text.lstrip()[:300].casefold()
    return "<html" not in prefix and "<!doctype html" not in prefix


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
    signals: _PageSignals, snapshot_mode: bool, robots_txt: str,
    llms_txt_found: bool, llms_full_txt_found: bool,
) -> SiteAuditResult:
    has_es_mx = "es-mx" in signals.hreflangs
    has_any_es = has_es_mx or any(h.startswith("es") for h in signals.hreflangs)
    spanish = signals.spanish_found or has_any_es
    ai_crawlers = _audit_ai_crawlers(robots_txt)

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
                                detail=f"本次抓取的 {pages_checked} 页范围内未发现 es-MX 声明，墨西哥用户与本地化 AI 检索难以定位西语内容（{hint}）"))
    if not spanish:
        issues.append(SiteIssue(severity=IssueSeverity.HIGH, code="NO_SPANISH_CONTENT",
                                detail=f"本次抓取的 {pages_checked} 页范围内未检测到西班牙语内容，建议扩大抓取后复核并补齐目标市场内容"))
    if signals.jsonld_count == 0:
        issues.append(SiteIssue(severity=IssueSeverity.MEDIUM, code="NO_STRUCTURED_DATA",
                                detail="未发现 JSON-LD 结构化数据，AI 难以准确理解品牌/产品实体"))
    if not signals.has_meta_desc:
        issues.append(SiteIssue(severity=IssueSeverity.LOW, code="NO_META_DESCRIPTION",
                                detail="首页缺少 meta description"))
    blocked_retrieval = [
        crawler.user_agent
        for crawler in ai_crawlers
        if crawler.purpose in {CrawlerPurpose.RETRIEVAL, CrawlerPurpose.BOTH}
        and not crawler.allowed
    ]
    if blocked_retrieval:
        issues.append(SiteIssue(
            severity=IssueSeverity.HIGH,
            code="AI_RETRIEVAL_CRAWLERS_BLOCKED",
            detail=f"搜索/引用或 Grounding 相关 AI 访问被 robots.txt 阻止: {', '.join(blocked_retrieval)}",
        ))
    if not llms_txt_found:
        issues.append(SiteIssue(
            severity=IssueSeverity.LOW,
            code="NO_LLMS_TXT",
            detail="未发现 /llms.txt（新兴的 LLM 内容导航约定，当前非强制标准）",
        ))
    if signals.likely_js_dependent:
        issues.append(SiteIssue(
            severity=IssueSeverity.MEDIUM,
            code="LIKELY_JS_DEPENDENT",
            detail=(
                f"首页原始 HTML 可提取正文约 {signals.raw_html_text_chars} 字符，"
                f"品牌实体{'已' if signals.brand_in_raw_html else '未'}出现，可能依赖客户端 JS 渲染"
            ),
        ))
    if not signals.direct_answer_content_found:
        issues.append(SiteIssue(
            severity=IssueSeverity.LOW,
            code="NO_DIRECT_ANSWER_CONTENT",
            detail="未发现容易被 AI 直接抽取的完整说明段落（启发式检查）",
        ))
    if not signals.faq_content_found:
        issues.append(SiteIssue(
            severity=IssueSeverity.LOW,
            code="NO_FAQ_CONTENT",
            detail="未发现 FAQPage / details / 常见问题标题结构（启发式检查）",
        ))

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
        advanced_checks_completed=True,
        ai_crawlers=ai_crawlers,
        llms_txt_found=llms_txt_found,
        llms_full_txt_found=llms_full_txt_found,
        raw_html_text_chars=signals.raw_html_text_chars,
        brand_in_raw_html=signals.brand_in_raw_html,
        likely_js_dependent=signals.likely_js_dependent,
        direct_answer_content_found=signals.direct_answer_content_found,
        faq_content_found=signals.faq_content_found,
    )


def scope_sample_sensitive_claims(result: SiteAuditResult) -> SiteAuditResult:
    """历史报告旧文案的口径收敛；不重新抓取、不改检查结果。"""

    for issue in result.issues:
        if issue.code == "NO_HREFLANG_ES_MX":
            hint_match = re.search(r"[（(]现有 hreflang:.*[）)]", issue.detail)
            hint = hint_match.group(0) if hint_match else ""
            issue.detail = (
                f"本次抓取的 {result.pages_checked} 页范围内未发现 es-MX 声明，"
                f"墨西哥用户与本地化 AI 检索难以定位西语内容{hint}"
            )
        elif issue.code == "NO_SPANISH_CONTENT":
            issue.detail = (
                f"本次抓取的 {result.pages_checked} 页范围内未检测到西班牙语内容，"
                "建议扩大抓取后复核并补齐目标市场内容"
            )
    return result


def _audit_snapshot(profile: BrandProfile) -> SiteAuditResult:
    snap_dir = FIXTURES_DIR / "site_snapshot"
    html = (snap_dir / "index.html").read_text(encoding="utf-8", errors="ignore")
    robots = (snap_dir / "robots.txt").read_text(encoding="utf-8", errors="ignore")
    signals = _analyze_html(html, brand_terms=[profile.brand_name, *profile.brand_aliases])
    return _build_result(
        crawlable=True,
        robots_ok=_robots_allows_all(robots),
        sitemap_found="sitemap:" in robots.lower(),
        pages_checked=1,
        signals=signals,
        snapshot_mode=True,
        robots_txt=robots,
        llms_txt_found=False,
        llms_full_txt_found=False,
    )


def _audit_live(url: str, profile: BrandProfile) -> SiteAuditResult:
    base = url.rstrip("/")
    with httpx.Client(headers=_HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        robots_ok, sitemap_found = True, False
        robots_txt = ""
        try:
            r = client.get(f"{base}/robots.txt")
            if r.status_code == 200:
                robots_txt = r.text
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

        llms_checks: dict[str, bool] = {}
        for filename in ("llms.txt", "llms-full.txt"):
            try:
                time.sleep(RATE_LIMIT_S)
                llms_checks[filename] = _plain_text_resource_exists(
                    client.get(f"{base}/{filename}")
                )
            except httpx.HTTPError:
                llms_checks[filename] = False

        time.sleep(RATE_LIMIT_S)
        home = client.get(base)  # 失败则抛异常，由上层降级快照
        home.raise_for_status()
        brand_terms = [profile.brand_name, *profile.brand_aliases]
        signals = _analyze_html(home.text, base, brand_terms)
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
                sub = _analyze_html(resp.text, brand_terms=brand_terms)
                pages_checked += 1
                signals.hreflangs |= sub.hreflangs
                signals.jsonld_count += sub.jsonld_count
                signals.spanish_found = signals.spanish_found or sub.spanish_found
                signals.direct_answer_content_found = (
                    signals.direct_answer_content_found
                    or sub.direct_answer_content_found
                )
                signals.faq_content_found = (
                    signals.faq_content_found or sub.faq_content_found
                )
            except httpx.HTTPError:
                continue

    return _build_result(
        crawlable=True, robots_ok=robots_ok, sitemap_found=sitemap_found,
        pages_checked=pages_checked, signals=signals, snapshot_mode=False,
        robots_txt=robots_txt,
        llms_txt_found=llms_checks.get("llms.txt", False),
        llms_full_txt_found=llms_checks.get("llms-full.txt", False),
    )


def audit_site(profile: BrandProfile, settings: Settings) -> SiteAuditResult:
    if not profile.website_url or (settings.mode == RunMode.MOCK and not settings.force_live_audit):
        return _audit_snapshot(profile)
    try:
        return _audit_live(profile.website_url, profile)
    except httpx.HTTPError as e:
        print(f"[warn] 官网实时抓取失败，降级快照模式: {e}")
        return _audit_snapshot(profile)
