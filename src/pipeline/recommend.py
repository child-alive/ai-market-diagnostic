"""⑥ 行动建议：由指标与缺口推导 P0/P1/P2 优先级清单。

每条建议 = 行动 + 理由（引用具体指标/缺口）+ 预期影响 + 工作量。
规则驱动，保证与报告中的数据自洽。
"""
from __future__ import annotations

from ..models import (
    ContentGap,
    GapType,
    Priority,
    Effort,
    Recommendation,
    SiteAuditResult,
    VisibilityMetrics,
)


def make_recommendations(
    metrics: VisibilityMetrics | None,
    gaps: list[ContentGap],
    site_audit: SiteAuditResult | None,
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    page_gaps = [g for g in gaps if g.gap_type == GapType.PAGE]
    signal_gaps = [g for g in gaps if g.gap_type == GapType.SIGNAL]

    # P0 — 技术信号问题最先修（成本低、影响抓取的地基）
    if signal_gaps:
        codes = "、".join(g.title.replace("站点信号缺失: ", "") for g in signal_gaps[:4])
        recs.append(Recommendation(
            priority=Priority.P0,
            action=f"修复官网技术信号: {codes}",
            reason="站点诊断发现影响搜索引擎与 AI 抓取/理解的基础问题，内容投入前必须先修地基",
            expected_impact="提升官网可抓取性与可引用性，是后续所有内容被 AI 收录的前提",
            effort=Effort.S,
        ))

    # P0 — 高购买意图页面缺口
    for g in page_gaps:
        if "哪里购买" in g.title:
            recs.append(Recommendation(
                priority=Priority.P0,
                action="上线 es-MX「Dónde comprar Deli」渠道页，列出墨西哥可购渠道（Mercado Libre/Amazon MX/线下经销商）并添加结构化数据",
                reason=f"缺口证据: {len(g.evidence)} 条 BOFU 购买类问题的 AI 回答完全由零售商与竞品承接",
                expected_impact="直接承接购买意图最强的 AI 流量，把'被提到'变成'可转化'",
                effort=Effort.S,
            ))

    # P0/P1 — 品类内容集群
    if metrics and metrics.visibility_rate < 0.5:
        recs.append(Recommendation(
            priority=Priority.P0,
            action="建立 es-MX 品类内容集群：针对未命中的榜单/对比类问题逐条产出「真实问题→直接答案」式页面（FAQ、对比页、场景页）",
            reason=f"AI 可见度仅 {metrics.visibility_rate:.0%}（{metrics.questions_checked} 条高价值问题中），品类榜单问题几乎全部旁落竞品",
            expected_impact="进入 AI 品类推荐答案位，可见度目标 3 个月内提升至 50%+",
            effort=Effort.M,
        ))

    for g in page_gaps:
        if "对比/榜单" in g.title:
            recs.append(Recommendation(
                priority=Priority.P1,
                action=f"产出西语对比评测内容（{g.title.split('（')[-1].rstrip('）')}），投放到官网博客与高权重第三方渠道",
                reason=f"MOFU 对比类问题未命中 {len(g.related_questions)} 条，用户比较阶段品牌不在候选集",
                expected_impact="在用户'比较阶段'进入 AI 候选集，挤占竞品答案位",
                effort=Effort.M,
            ))

    # P1 — 话语权 / 引用源建设
    if metrics and metrics.sov < 0.15:
        top_comp = metrics.competitor_ranking[0].name if metrics.competitor_ranking else "头部竞品"
        recs.append(Recommendation(
            priority=Priority.P1,
            action="权威引用源建设：争取墨西哥本地媒体测评、Profeco 类比价内容收录、行业目录与高权重导购站露出",
            reason=f"话语权 SOV 仅 {metrics.sov:.1%}（{top_comp} 领先），且 AI 引用源集中于电商与零售站，品牌缺少可信第三方背书",
            expected_impact="提升 Citation Rate 与 SOV，让 AI'敢引用'品牌信息",
            effort=Effort.L,
        ))

    # P1 — 排名靠后
    if metrics and metrics.avg_position is not None and metrics.avg_position >= 3:
        recs.append(Recommendation(
            priority=Priority.P1,
            action="针对已命中问题优化答案位排名：补充产品参数/价格/评价等结构化信息，强化「性价比首选」定位话术",
            reason=f"品牌平均排名第 {metrics.avg_position:.1f} 位，被提及但处于答案尾部，用户记忆度低",
            expected_impact="平均排名进入前 3，显著提升 AI 推荐转化",
            effort=Effort.M,
        ))

    # P2 — 口碑与持续监测
    if metrics and metrics.sentiment_summary.get("neg", 0) > 0:
        recs.append(Recommendation(
            priority=Priority.P2,
            action="口碑管理：针对负面语境（质量疑虑/售后缺失）产出官方回应内容与保修政策页",
            reason=f"检测到 {metrics.sentiment_summary['neg']} 条负面倾向回答",
            expected_impact="扭转 AI 回答中的负面框架",
            effort=Effort.S,
        ))
    recs.append(Recommendation(
        priority=Priority.P2,
        action="建立周期性 AI 可见度监测：扩大问题样本至 100+，多平台多轮采样取均值",
        reason="单次 8~10 问采样仅为演示规模，AI 回答存在随机性，结论需多轮验证",
        expected_impact="形成可跟踪的 GEO 指标基线，验证上述动作的实际效果",
        effort=Effort.M,
    ))

    order = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2}
    return sorted(recs, key=lambda r: order[r.priority])
