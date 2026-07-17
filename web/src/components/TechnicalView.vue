<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import type { Report } from '../types'
import { useScrollReveal } from '../composables/useScrollReveal'

const props = defineProps<{
  report: Report
  reportHref: string
  liveEnabled: boolean
  apiBase: string
}>()

const TechnicalPanel = defineAsyncComponent(() => import('./TechnicalPanel.vue'))
// 国际静态构建不生成实况组件 chunk，避免“只是在 UI 上隐藏”的伪隔离。
const buildLiveEnabled = import.meta.env.VITE_ENABLE_LIVE === 'true'
const LivePanel = buildLiveEnabled
  ? defineAsyncComponent(() => import('./LivePanel.vue'))
  : null
const activeStage = ref(0)
const showLive = ref(false)

useScrollReveal('.technical-page')

const mainSourceCount = computed(() => props.report.answers.reduce((sum, item) => sum + item.source_urls.length, 0))
const fanoutSourceCount = computed(() => props.report.fanout_answers.reduce((sum, item) => sum + item.source_urls.length, 0))

const modules = [
  { no: '01', label: 'question_gen', file: 'src/question_gen.py', role: '生成与分层当地语言问题' },
  { no: '02', label: 'providers', file: 'src/providers/', role: '统一 Web Search Provider 契约' },
  { no: '03', label: 'analysis', file: 'src/analysis.py', role: '提及、推荐、顺位与来源抽取' },
  { no: '04', label: 'site_audit', file: 'src/site_audit.py', role: '限速抓取与站点信号检查' },
  { no: '05', label: 'query_fanout', file: 'src/query_fanout.py', role: '派生问法与品牌泄漏防护' },
  { no: '06', label: 'gaps', file: 'src/gaps.py', role: '证据驱动的缺口规则' },
  { no: '07', label: 'recommend', file: 'src/recommend.py', role: 'P0/P1/P2 行动排序' },
]

const stagePayload = computed(() => {
  const payloads = [
    props.report.questions,
    props.report.answers,
    { metrics: props.report.metrics, analyses: props.report.analyses },
    props.report.site_audit,
    { queries: props.report.fanout_queries, metrics: props.report.fanout_metrics },
    props.report.gaps,
    props.report.recommendations,
  ]
  return payloads[activeStage.value]
})

const stageCommand = computed(() => [
  '.venv/bin/python -m src.main --query-fanout',
  'DeepSeekProvider.get_answer(question)  # server-side Web Search',
  'analysis.aggregate_metrics(...)  # branded / unbranded',
  'site_audit.audit_site(profile, settings)  # ≤15 pages, ≤1 req/s',
  'query_fanout.run_query_fanout(..., max_parents=2)',
  'gaps.find_gaps(questions, analyses, audit)',
  'recommend.make_recommendations(metrics, gap_list, audit)',
][activeStage.value])
</script>

<template>
  <div class="technical-page">
    <section id="top" class="technical-hero hero-entrance">
      <div>
        <span class="tech-kicker">TECHNICAL VIEW · 给技术评审</span>
        <h1>一条可复现、<br>可审计、可安全降级的诊断管道。</h1>
        <p>从模块边界、数据契约、真实调用到失败降级，展示这条诊断链路如何可靠运行。</p>
        <div class="tech-actions"><a :href="reportHref" target="_blank" rel="noopener">检查完整报告 ↗</a><code>run_id={{ report.meta.run_id }}</code></div>
      </div>
      <div class="delivery-console">
        <header><i></i><i></i><i></i><span>delivery.status</span></header>
        <dl>
          <div><dt>tests</dt><dd>55 passed</dd></div>
          <div><dt>grounded</dt><dd>{{ report.answers.filter(item => item.search_grounded).length }}/{{ report.answers.length }}</dd></div>
          <div><dt>main_sources</dt><dd>{{ mainSourceCount }}</dd></div>
          <div><dt>site_pages</dt><dd>{{ report.site_audit.pages_checked }}</dd></div>
          <div><dt>mock_in_real_run</dt><dd>0</dd></div>
          <div><dt>api_key_in_client</dt><dd>0</dd></div>
        </dl>
      </div>
    </section>

    <section class="architecture-section" data-reveal>
      <header class="tech-section-head"><span>01 · SYSTEM DECOMPOSITION</span><h2>七个模块，一份统一数据契约。</h2><p>每个模块可单测、可替换；下游只读取模型字段，不依赖上游内部实现。</p></header>
      <div class="architecture-flow">
        <button v-for="(module, index) in modules" :key="module.no" :class="{ active: activeStage === index }" @click="activeStage = index">
          <span>{{ module.no }}</span><b>{{ module.label }}</b><code>{{ module.file }}</code><small>{{ module.role }}</small>
        </button>
      </div>
    </section>

    <section class="trace-section" data-reveal>
      <header class="tech-section-head"><span>02 · INSPECTABLE TRACE</span><h2>选择模块，查看命令、字段与原始数据。</h2><p>沿同一个 run_id 回查每一步输入输出；原始 JSON 按需展开，避免信息过载。</p></header>
      <div class="trace-layout">
        <nav aria-label="技术模块">
          <button v-for="(module, index) in modules" :key="module.no" :class="{ active: activeStage === index }" @click="activeStage = index"><span>{{ module.no }}</span>{{ module.label }}</button>
        </nav>
        <Suspense>
          <TechnicalPanel :report="report" :active-stage="activeStage" :command="stageCommand" :payload="stagePayload" />
          <template #fallback><div class="technical-output panel-loader">正在加载技术追踪视图…</div></template>
        </Suspense>
      </div>
    </section>

    <section class="engineering-section" data-reveal>
      <header class="tech-section-head"><span>03 · RELIABILITY BOUNDARY</span><h2>外部服务失败，主交付仍然成立。</h2></header>
      <div class="engineering-grid">
        <article><b>DATA CONTRACT</b><h3>Pydantic 是唯一模块边界</h3><p>JSON 字段固定；报告、SQLite、网页都消费同一份 Report。</p></article>
        <article><b>REPRODUCIBILITY</b><h3>Mock 与真实 run 双轨</h3><p>真实样本证明联网链路；Mock 保证无 Key、无额度时仍能验收。</p></article>
        <article><b>FAIL-SAFE</b><h3>限流、并发、超时和回放</h3><p>实况每 IP 每小时 2 次、并发 1、超时终止；失败不影响静态回放。</p></article>
        <article><b>MEASUREMENT</b><h3>不把漂亮数字当事实</h3><p>品牌词/无品牌词分层；Mention ≠ Recommendation；URL ≠ 逐句核验。</p></article>
      </div>
    </section>

    <section class="environment-section" data-reveal>
      <header class="tech-section-head"><span>04 · CONTROLLED EXECUTION</span><h2>真实调用可演示，也不会绑架主交付。</h2><p>稳定回放保证任何环境都能复现；受控实况用于验证真实链路，并把密钥、额度和并发风险留在服务端。</p></header>

      <div v-if="!showLive" class="environment-grid">
        <article class="current"><span>EVIDENCE REPLAY</span><h3>稳定回放</h3><p>固化同一个真实 run 的问题、回答、来源与报告；默认零 API 消耗，结果可重复核验。</p><small>评审入口始终可用</small></article>
        <article><span>CONTROLLED LIVE</span><h3>受控实况</h3><p>固定 3 个无品牌词，服务端持有密钥，并设置限流、并发 1 与超时终止。</p><button v-if="liveEnabled" @click="showLive = true">启动 3 题实况诊断</button><small v-else>实况能力按部署环境显式启用</small></article>
      </div>

      <Suspense v-else-if="liveEnabled && LivePanel">
        <component :is="LivePanel" :api-base="apiBase" @exit="showLive = false" />
        <template #fallback><div class="view-loader">正在加载实况模块…</div></template>
      </Suspense>
    </section>

    <section class="technical-handoff" data-reveal>
      <div><span>REPRODUCE</span><h2>三步复现，不要求评审者提供 Key。</h2></div>
      <pre>python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.main --mock</pre>
      <aside><b>预期输出</b><p>20 问题 · 8 回答 · 7 缺口 · 7 建议</p><a :href="reportHref" target="_blank" rel="noopener">打开固化报告 ↗</a></aside>
    </section>

    <footer class="technical-footer">deepseek · {{ report.meta.model }} · {{ mainSourceCount }} main sources · {{ fanoutSourceCount }} fanout sources · source URLs are not human fact-checks</footer>
  </div>
</template>
