"""⑤ Query Fanout：高价值无品牌词派生、抽样检测与覆盖率。

真实模式只用 DeepSeek 生成分支并获取 Web Search 回答；Mock 模式使用确定性
派生与 MockProvider，保证离线验收。派生问题经过品牌名/别名泄漏硬校验。
"""
from __future__ import annotations

from collections import Counter

from ..config import Settings
from ..models import (
    AIAnswer,
    AnswerAnalysis,
    BrandProfile,
    FanoutMetrics,
    FanoutQuery,
    FanoutType,
    QueryScope,
    UserQuestion,
)
from ..providers.base import AnswerProvider, ProviderError
from .analysis import heuristic_analyze
from .segmentation import _contains_term, label_question_scopes

DEFAULT_PARENTS = 2
DEFAULT_BRANCHES = 3

_FANOUT_PROMPT = """你是一名 GEO Query Fanout 设计师。根据下面的高价值无品牌词问题，为每个父问题派生恰好 {branches} 个西班牙语（墨西哥）子问法。

父问题：
{parents}

规则：
1. 每个父问题至少覆盖 paraphrase（同义改写）、scenario（场景细化）、follow_up（追问式）三类；
2. 子问法保持原始商业意图，但措辞/条件/追问角度必须有实质差异；
3. 所有西语与中文文本都严禁出现目标品牌及别名：{brand_terms}；
4. 不要在问题中提示、暗示或优待任何具体品牌；
5. 只输出 JSON：
{{"fanouts":[{{"parent_question_id":"q05","text_local":"...","text_zh":"...","fanout_type":"paraphrase|scenario|follow_up"}}]}}
"""


def select_parent_questions(
    questions: list[UserQuestion],
    profile: BrandProfile,
    max_parents: int = DEFAULT_PARENTS,
) -> list[UserQuestion]:
    label_question_scopes(questions, profile)
    unbranded = [
        question for question in questions
        if question.query_scope == QueryScope.UNBRANDED
    ]
    return sorted(unbranded, key=lambda question: -question.value_score)[:max_parents]


def _deterministic_fanouts(
    parents: list[UserQuestion], branches_per_parent: int
) -> list[FanoutQuery]:
    templates = [
        (
            FanoutType.PARAPHRASE,
            "Si tuvieras que hacer una lista corta, responde esta pregunta: {local}",
            "如果只列一个精简榜单，请回答：{zh}",
        ),
        (
            FanoutType.SCENARIO,
            "Para una compra real con presupuesto medio en México: {local}",
            "面向墨西哥中等预算的真实采购场景：{zh}",
        ),
        (
            FanoutType.FOLLOW_UP,
            "Después de comparar opciones, ¿qué criterios y alternativas aclaran esta pregunta: «{local}»?",
            "比较候选项后，哪些标准和替代方案能进一步回答：{zh}",
        ),
        (
            FanoutType.SCENARIO,
            "Para una compra por volumen, responde con opciones disponibles en México: {local}",
            "针对批量采购，请结合墨西哥可买到的选项回答：{zh}",
        ),
        (
            FanoutType.FOLLOW_UP,
            "¿Qué cambia si se priorizan disponibilidad, precio y durabilidad al responder: «{local}»?",
            "如果优先考虑可得性、价格和耐用性，这个问题的答案会如何变化：{zh}",
        ),
    ]
    fanouts: list[FanoutQuery] = []
    for parent in parents:
        for index, (fanout_type, local, zh) in enumerate(
            templates[:branches_per_parent], start=1
        ):
            fanouts.append(FanoutQuery(
                id=f"fo-{parent.id}-{index}",
                parent_question_id=parent.id,
                text_local=local.format(local=parent.text_local, zh=parent.text_zh),
                text_zh=zh.format(local=parent.text_local, zh=parent.text_zh),
                fanout_type=fanout_type,
                is_mock=True,
            ))
    return fanouts


def _contains_brand(text: str, profile: BrandProfile) -> bool:
    return any(
        _contains_term(text, term)
        for term in [profile.brand_name, *profile.brand_aliases]
    )


def validate_fanout_queries(
    raw_items: list[dict],
    parents: list[UserQuestion],
    profile: BrandProfile,
    branches_per_parent: int,
) -> list[FanoutQuery]:
    parent_ids = {parent.id for parent in parents}
    counts: Counter[str] = Counter()
    types_by_parent: dict[str, set[FanoutType]] = {}
    texts_by_parent: dict[str, set[str]] = {}
    results: list[FanoutQuery] = []
    for raw in raw_items:
        parent_id = str(raw.get("parent_question_id", "")).strip()
        if parent_id not in parent_ids:
            raise ValueError(f"Fanout 引用了未知父问题: {parent_id or '<empty>'}")
        counts[parent_id] += 1
        item = FanoutQuery(
            id=f"fo-{parent_id}-{counts[parent_id]}",
            parent_question_id=parent_id,
            text_local=str(raw.get("text_local", "")).strip(),
            text_zh=str(raw.get("text_zh", "")).strip(),
            fanout_type=raw.get("fanout_type"),
            is_mock=False,
        )
        if not item.text_local or not item.text_zh:
            raise ValueError(f"{item.id} 缺少西语或中文文本")
        if _contains_brand(f"{item.text_local}\n{item.text_zh}", profile):
            raise ValueError(f"{item.id} 泄漏目标品牌名/别名")
        normalized = item.text_local.casefold()
        if normalized in texts_by_parent.setdefault(parent_id, set()):
            raise ValueError(f"{item.id} 与同父问题的分支重复")
        texts_by_parent[parent_id].add(normalized)
        types_by_parent.setdefault(parent_id, set()).add(item.fanout_type)
        results.append(item)

    required_types = {
        FanoutType.PARAPHRASE,
        FanoutType.SCENARIO,
        FanoutType.FOLLOW_UP,
    }
    for parent_id in parent_ids:
        if counts[parent_id] != branches_per_parent:
            raise ValueError(
                f"{parent_id} Fanout 数量应为 {branches_per_parent}，实际 {counts[parent_id]}"
            )
        if not required_types.issubset(types_by_parent.get(parent_id, set())):
            raise ValueError(f"{parent_id} 未覆盖三种 Fanout 类型")
    return results


def generate_fanout_queries(
    parents: list[UserQuestion],
    profile: BrandProfile,
    settings: Settings,
    branches_per_parent: int = DEFAULT_BRANCHES,
) -> list[FanoutQuery]:
    if settings.force_mock or not settings.deepseek_api_key:
        return _deterministic_fanouts(parents, branches_per_parent)

    from ..providers.deepseek import DeepSeekClient

    parent_lines = "\n".join(
        f"- {parent.id}: {parent.text_local}（{parent.text_zh}）"
        for parent in parents
    )
    prompt = _FANOUT_PROMPT.format(
        branches=branches_per_parent,
        parents=parent_lines,
        brand_terms="、".join([profile.brand_name, *profile.brand_aliases]),
    )
    try:
        data = DeepSeekClient(settings).chat_json(
            [{"role": "user", "content": prompt}], temperature=0.6
        )
        return validate_fanout_queries(
            data["fanouts"], parents, profile, branches_per_parent
        )
    except (ProviderError, KeyError, TypeError, ValueError) as exc:
        print(f"[warn] Query Fanout 生成失败，使用确定性派生并标记 Mock: {exc}")
        return _deterministic_fanouts(parents, branches_per_parent)


def build_fanout_metrics(
    queries: list[FanoutQuery],
    answers: list[AIAnswer],
    analyses: list[AnswerAnalysis],
) -> FanoutMetrics:
    checked = len(analyses)
    if not queries:
        return FanoutMetrics()
    analysis_by_id = {analysis.question_id: analysis for analysis in analyses}
    parent_ids = {query.parent_question_id for query in queries}
    parents_hit = {
        query.parent_question_id
        for query in queries
        if analysis_by_id.get(query.id) is not None
        and analysis_by_id[query.id].brand_mentioned
    }
    mention_hits = sum(analysis.brand_mentioned for analysis in analyses)
    recommendation_hits = sum(analysis.brand_recommended for analysis in analyses)
    return FanoutMetrics(
        parents_selected=len(parent_ids),
        queries_generated=len(queries),
        queries_checked=checked,
        mention_hits=mention_hits,
        recommendation_hits=recommendation_hits,
        mention_coverage=round(mention_hits / checked, 4) if checked else 0.0,
        recommendation_coverage=(
            round(recommendation_hits / checked, 4) if checked else 0.0
        ),
        parent_fanout_coverage=round(len(parents_hit) / len(parent_ids), 4),
        grounded_rate=(
            round(sum(answer.search_grounded for answer in answers) / len(answers), 4)
            if answers else 0.0
        ),
    )


def run_query_fanout(
    questions: list[UserQuestion],
    profile: BrandProfile,
    settings: Settings,
    provider: AnswerProvider,
    max_parents: int = DEFAULT_PARENTS,
    branches_per_parent: int = DEFAULT_BRANCHES,
) -> tuple[list[FanoutQuery], list[AIAnswer], list[AnswerAnalysis], FanoutMetrics]:
    parents = select_parent_questions(questions, profile, max_parents)
    fanout_queries = generate_fanout_queries(
        parents, profile, settings, branches_per_parent
    )
    parent_by_id = {parent.id: parent for parent in parents}
    answers: list[AIAnswer] = []
    for query in fanout_queries:
        parent = parent_by_id[query.parent_question_id]
        as_question = UserQuestion(
            id=query.id,
            text_local=query.text_local,
            text_zh=query.text_zh,
            tier=parent.tier,
            funnel=parent.funnel,
            value_score=parent.value_score,
            value_reason=f"Query Fanout · {query.fanout_type.value}",
            query_scope=QueryScope.UNBRANDED,
        )
        try:
            answers.append(provider.get_answer(as_question))
        except ProviderError as exc:
            print(f"[warn] {query.id} Fanout 检测失败并跳过: {exc}")
    analyses = [heuristic_analyze(answer, profile) for answer in answers]
    metrics = build_fanout_metrics(fanout_queries, answers, analyses)
    return fanout_queries, answers, analyses, metrics
