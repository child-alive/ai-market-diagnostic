"""联网引用的页面级证据预审。

本模块不把“API 返回 URL”等同于“来源支持结论”：
1. 优先使用 OpenAI/Gemini 的原生文本区间作为 claim；
2. DeepSeek 无区间时，对答案拆句并在前 N 个搜索来源中找最佳证据；
3. 当前只做可复现的词面覆盖预审，结果始终标记需要人工复核。
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

from ..models import (
    AIAnswer,
    EvidenceMetrics,
    EvidenceReview,
    EvidenceStatus,
)

TIMEOUT = 15.0
MAX_RESPONSE_BYTES = 2_000_000
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIMarketDiagnostic/0.2; evidence-verifier)"
}
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_TOKEN_RE = re.compile(r"[a-záéíóúüñ0-9-]+", re.IGNORECASE)
_SOURCE_SECTION_RE = re.compile(
    r"(?:Fuentes recuperadas por búsqueda web|Fuentes:)\s*",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a", "al", "ante", "como", "con", "de", "del", "el", "en", "es", "esta",
    "este", "la", "las", "los", "o", "para", "por", "que", "se", "son", "su",
    "sus", "un", "una", "y", "the", "of", "in", "to", "and", "is", "are",
}


@dataclass(frozen=True)
class PageDocument:
    url: str
    text: str = ""
    title: str = ""
    error: str = ""


@dataclass(frozen=True)
class _ClaimCandidate:
    claim: str
    sources: tuple[tuple[str, str], ...]


def _is_safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def _visible_text(html: str) -> tuple[str, str]:
    tree = HTMLParser(html)
    for selector in ("script", "style", "noscript", "svg"):
        for node in tree.css(selector):
            node.decompose()
    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else ""
    root = tree.body or tree.root
    return root.text(separator="\n", strip=True), title


def fetch_page(url: str) -> PageDocument:
    if not _is_safe_public_url(url):
        return PageDocument(url=url, error="非公开 HTTP(S) URL")
    try:
        response = httpx.get(
            url,
            headers=_HEADERS,
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "text/plain" not in content_type:
            return PageDocument(url=url, error=f"不支持的内容类型: {content_type or '未知'}")
        if len(response.content) > MAX_RESPONSE_BYTES:
            return PageDocument(url=url, error="页面超过 2MB 预审上限")
        if "text/html" in content_type:
            text, title = _visible_text(response.text)
        else:
            text, title = response.text, ""
        return PageDocument(url=str(response.url), text=text, title=title)
    except httpx.HTTPError as exc:
        return PageDocument(url=url, error=str(exc))


def _segments(text: str) -> list[str]:
    segments: list[str] = []
    for part in _SENTENCE_SPLIT_RE.split(text):
        normalized = " ".join(part.split()).strip(" -*•")
        if 25 <= len(normalized) <= 800:
            segments.append(normalized)
    return segments


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if len(token) > 1 and token.lower() not in _STOPWORDS
    }


def _best_evidence(claim: str, page_text: str) -> tuple[str, float]:
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return "", 0.0
    best_quote, best_score = "", 0.0
    for segment in _segments(page_text):
        segment_tokens = _tokens(segment)
        if not segment_tokens:
            continue
        score = len(claim_tokens & segment_tokens) / len(claim_tokens)
        if score > best_score:
            best_quote, best_score = segment, score
    return best_quote, round(best_score, 4)


def _claim_candidates(
    answer: AIAnswer,
    max_sources: int,
    max_claims: int,
) -> list[_ClaimCandidate]:
    candidates: list[_ClaimCandidate] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    for annotation in answer.source_annotations:
        claim = " ".join(annotation.cited_text.split())
        if not claim:
            continue
        sources = ((annotation.url, annotation.title),)
        key = (claim, (annotation.url,))
        if key not in seen:
            seen.add(key)
            candidates.append(_ClaimCandidate(claim=claim, sources=sources))
        if len(candidates) >= max_claims:
            return candidates

    if candidates:
        return candidates

    answer_body = _SOURCE_SECTION_RE.split(answer.raw_text, maxsplit=1)[0]
    source_pool = tuple((url, "") for url in answer.source_urls[:max_sources])
    for claim in _segments(answer_body):
        if not source_pool:
            break
        key = (claim, tuple(url for url, _title in source_pool))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(_ClaimCandidate(claim=claim, sources=source_pool))
        if len(candidates) >= max_claims:
            break
    return candidates


def verify_answers(
    answers: list[AIAnswer],
    *,
    max_sources: int = 3,
    max_claims: int = 3,
    fetcher: Callable[[str], PageDocument] = fetch_page,
) -> tuple[list[EvidenceReview], EvidenceMetrics]:
    """抓取来源并对引用陈述做词面证据预审；不会输出“已人工核验”。"""

    cache: dict[str, PageDocument] = {}
    reviews: list[EvidenceReview] = []
    for answer in answers:
        candidates = _claim_candidates(answer, max(1, max_sources), max(1, max_claims))
        if not candidates and answer.search_grounded:
            reviews.append(
                EvidenceReview(
                    provider=answer.provider,
                    question_id=answer.question_id,
                    claim="",
                    status=EvidenceStatus.UNMAPPED,
                    error="联网回答缺少可验证文本区间或可拆分陈述",
                )
            )
            continue

        for candidate in candidates:
            best: tuple[PageDocument, str, str, float] | None = None
            errors: list[str] = []
            for source_url, source_title in candidate.sources:
                if source_url not in cache:
                    cache[source_url] = fetcher(source_url)
                page = cache[source_url]
                if page.error or not page.text:
                    errors.append(f"{source_url}: {page.error or '无正文'}")
                    continue
                quote, score = _best_evidence(candidate.claim, page.text)
                if best is None or score > best[3]:
                    best = (page, source_title or page.title, quote, score)

            if best is None:
                reviews.append(
                    EvidenceReview(
                        provider=answer.provider,
                        question_id=answer.question_id,
                        claim=candidate.claim,
                        source_url=candidate.sources[0][0] if candidate.sources else "",
                        source_title=candidate.sources[0][1] if candidate.sources else "",
                        status=EvidenceStatus.INACCESSIBLE,
                        error="; ".join(errors)[:1000],
                    )
                )
                continue

            page, source_title, quote, score = best
            if score >= 0.65:
                status = EvidenceStatus.SUPPORTED
            elif score >= 0.35:
                status = EvidenceStatus.PARTIAL
            else:
                status = EvidenceStatus.NOT_FOUND
            reviews.append(
                EvidenceReview(
                    provider=answer.provider,
                    question_id=answer.question_id,
                    claim=candidate.claim,
                    source_url=page.url,
                    source_title=source_title,
                    evidence_quote=quote,
                    status=status,
                    support_score=score,
                )
            )

    counts = {status: 0 for status in EvidenceStatus}
    for review in reviews:
        counts[review.status] += 1
    evaluable = sum(
        counts[status]
        for status in (
            EvidenceStatus.SUPPORTED,
            EvidenceStatus.PARTIAL,
            EvidenceStatus.NOT_FOUND,
            EvidenceStatus.CONTRADICTED,
        )
    )
    metrics = EvidenceMetrics(
        total_claims=len(reviews),
        supported=counts[EvidenceStatus.SUPPORTED],
        partial=counts[EvidenceStatus.PARTIAL],
        not_found=counts[EvidenceStatus.NOT_FOUND],
        inaccessible=counts[EvidenceStatus.INACCESSIBLE],
        unmapped=counts[EvidenceStatus.UNMAPPED],
        contradicted=counts[EvidenceStatus.CONTRADICTED],
        support_rate=(round(counts[EvidenceStatus.SUPPORTED] / evaluable, 4) if evaluable else 0.0),
    )
    return reviews, metrics
