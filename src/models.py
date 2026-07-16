"""全链路 Pydantic 数据契约（PLAN.md §6）。

模块之间只允许通过本文件定义的模型传递数据。
字段可增不可随意改名；改名必须记录到 PROGRESS.md 决策记录。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- 枚举

class QuestionTier(str, Enum):
    """问题三层分类，对齐 GEO 行业术语：品牌词 / 地区排名词 / 品类(全国)排名词。"""

    BRAND = "brand"
    REGIONAL = "regional"
    CATEGORY = "category"


class QueryScope(str, Enum):
    """可见度测量口径：品牌词只测认知，无品牌词才测主动推荐竞争力。"""

    BRANDED = "branded"
    UNBRANDED = "unbranded"


class Funnel(str, Enum):
    TOFU = "TOFU"  # 认知
    MOFU = "MOFU"  # 比较
    BOFU = "BOFU"  # 决策


class Sentiment(str, Enum):
    POSITIVE = "pos"
    NEUTRAL = "neu"
    NEGATIVE = "neg"


class GapType(str, Enum):
    PAGE = "page"      # 缺少的页面类型
    TOPIC = "topic"    # 缺少的内容主题
    SIGNAL = "signal"  # 缺少的品牌/技术信号(hreflang, schema 等)


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class Effort(str, Enum):
    S = "S"
    M = "M"
    L = "L"


class RunMode(str, Enum):
    MOCK = "mock"
    REAL = "real"
    HYBRID = "hybrid"


class IssueSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    INACCESSIBLE = "inaccessible"
    UNMAPPED = "unmapped"
    CONTRADICTED = "contradicted"  # 预留给后续语义/人工核验


# ---------------------------------------------------------------- 输入

class BrandProfile(BaseModel):
    brand_name: str
    brand_aliases: list[str] = Field(default_factory=list)
    category: str
    market: str
    language: str
    website_url: str = ""
    seed_competitors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- ① 问题发现

class UserQuestion(BaseModel):
    id: str
    text_local: str                      # 目标市场语言原文
    text_zh: str                         # 中文对照
    tier: QuestionTier
    funnel: Funnel
    value_score: int = Field(ge=1, le=5)  # 商业价值评分
    value_reason: str
    # 旧 JSON 可依默认值加载；运行时由 tier + 品牌词命中确定。
    query_scope: Optional[QueryScope] = None


# ---------------------------------------------------------------- ② AI 回答采集

class SourceAnnotation(BaseModel):
    """平台原生的答案片段 → 来源 URL 映射。

    DeepSeek 当前仅返回搜索结果集合，因此该列表可为空；
    OpenAI Search / Gemini Grounding 可提供原生文本区间。
    """

    url: str
    title: str = ""
    start_index: Optional[int] = None
    end_index: Optional[int] = None
    cited_text: str = ""


class AIAnswer(BaseModel):
    question_id: str
    provider: str                        # deepseek / mock / ...
    model: str = ""                     # 该回答实际请求的模型
    raw_text: str
    retrieved_at: datetime
    is_mock: bool
    search_grounded: bool = False        # 是否由联网搜索结果支撑
    source_urls: list[str] = Field(default_factory=list)  # Web Search 返回的实际 URL
    source_annotations: list[SourceAnnotation] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- ③ 回答结构化分析

class CompetitorMention(BaseModel):
    name: str
    position: Optional[int] = None       # 在回答中的出现顺位(1-based)


class Citation(BaseModel):
    domain: str
    url: Optional[str] = None


class AnswerAnalysis(BaseModel):
    question_id: str
    provider: str = ""                  # 与 question_id 组成跨平台唯一标识
    model: str = ""
    brand_mentioned: bool
    brand_position: Optional[int] = None
    competitors: list[CompetitorMention] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    sentiment: Sentiment = Sentiment.NEUTRAL
    evidence_quote: str = ""             # 回答原文中的证据句
    parse_degraded: bool = False         # 结构化抽取失败降级标记


class CompetitorRank(BaseModel):
    name: str
    mention_count: int                   # 被提及的回答数
    avg_position: Optional[float] = None
    sov: float                           # 话语权占比 0~1


class VisibilitySegmentMetrics(BaseModel):
    """单一查询口径的指标切片；全字段默认保证旧报告可加载。"""

    visibility_rate: float = 0.0         # Visibility: 品牌出现的回答占比 0~1
    sov: float = 0.0                     # Share of Voice: 品牌提及/全部品牌提及 0~1
    avg_position: Optional[float] = None  # Average Position: 品牌平均顺位
    citation_rate: float = 0.0           # Citation Rate: 含搜索 URL/声明域名的回答占比 0~1
    sentiment_summary: dict[str, int] = Field(default_factory=dict)  # {pos: n, neu: n, neg: n}
    competitor_ranking: list[CompetitorRank] = Field(default_factory=list)
    questions_checked: int = 0


class VisibilityMetrics(VisibilitySegmentMetrics):
    """指标命名对齐聚路国际体系；顶层旧字段继续表示全样本。"""

    branded: VisibilitySegmentMetrics = Field(default_factory=VisibilitySegmentMetrics)
    unbranded: VisibilitySegmentMetrics = Field(default_factory=VisibilitySegmentMetrics)


class EvidenceReview(BaseModel):
    provider: str
    question_id: str
    claim: str
    source_url: str = ""
    source_title: str = ""
    evidence_quote: str = ""
    status: EvidenceStatus
    support_score: float = 0.0
    verification_method: str = "lexical_page_match"
    requires_human_review: bool = True
    error: str = ""


class EvidenceMetrics(BaseModel):
    total_claims: int = 0
    supported: int = 0
    partial: int = 0
    not_found: int = 0
    inaccessible: int = 0
    unmapped: int = 0
    contradicted: int = 0
    support_rate: float = 0.0


class PlatformResult(BaseModel):
    """单个 AI 平台的完整检测切片；顶层旧字段仍保留主平台结果。"""

    provider: str
    model: str = ""
    answers: list[AIAnswer] = Field(default_factory=list)
    analyses: list[AnswerAnalysis] = Field(default_factory=list)
    metrics: VisibilityMetrics
    evidence_reviews: list[EvidenceReview] = Field(default_factory=list)
    evidence_metrics: EvidenceMetrics = Field(default_factory=EvidenceMetrics)


# ---------------------------------------------------------------- ④ 网站诊断

class SiteIssue(BaseModel):
    severity: IssueSeverity
    code: str                            # 如 NO_HREFLANG_ES_MX / NO_SITEMAP
    detail: str


class SiteAuditResult(BaseModel):
    crawlable: bool = False
    robots_ok: bool = False
    sitemap_found: bool = False
    pages_checked: int = 0
    has_es_mx_hreflang: bool = False
    has_structured_data: bool = False
    spanish_content_found: bool = False
    issues: list[SiteIssue] = Field(default_factory=list)
    snapshot_mode: bool = False          # 网络失败降级为本地快照时为 True


# ---------------------------------------------------------------- ⑤⑥ 缺口与建议

class ContentGap(BaseModel):
    gap_type: GapType
    title: str
    evidence: list[str] = Field(default_factory=list)
    related_questions: list[str] = Field(default_factory=list)  # UserQuestion.id


class Recommendation(BaseModel):
    priority: Priority
    action: str
    reason: str
    expected_impact: str
    effort: Effort


# ---------------------------------------------------------------- ⑦ 汇总报告

class ReportMeta(BaseModel):
    generated_at: datetime
    mode: RunMode
    run_id: str = ""
    model: str = ""
    web_search_enabled: bool = False
    providers: list[str] = Field(default_factory=list)
    models: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class DiagnosticReport(BaseModel):
    brand_profile: BrandProfile
    questions: list[UserQuestion] = Field(default_factory=list)
    answers: list[AIAnswer] = Field(default_factory=list)
    analyses: list[AnswerAnalysis] = Field(default_factory=list)
    metrics: Optional[VisibilityMetrics] = None
    platform_results: list[PlatformResult] = Field(default_factory=list)
    site_audit: Optional[SiteAuditResult] = None
    gaps: list[ContentGap] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    meta: ReportMeta
