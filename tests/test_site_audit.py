"""AI 爬虫、llms.txt 与原始 HTML 可读性检查。"""
from __future__ import annotations

import httpx

from src.config import DELI_PROFILE, Settings
from src.models import SiteAuditResult
from src.pipeline.site_audit import (
    _analyze_html,
    _audit_ai_crawlers,
    _plain_text_resource_exists,
    audit_site,
)


def test_ai_crawler_audit_distinguishes_specific_and_wildcard_rules() -> None:
    robots = """User-agent: *
Allow: /

User-agent: GPTBot
Disallow: /

User-agent: OAI-SearchBot
Allow: /
"""

    crawlers = {item.user_agent: item for item in _audit_ai_crawlers(robots)}

    assert crawlers["GPTBot"].allowed is False
    assert crawlers["GPTBot"].rule_source == "specific"
    assert crawlers["OAI-SearchBot"].allowed is True
    assert crawlers["OAI-SearchBot"].purpose.value == "retrieval"
    assert crawlers["Google-Extended"].purpose.value == "both"
    assert crawlers["ClaudeBot"].allowed is True
    assert crawlers["ClaudeBot"].rule_source == "wildcard"


def test_html_readability_flags_js_shell_and_recognizes_extractable_content() -> None:
    shell = _analyze_html(
        "<html><body><div id='app'></div><script src='app.js'></script></body></html>",
        brand_terms=["Deli"],
    )
    rich = _analyze_html(
        """<html><body><main><h1>Deli office supplies</h1>
        <p>Deli provides practical stationery and office products for students,
        families, schools and professional teams across many everyday work and
        learning scenarios, with clear product information and support. The page
        explains product uses, materials, availability, maintenance and warranty
        details in plain language so a visitor can understand the offer without
        running client-side scripts or opening another application.</p>
        <h2>FAQ</h2><details><summary>Where to buy?</summary>Online.</details>
        </main></body></html>""",
        brand_terms=["Deli"],
    )

    assert shell.likely_js_dependent is True
    assert shell.brand_in_raw_html is False
    assert rich.likely_js_dependent is False
    assert rich.brand_in_raw_html is True
    assert rich.direct_answer_content_found is True
    assert rich.faq_content_found is True


def test_llms_txt_check_rejects_soft_404_html() -> None:
    valid = httpx.Response(200, text="# Example\nUseful links")
    soft_404 = httpx.Response(200, text="<!doctype html><html>Not found</html>")

    assert _plain_text_resource_exists(valid) is True
    assert _plain_text_resource_exists(soft_404) is False


def test_snapshot_audit_populates_advanced_fields_and_old_json_stays_compatible() -> None:
    result = audit_site(DELI_PROFILE, Settings(force_mock=True))
    legacy = SiteAuditResult.model_validate({"pages_checked": 15})

    assert result.advanced_checks_completed is True
    assert len(result.ai_crawlers) == 8
    assert {item.purpose.value for item in result.ai_crawlers} == {
        "training",
        "retrieval",
        "both",
    }
    assert result.raw_html_text_chars > 300
    assert result.brand_in_raw_html is True
    assert result.likely_js_dependent is False
    assert legacy.advanced_checks_completed is False
    assert legacy.ai_crawlers == []
