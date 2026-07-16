"""⑤ 内容缺口分析：综合问题、可见度分析与站点诊断，输出带证据链的缺口清单。

规则驱动（确定性、可解释）：
1. 未命中问题按三层分类聚合 → 主题缺口；
2. BOFU 渠道类未命中 → "哪里购买"页面缺口；
3. MOFU 品类对比未命中 → 对比/榜单内容缺口；
4. 命中但排名靠后 → 排名劣势主题缺口；
5. site_audit 的 high/medium 问题 → 技术信号缺口（Stage 2 接入证据）。
"""
from __future__ import annotations

from ..models import (
    AnswerAnalysis,
    ContentGap,
    Funnel,
    GapType,
    IssueSeverity,
    QuestionTier,
    SiteAuditResult,
    UserQuestion,
)

_TIER_GAP_TITLES = {
    QuestionTier.CATEGORY: "全国品类榜单类问题中品牌完全缺席",
    QuestionTier.REGIONAL: "地区/渠道类问题中品牌完全缺席",
    QuestionTier.BRAND: "品牌词问题下 AI 无法给出品牌有效信息",
}


def _evidence_line(q: UserQuestion, a: AnswerAnalysis) -> str:
    comps = ", ".join(c.name for c in a.competitors[:5])
    hit = f"AI 回答提及竞品: {comps}" if comps else "AI 回答仅提及零售渠道"
    return f"「{q.text_local}」→ {hit}，未提及品牌"


def find_gaps(
    questions: list[UserQuestion],
    analyses: list[AnswerAnalysis],
    site_audit: SiteAuditResult | None,
) -> list[ContentGap]:
    qmap = {q.id: q for q in questions}
    gaps: list[ContentGap] = []

    checked = [a for a in analyses if a.question_id in qmap]
    missed = [a for a in checked if not a.brand_mentioned]

    # 1) 未命中问题按层聚合 → 主题缺口
    for tier, title in _TIER_GAP_TITLES.items():
        items = [a for a in missed if qmap[a.question_id].tier == tier]
        if items:
            gaps.append(ContentGap(
                gap_type=GapType.TOPIC,
                title=title,
                evidence=[_evidence_line(qmap[a.question_id], a) for a in items],
                related_questions=[a.question_id for a in items],
            ))

    # 2) BOFU 渠道类未命中 → 页面缺口
    bofu_missed = [a for a in missed if qmap[a.question_id].funnel == Funnel.BOFU]
    if bofu_missed:
        gaps.append(ContentGap(
            gap_type=GapType.PAGE,
            title="缺少 es-MX「哪里购买/授权经销商」落地页（Dónde comprar）",
            evidence=[_evidence_line(qmap[a.question_id], a) for a in bofu_missed]
                     + ["购买意图最强的问题被零售商与竞品承接，品牌无可被 AI 引用的渠道页"],
            related_questions=[a.question_id for a in bofu_missed],
        ))

    # 3) MOFU 品类对比未命中 → 对比/榜单内容缺口
    mofu_cat_missed = [
        a for a in missed
        if qmap[a.question_id].funnel == Funnel.MOFU
        and qmap[a.question_id].tier == QuestionTier.CATEGORY
    ]
    if mofu_cat_missed:
        top_comps: dict[str, int] = {}
        for a in mofu_cat_missed:
            for c in a.competitors:
                top_comps[c.name] = top_comps.get(c.name, 0) + 1
        comp_names = ", ".join(sorted(top_comps, key=top_comps.get, reverse=True)[:4])
        gaps.append(ContentGap(
            gap_type=GapType.PAGE,
            title="缺少西语品类对比/榜单型内容（vs " + (comp_names or "主要竞品") + "）",
            evidence=[_evidence_line(qmap[a.question_id], a) for a in mofu_cat_missed],
            related_questions=[a.question_id for a in mofu_cat_missed],
        ))

    # 4) 命中但排名靠后
    low_rank = [
        a for a in checked
        if a.brand_mentioned and a.brand_position is not None and a.brand_position >= 3
    ]
    if low_rank:
        avg = sum(a.brand_position for a in low_rank) / len(low_rank)
        gaps.append(ContentGap(
            gap_type=GapType.TOPIC,
            title=f"品牌被 AI 提及但排名靠后（这些回答中平均第 {avg:.1f} 位）",
            evidence=[
                f"「{qmap[a.question_id].text_local}」→ 品牌列于第 {a.brand_position} 位；"
                f"证据: {a.evidence_quote[:80]}" for a in low_rank
            ],
            related_questions=[a.question_id for a in low_rank],
        ))

    # 5) 站点技术信号缺口（Stage 2 起有真实 issues）
    if site_audit:
        for issue in site_audit.issues:
            if issue.severity in (IssueSeverity.HIGH, IssueSeverity.MEDIUM):
                gaps.append(ContentGap(
                    gap_type=GapType.SIGNAL,
                    title=f"站点信号缺失: {issue.code}",
                    evidence=[issue.detail],
                ))

    return gaps
