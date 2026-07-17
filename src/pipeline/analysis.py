"""③ 回答结构化分析 + 指标聚合。

两条抽取路径：
- hybrid：DeepSeek JSON-mode 结构化抽取；失败重试 1 次（Client 内置），
  仍失败则降级到启发式抽取并标记 parse_degraded=True；
- mock：直接走启发式抽取（词典 + 正则），确定性、可单测、离线可跑。

指标命名对齐聚路国际数据检测平台，且全部按 branded / unbranded 分层独立聚合：
Mention Rate (Visibility) / Recommendation Rate / SOV / Avg Position /
Citation Rate (来源覆盖率，回答附带搜索来源的占比) / Sentiment / Source Mix。
顶层旧字段保留全样本口径仅为向后兼容，头版结论只使用 unbranded 切片。
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..config import Settings
from ..models import (
    AIAnswer,
    AnswerAnalysis,
    BrandProfile,
    Citation,
    CompetitorMention,
    CompetitorRank,
    DiagnosticReport,
    QueryScope,
    Sentiment,
    SourceType,
    UserQuestion,
    VisibilityMetrics,
    VisibilitySegmentMetrics,
)
from .segmentation import classify_question_scope, label_question_scopes

# 墨西哥文具/办公品类的常见品牌词典（启发式抽取用；生产环境应换实体词典服务）
KNOWN_BRANDS = [
    "BIC", "Norma", "Scribe", "Pelikan", "Faber-Castell", "Barrilito",
    "Paper Mate", "Pilot", "Zebra", "Crayola", "Pritt", "3M", "Post-it",
    "Esselte", "Leitz", "Sablón", "HP", "Epson", "Casio", "Maped", "Dixon",
]
# 渠道/零售商不计入品牌 SOV，但保留在竞品提及里价值有限，直接排除
RETAILERS = {
    "Office Depot", "OfficeMax", "Lumen", "Ofix", "Waldo's",
    "Amazon", "Mercado Libre", "Walmart", "Chedraui",
}

_DOMAIN_RE = re.compile(
    r"\b((?:[a-z0-9-]+\.)+(?:com\.mx|gob\.mx|org\.mx|mx|com|org|net))(/[\w\-./]*)?",
    re.IGNORECASE,
)

_POSITIVE_CUES = [
    "buena reputación", "vale la pena", "recomend", "buena relación calidad-precio",
    "buena calidad", "confiable", "mejor opción", "razonable",
]
_NEGATIVE_CUES = [
    "menos conocida", "todavía es limitada", "no se recomienda", "mala calidad",
    "evita", "poco confiable", "queja",
]
_RECOMMENDATION_CUES = [
    "recomend", "recommend", "vale la pena", "worth considering", "worth buying",
    "mejor opción", "buena opción", "good option", "opción razonable", "razonable para",
    "ideal para", "conviene", "首选", "推荐", "值得购买", "值得考虑",
]
_NEGATED_RECOMMENDATION_CUES = [
    "no se recomienda", "no recomiendo", "not recommended", "do not recommend",
    "evita ", "avoid ", "不推荐", "不要选择",
]
_RECOMMENDATION_LIST_CUES = [
    "marcas recomend", "mejores marcas", "mejor balance", "opciones recomend",
    "recommended brands", "best brands", "top brands", "推荐品牌", "最佳品牌",
]

_ECOMMERCE_DOMAINS = (
    "amazon.", "mercadolibre.", "officedepot.", "officemax.", "lumen.com.mx",
    "ofix.com", "walmart.", "chedraui.", "ebay.", "aliexpress.", "suning.com",
    "shopify.", "szlcsc.com", "smzdm.com",
)
_FORUM_DOMAINS = (
    "reddit.", "quora.", "stackexchange.", "facebook.", "xiaohongshu.",
    "bbs.",
)
_DIRECTORY_DOMAINS = (
    "yelp.", "yellowpages.", "seccionamarilla.", "hotfrog.", "cylex.",
    "crunchbase.", "linkedin.", "directorio", "ipaddress.", "top-rated.",
    "storecensus.", "qyresearch.", "researchandmarkets.", "indexbox.",
    "dunsguide.", "52wmb.", "hypestat.", "verif.",
)
_AUTHORITY_MEDIA_DOMAINS = (
    "eluniversal.", "forbes.", "reuters.", "apnews.", "bbc.", "nytimes.",
    "milenio.", "eleconomista.", "expansion.", "inegi.org.mx", "imt.mx",
    "udg.mx", "lopezdoriga.com", "esemanal.mx", "163.com", "zeelive.com.tw",
)


# ---------------------------------------------------------------- 启发式抽取

def _find_brand_mentions(text: str, names: list[str]) -> dict[str, int]:
    """返回 {品牌名: 首次出现的字符位置}，大小写不敏感、词边界匹配。"""
    found: dict[str, int] = {}
    for name in names:
        m = re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text, re.IGNORECASE)
        if m:
            found[name] = m.start()
    return found


def _evidence_sentence(text: str, pos: int) -> str:
    """截取包含指定位置的句子/列表行作为证据。"""
    start = max(text.rfind("\n", 0, pos), text.rfind(". ", 0, pos))
    start = start + 1 if start >= 0 else 0
    end_candidates = [i for i in (text.find("\n", pos), text.find(". ", pos)) if i >= 0]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end].strip().strip("-*• ").strip()


def classify_source_type(domain: str, profile: BrandProfile) -> SourceType:
    """按可解释的域名规则给引用来源分层；未知来源保守归 other。"""

    normalized = domain.casefold().split(":", maxsplit=1)[0].removeprefix("www.")
    official = (urlparse(profile.website_url).hostname or "").casefold().removeprefix("www.")
    if official and (normalized == official or normalized.endswith(f".{official}")):
        return SourceType.OFFICIAL
    if any(marker in normalized for marker in _ECOMMERCE_DOMAINS):
        return SourceType.ECOMMERCE
    if any(marker in normalized for marker in _FORUM_DOMAINS):
        return SourceType.FORUM
    if any(marker in normalized for marker in _DIRECTORY_DOMAINS):
        return SourceType.DIRECTORY
    if (
        normalized in {"gov", "gov.mx", "gob.mx", "edu", "edu.mx"}
        or normalized.endswith((".gov", ".gov.mx", ".gob.mx", ".edu", ".edu.mx"))
        or any(marker in normalized for marker in _AUTHORITY_MEDIA_DOMAINS)
    ):
        return SourceType.AUTHORITY_MEDIA
    return SourceType.OTHER


def _classify_citations(
    citations: list[Citation], profile: BrandProfile
) -> list[Citation]:
    for citation in citations:
        citation.source_type = classify_source_type(citation.domain, profile)
    return citations


def _citations_from_source_urls(
    source_urls: list[str], profile: BrandProfile
) -> list[Citation]:
    """将 Web Search 返回的 URL 转成权威 Citation，按 URL 去重。"""

    citations: list[Citation] = []
    seen: set[str] = set()
    for url in source_urls:
        normalized_url = url.strip()
        domain = urlparse(normalized_url).netloc.lower()
        if not domain or normalized_url in seen:
            continue
        seen.add(normalized_url)
        citations.append(Citation(
            domain=domain,
            url=normalized_url,
            source_type=classify_source_type(domain, profile),
        ))
    return citations


def _is_brand_recommended(text: str, brand_pos: int | None) -> bool:
    """区分“被列举/描述”与“被作为候选建议”；结果仍是启发式。"""

    if brand_pos is None:
        return False
    evidence_sentence = _evidence_sentence(text, brand_pos).casefold()
    if any(cue in evidence_sentence for cue in _NEGATED_RECOMMENDATION_CUES):
        return False
    if any(cue in evidence_sentence for cue in _RECOMMENDATION_CUES):
        return True

    line_start = text.rfind("\n", 0, brand_pos) + 1
    line_end = text.find("\n", brand_pos)
    raw_line = text[line_start:line_end if line_end >= 0 else len(text)]
    is_list_item = bool(re.match(r"\s*(?:[-*•]|\d+[.)])\s*", raw_line))
    preceding = text[max(0, line_start - 700):line_start].casefold()
    return is_list_item and any(cue in preceding for cue in _RECOMMENDATION_LIST_CUES)


def heuristic_analyze(answer: AIAnswer, profile: BrandProfile) -> AnswerAnalysis:
    text = answer.raw_text
    brand_names = [profile.brand_name] + profile.brand_aliases
    competitor_names = [
        n for n in dict.fromkeys(list(profile.seed_competitors) + KNOWN_BRANDS)
        if n not in RETAILERS
    ]

    brand_hits = _find_brand_mentions(text, brand_names)
    comp_hits = _find_brand_mentions(text, competitor_names)

    # 出现顺序 = 排名顺位（1-based）：把品牌与竞品统一按首次出现位置排序
    brand_first = min(brand_hits.values()) if brand_hits else None
    entities: list[tuple[str, int, bool]] = [(n, p, False) for n, p in comp_hits.items()]
    if brand_first is not None:
        entities.append((profile.brand_name, brand_first, True))
    entities.sort(key=lambda t: t[1])

    brand_position = None
    competitors: list[CompetitorMention] = []
    for rank, (name, _pos, is_brand) in enumerate(entities, start=1):
        if is_brand:
            brand_position = rank
        else:
            competitors.append(CompetitorMention(name=name, position=rank))

    if answer.search_grounded and answer.source_urls:
        citations = _citations_from_source_urls(answer.source_urls, profile)
    elif answer.is_mock:
        citations = _classify_citations([
            Citation(domain=m[0].lower(), url=None)
            for m in dict.fromkeys(_DOMAIN_RE.findall(text))
        ], profile)
        # 去重 domain
        seen: set[str] = set()
        citations = [c for c in citations if not (c.domain in seen or seen.add(c.domain))]
    else:
        # 真实回答只计入 Web Search 实际返回的 URL，不把模型声明域名当作联网引用。
        citations = []

    sentiment = Sentiment.NEUTRAL
    evidence = ""
    if brand_first is not None:
        evidence = _evidence_sentence(text, brand_first)
        ctx = text.lower()
        pos_score = sum(cue in ctx for cue in _POSITIVE_CUES)
        neg_score = sum(cue in ctx for cue in _NEGATIVE_CUES)
        if pos_score > neg_score:
            sentiment = Sentiment.POSITIVE
        elif neg_score > pos_score:
            sentiment = Sentiment.NEGATIVE

    return AnswerAnalysis(
        question_id=answer.question_id,
        provider=answer.provider,
        model=answer.model,
        brand_mentioned=brand_first is not None,
        brand_recommended=_is_brand_recommended(text, brand_first),
        recommendation_assessed=True,
        brand_position=brand_position,
        competitors=competitors,
        citations=citations,
        sentiment=sentiment,
        evidence_quote=evidence,
    )


# ---------------------------------------------------------------- LLM 抽取

def _normalize_competitors(
    competitors: list[CompetitorMention],
    profile: BrandProfile,
) -> list[CompetitorMention]:
    """统一 LLM 输出的品牌大小写，去重并过滤渠道名称。"""

    canonical_names = list(profile.seed_competitors) + KNOWN_BRANDS
    canonical_by_key = {name.casefold(): name for name in canonical_names}
    retailer_keys = {name.casefold() for name in RETAILERS}
    seen: set[str] = set()
    normalized: list[CompetitorMention] = []

    for competitor in competitors:
        raw_name = competitor.name.strip()
        key = raw_name.casefold()
        if not raw_name or key in retailer_keys or key in seen:
            continue
        seen.add(key)
        normalized.append(
            CompetitorMention(
                name=canonical_by_key.get(key, raw_name),
                position=competitor.position,
            )
        )
    return normalized

_EXTRACT_PROMPT = """从下面这段"AI 对消费者问题的回答"中抽取结构化信息。目标品牌：{brand}（别名：{aliases}）。

回答原文：
---
{answer}
---

输出 JSON：
{{
  "brand_mentioned": true/false,
  "brand_recommended": true/false（只有把目标品牌作为建议、候选或首选时才为 true；仅客观列举/描述为 false）,
  "brand_position": 品牌在回答提及的所有品牌中的顺位(1-based)，未提及则 null,
  "competitors": [{{"name": "竞品品牌名", "position": 顺位}}]（只列产品品牌，不列零售商/电商平台）,
  "citations": [{{"domain": "域名", "url": "完整URL或null"}}],
  "sentiment": "pos|neu|neg"（回答对目标品牌的倾向，未提及为 neu）,
  "evidence_quote": "原文中最能证明上述判断的一句话"
}}"""


def llm_analyze(answer: AIAnswer, profile: BrandProfile, settings: Settings) -> AnswerAnalysis:
    from ..providers.base import ProviderError
    from ..providers.deepseek import DeepSeekClient

    data = DeepSeekClient(settings).chat_json(
        [{"role": "user", "content": _EXTRACT_PROMPT.format(
            brand=profile.brand_name,
            aliases="、".join(profile.brand_aliases),
            answer=answer.raw_text,
        )}]
    )
    try:
        result = AnswerAnalysis(
            question_id=answer.question_id,
            provider=answer.provider,
            model=answer.model,
            **data,
        )
        result.competitors = _normalize_competitors(result.competitors, profile)
        result.brand_recommended = bool(
            result.brand_mentioned and result.brand_recommended
        )
        result.recommendation_assessed = True
        if answer.search_grounded and answer.source_urls:
            result.citations = _citations_from_source_urls(answer.source_urls, profile)
        elif not answer.is_mock:
            result.citations = []
        else:
            result.citations = _classify_citations(result.citations, profile)
        return result
    except Exception as e:  # ValidationError 等
        raise ProviderError(f"抽取结果不符合契约: {e}")


def analyze_answers(
    answers: list[AIAnswer], profile: BrandProfile, settings: Settings
) -> list[AnswerAnalysis]:
    from ..providers.base import ProviderError

    results: list[AnswerAnalysis] = []
    for a in answers:
        if settings.deepseek_api_key and not settings.force_mock:
            try:
                results.append(llm_analyze(a, profile, settings))
                continue
            except ProviderError as e:
                print(f"[warn] {a.question_id} LLM 抽取失败，降级启发式: {e}")
                degraded = heuristic_analyze(a, profile)
                degraded.parse_degraded = True
                results.append(degraded)
                continue
        results.append(heuristic_analyze(a, profile))
    return results


# ---------------------------------------------------------------- 指标聚合

def _aggregate_segment(analyses: list[AnswerAnalysis]) -> VisibilitySegmentMetrics:
    n = len(analyses)
    if n == 0:
        return VisibilitySegmentMetrics()

    mentioned = [a for a in analyses if a.brand_mentioned]
    brand_mentions = len(mentioned)
    recommendation_assessed = [a for a in analyses if a.recommendation_assessed]

    # SOV：按"回答级提及"计数——每条回答里每个品牌至多记 1 次
    comp_counts: dict[str, int] = {}
    comp_positions: dict[str, list[int]] = {}
    for a in analyses:
        for c in a.competitors:
            comp_counts[c.name] = comp_counts.get(c.name, 0) + 1
            if c.position is not None:
                comp_positions.setdefault(c.name, []).append(c.position)
    total_mentions = brand_mentions + sum(comp_counts.values())

    positions = [a.brand_position for a in mentioned if a.brand_position is not None]
    sentiment_summary = {s.value: 0 for s in Sentiment}
    for a in analyses:
        sentiment_summary[a.sentiment.value] += 1
    source_type_summary = {source_type.value: 0 for source_type in SourceType}
    for analysis in analyses:
        for citation in analysis.citations:
            source_type_summary[citation.source_type.value] += 1

    competitor_ranking = sorted(
        (
            CompetitorRank(
                name=name,
                mention_count=cnt,
                avg_position=(
                    round(sum(comp_positions[name]) / len(comp_positions[name]), 2)
                    if comp_positions.get(name) else None
                ),
                sov=round(cnt / total_mentions, 4) if total_mentions else 0.0,
            )
            for name, cnt in comp_counts.items()
        ),
        key=lambda r: (-r.mention_count, r.avg_position or 99),
    )

    return VisibilitySegmentMetrics(
        visibility_rate=round(brand_mentions / n, 4),
        recommendation_rate=(
            round(sum(a.brand_recommended for a in analyses) / n, 4)
            if len(recommendation_assessed) == n else None
        ),
        sov=round(brand_mentions / total_mentions, 4) if total_mentions else 0.0,
        avg_position=round(sum(positions) / len(positions), 2) if positions else None,
        citation_rate=round(sum(1 for a in analyses if a.citations) / n, 4),
        sentiment_summary=sentiment_summary,
        competitor_ranking=competitor_ranking,
        source_type_summary=source_type_summary,
        questions_checked=n,
    )


def aggregate_metrics(
    analyses: list[AnswerAnalysis],
    questions: list[UserQuestion] | None = None,
    profile: BrandProfile | None = None,
) -> VisibilityMetrics:
    """保留全样本顶层指标，同时独立计算 branded / unbranded。

    ``questions``/``profile`` 可选是为了保持旧调用方兼容；正式管道始终传入。
    """

    overall = _aggregate_segment(analyses)
    branded_analyses: list[AnswerAnalysis] = []
    unbranded_analyses: list[AnswerAnalysis] = []

    if questions is not None and profile is not None:
        label_question_scopes(questions, profile)
        scope_by_id = {
            question.id: question.query_scope or classify_question_scope(question, profile)
            for question in questions
        }
        for item in analyses:
            scope = scope_by_id.get(item.question_id)
            if scope == QueryScope.BRANDED:
                branded_analyses.append(item)
            elif scope == QueryScope.UNBRANDED:
                unbranded_analyses.append(item)

    return VisibilityMetrics(
        **overall.model_dump(),
        branded=_aggregate_segment(branded_analyses),
        unbranded=_aggregate_segment(unbranded_analyses),
    )


def refresh_report_metrics(report: DiagnosticReport) -> DiagnosticReport:
    """为旧 SQLite/JSON 补算分层、推荐与来源类型，不调用 Provider。"""

    def enrich(
        analyses: list[AnswerAnalysis], answers: list[AIAnswer]
    ) -> None:
        answer_by_key = {
            (answer.provider, answer.question_id): answer for answer in answers
        }
        answer_by_question = {answer.question_id: answer for answer in answers}
        for item in analyses:
            item.citations = _classify_citations(item.citations, report.brand_profile)
            if item.recommendation_assessed:
                continue
            answer = answer_by_key.get(
                (item.provider, item.question_id)
            ) or answer_by_question.get(item.question_id)
            if answer is None:
                continue
            brand_hits = _find_brand_mentions(
                answer.raw_text,
                [report.brand_profile.brand_name, *report.brand_profile.brand_aliases],
            )
            brand_first = min(brand_hits.values()) if brand_hits else None
            item.brand_recommended = _is_brand_recommended(
                answer.raw_text, brand_first
            )
            item.recommendation_assessed = True

    label_question_scopes(report.questions, report.brand_profile)
    enrich(report.analyses, report.answers)
    if report.metrics is not None:
        report.metrics = aggregate_metrics(
            report.analyses, report.questions, report.brand_profile
        )
    for platform in report.platform_results:
        enrich(platform.analyses, platform.answers)
        platform.metrics = aggregate_metrics(
            platform.analyses, report.questions, report.brand_profile
        )
    return report
