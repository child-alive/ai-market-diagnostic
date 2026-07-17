<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Perspective, Report } from './types'

const TechnicalPanel = defineAsyncComponent(() => import('./components/TechnicalPanel.vue'))
const LivePanel = defineAsyncComponent(() => import('./components/LivePanel.vue'))

const report = ref<Report | null>(null)
const loadError = ref('')
const perspective = ref<Perspective>('product')
const activeStage = ref(0)
const isPlaying = ref(true)
const showLive = ref(false)
let replayTimer: number | undefined

const stages = [
  { no: '01', label: '问题生成', en: 'Prompt discovery', short: '22 个需求问题' },
  { no: '02', label: '联网问询', en: 'AI retrieval', short: '8 个真实回答' },
  { no: '03', label: '回答分析', en: 'Signal extraction', short: '提及 ≠ 推荐' },
  { no: '04', label: '官网诊断', en: 'Site audit', short: '15 页实抓' },
  { no: '05', label: '问题分支', en: 'Query Fanout', short: '6 个派生问法' },
  { no: '06', label: '缺口定位', en: 'Gap analysis', short: '证据驱动' },
  { no: '07', label: '行动优先级', en: 'Recommendations', short: 'P0 → P2' },
]

const progress = computed(() => ((activeStage.value + 1) / stages.length) * 100)
const mainSourceCount = computed(() =>
  report.value?.answers.reduce((sum, answer) => sum + answer.source_urls.length, 0) ?? 0,
)
const fanoutSourceCount = computed(() =>
  report.value?.fanout_answers.reduce((sum, answer) => sum + answer.source_urls.length, 0) ?? 0,
)
const analysisById = computed(() =>
  new Map(report.value?.analyses.map((item) => [item.question_id, item]) ?? []),
)
const questionById = computed(() =>
  new Map(report.value?.questions.map((item) => [item.id, item]) ?? []),
)
const stagePayload = computed(() => {
  if (!report.value) return {}
  const payloads = [
    report.value.questions,
    report.value.answers,
    { metrics: report.value.metrics, analyses: report.value.analyses },
    report.value.site_audit,
    {
      queries: report.value.fanout_queries,
      metrics: report.value.fanout_metrics,
    },
    report.value.gaps,
    report.value.recommendations,
  ]
  return payloads[activeStage.value]
})
const stageCommand = computed(() => [
  '.venv/bin/python -m src.main --query-fanout',
  'DeepSeekProvider.get_answer(question)  # server-side Web Search',
  'analysis.aggregate_metrics(...)  # branded / unbranded 分层',
  'site_audit.audit_site(profile, settings)  # ≤15 pages, ≤1 req/s',
  'query_fanout.run_query_fanout(..., max_parents=2, branches_per_parent=3)',
  'gaps.find_gaps(questions, analyses, audit)',
  'recommend.make_recommendations(metrics, gap_list, audit)',
][activeStage.value])

function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

function concise(text: string, max = 220): string {
  const cleaned = text.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim()
  return cleaned.length > max ? `${cleaned.slice(0, max)}…` : cleaned
}

function restartReplay(): void {
  activeStage.value = 0
  isPlaying.value = true
}

function nextStage(): void {
  activeStage.value = (activeStage.value + 1) % stages.length
}

function startReplayTimer(): void {
  if (replayTimer) window.clearInterval(replayTimer)
  if (!isPlaying.value || !report.value || showLive.value) return
  replayTimer = window.setInterval(nextStage, 3200)
}

watch([isPlaying, report, showLive], startReplayTimer)

function selectStage(index: number): void {
  activeStage.value = index
  isPlaying.value = false
}

async function loadReport(): Promise<void> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}demo-report.json`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    report.value = await response.json() as Report
  } catch (error) {
    loadError.value = `回放数据加载失败：${error instanceof Error ? error.message : '未知错误'}`
  }
}

onMounted(loadReport)
onUnmounted(() => {
  if (replayTimer) window.clearInterval(replayTimer)
})
</script>

<template>
  <main class="site-shell">
    <header class="topbar">
      <a class="brand-lockup" href="#top" aria-label="返回首页">
        <span class="brand-mark">J</span>
        <span><b>聚路 GEO Lab</b><small>AI Market Diagnostic</small></span>
      </a>
      <div class="top-actions">
        <span v-if="report" class="run-pill"><i></i> REAL RUN {{ report.meta.run_id }}</span>
        <div class="segmented" aria-label="视角切换">
          <button :class="{ active: perspective === 'product' }" @click="perspective = 'product'">产品视角</button>
          <button :class="{ active: perspective === 'technical' }" @click="perspective = 'technical'">技术视角</button>
        </div>
      </div>
    </header>

    <div v-if="loadError" class="fatal-state">
      <span>DATA LOAD ERROR</span>
      <h1>回放数据没有加载成功</h1>
      <p>{{ loadError }}</p>
    </div>

    <template v-else-if="report">
      <section id="top" class="hero">
        <div class="hero-copy">
          <div class="eyebrow"><span>DELI × MÉXICO</span><b>es-MX</b></div>
          <h1>AI 认识 Deli，<br><em>但不会主动推荐它。</em></h1>
          <p class="hero-lead">
            在 {{ report.metrics.unbranded.questions_checked }} 个高价值无品牌词问题和
            {{ report.fanout_metrics.queries_checked }} 个派生分支中，Deli 的提及与推荐均为 0。
            品牌认知存在，通用需求的叙事入口与官网承接却同时断层。
          </p>
          <div class="hero-actions">
            <button class="primary-button" @click="showLive = false; restartReplay()">
              <span>▶</span> 重播真实诊断
            </button>
            <a class="text-button" href="./full-report.html" target="_blank" rel="noopener">打开完整报告 ↗</a>
          </div>
          <p class="scope-note">单平台单轮采样（无品牌词 {{ report.metrics.unbranded.questions_checked }} 题 + 分支 {{ report.fanout_metrics.queries_checked }} 题）· 观测值非定论 · 不等同于 ChatGPT / Gemini 市场表现</p>
        </div>

        <div class="signal-board" aria-label="核心诊断指标">
          <div class="board-head">
            <span>SIGNAL BOARD</span>
            <span>{{ report.meta.model }}</span>
          </div>
          <div class="core-signal">
            <div class="signal-ring"><strong>{{ percent(report.metrics.unbranded.visibility_rate) }}</strong><span>UNBRANDED<br>MENTION</span></div>
            <div class="signal-copy"><b>通用需求里没有进入答案</b><small>{{ report.metrics.unbranded.questions_checked }}/{{ report.metrics.unbranded.questions_checked }} 个主问题未提及 · {{ report.fanout_metrics.queries_checked }}/{{ report.fanout_metrics.queries_checked }} 个分支未提及</small></div>
          </div>
          <div class="signal-grid">
            <article><span>品牌词认知</span><strong>{{ percent(report.metrics.branded.visibility_rate) }}</strong><small>AI 认识品牌</small></article>
            <article><span>无品牌词推荐</span><strong>{{ percent(report.metrics.unbranded.recommendation_rate) }}</strong><small>未进入推荐集</small></article>
            <article><span>来源覆盖率</span><strong>{{ percent(report.metrics.unbranded.citation_rate) }}</strong><small>带搜索来源的回答占比 · {{ mainSourceCount }} 个主来源</small></article>
            <article><span>官网承接</span><strong>0</strong><small>无品牌词官方来源</small></article>
          </div>
          <div class="board-foot"><span>OBSERVATION, NOT A FORECAST</span><span>{{ new Date(report.meta.generated_at).toLocaleDateString('zh-CN') }}</span></div>
        </div>
      </section>

      <section class="mode-deck" aria-label="演示模式">
        <div>
          <span class="section-index">DEMO MODE</span>
          <h2>一份数据，两种观看方式</h2>
          <p>回放不消耗 API；实况只在明确启动后调用服务端 DeepSeek。</p>
        </div>
        <div class="mode-switch">
          <button :class="{ active: !showLive }" @click="showLive = false">
            <span>01</span><b>回放模式</b><small>默认 · 零成本 · 永不翻车</small>
          </button>
          <button :class="{ active: showLive }" @click="showLive = true; isPlaying = false">
            <span>02</span><b>实况模式</b><small>技术评审 · 3 次联网问询</small>
          </button>
        </div>
      </section>

      <section v-if="!showLive" class="replay-section">
        <div class="pipeline" aria-label="诊断管道">
          <button
            v-for="(stage, index) in stages"
            :key="stage.no"
            :class="{ active: index === activeStage, done: index < activeStage }"
            @click="selectStage(index)"
          >
            <span>{{ stage.no }}</span><b>{{ stage.label }}</b><small>{{ stage.en }}</small>
          </button>
          <div class="pipeline-progress" :style="{ width: `${progress}%` }"></div>
        </div>

        <div class="replay-toolbar">
          <div><span class="live-dot"></span> REAL DATA REPLAY <b>{{ activeStage + 1 }}/{{ stages.length }}</b></div>
          <div>
            <button @click="restartReplay">↺ 重置</button>
            <button @click="isPlaying = !isPlaying">{{ isPlaying ? 'Ⅱ 暂停' : '▶ 继续' }}</button>
            <button @click="nextStage">下一步 →</button>
          </div>
        </div>

        <div class="stage-layout" aria-live="polite">
          <aside class="stage-context">
            <span class="giant-number">{{ stages[activeStage].no }}</span>
            <p>{{ stages[activeStage].en }}</p>
            <h2>{{ stages[activeStage].label }}</h2>
            <strong>{{ stages[activeStage].short }}</strong>
            <div class="stage-trace">
              <span>INPUT</span><i></i><span>PROCESS</span><i></i><span>OUTPUT</span>
            </div>
          </aside>

          <div v-if="perspective === 'product'" class="stage-output product-output">
            <template v-if="activeStage === 0">
              <div class="output-head"><span>PROMPT SET</span><b>{{ report.questions.length }} QUESTIONS</b></div>
              <div class="question-stream">
                <article v-for="question in report.questions.slice(0, 6)" :key="question.id">
                  <span>{{ question.id }} · {{ question.funnel }}</span>
                  <p>{{ question.text_local }}</p>
                  <small>{{ question.text_zh }}</small>
                  <b :class="question.query_scope">{{ question.query_scope === 'branded' ? '品牌词' : '无品牌词' }}</b>
                </article>
              </div>
              <p class="output-insight">先把品牌词与无品牌词分开：前者测认知，后者才测主动推荐竞争力。</p>
            </template>

            <template v-else-if="activeStage === 1">
              <div class="output-head"><span>DEEPSEEK WEB SEARCH</span><b>{{ report.answers.filter(a => a.search_grounded).length }}/{{ report.answers.length }} GROUNDED</b></div>
              <div class="answer-stack">
                <article v-for="answer in report.answers.slice(0, 3)" :key="answer.question_id">
                  <header><b>{{ answer.question_id }}</b><span>WEB · {{ answer.source_urls.length }} SOURCES</span></header>
                  <p>{{ concise(answer.raw_text) }}</p>
                  <small>{{ questionById.get(answer.question_id)?.text_local }}</small>
                </article>
              </div>
              <p class="output-insight">搜索来源由平台 API 返回；有 URL 不等于每句话已经人工核验。</p>
            </template>

            <template v-else-if="activeStage === 2">
              <div class="output-head"><span>MEASUREMENT LAYER</span><b>BRANDED ≠ UNBRANDED</b></div>
              <div class="comparison-panel">
                <div><span>品牌词 / Branded</span><strong>{{ percent(report.metrics.branded.visibility_rate) }}</strong><p>AI 认识 Deli</p></div>
                <i>≠</i>
                <div class="danger"><span>无品牌词 / Unbranded</span><strong>{{ percent(report.metrics.unbranded.visibility_rate) }}</strong><p>AI 不会主动带出 Deli</p></div>
              </div>
              <div class="mini-metrics">
                <span>推荐率 <b>{{ percent(report.metrics.unbranded.recommendation_rate) }}</b></span>
                <span>SOV <b>{{ percent(report.metrics.unbranded.sov) }}</b></span>
                <span>来源覆盖率 <b>{{ percent(report.metrics.unbranded.citation_rate) }}</b></span>
              </div>
              <p class="output-insight">若把两类问题混算，整体 37.5% 会制造品牌已经有竞争力的错觉。</p>
            </template>

            <template v-else-if="activeStage === 3">
              <div class="output-head"><span>DELITWORLD.COM</span><b>{{ report.site_audit.pages_checked }} PAGES · LIVE CRAWL</b></div>
              <div class="audit-grid">
                <article class="pass"><span>原始 HTML</span><strong>{{ report.site_audit.raw_html_text_chars.toLocaleString() }}</strong><small>字符可提取</small></article>
                <article class="fail"><span>es-MX hreflang</span><strong>NOT FOUND</strong><small>抓取范围内</small></article>
                <article class="fail"><span>西语内容</span><strong>NOT FOUND</strong><small>抓取范围内</small></article>
                <article class="warn"><span>llms.txt</span><strong>NOT FOUND</strong><small>非强制标准</small></article>
              </div>
              <p class="output-insight">网站能被读取，不代表它能承接墨西哥用户：机器可见，市场内容却缺席。</p>
            </template>

            <template v-else-if="activeStage === 4">
              <div class="output-head"><span>QUERY FANOUT</span><b>{{ report.fanout_metrics.queries_checked }}/{{ report.fanout_metrics.queries_generated }} GROUNDED · {{ fanoutSourceCount }} SOURCES</b></div>
              <div class="fanout-tree">
                <article v-for="query in report.fanout_queries" :key="query.id">
                  <span>{{ query.parent_question_id }} → {{ query.fanout_type }}</span>
                  <p>{{ query.text_local }}</p>
                  <b>未提及 Deli</b>
                </article>
              </div>
              <p class="output-insight">6 个分支无品牌泄漏，提及/推荐仍为 0%；这是同平台小样本扩展，不是独立统计验证。</p>
            </template>

            <template v-else-if="activeStage === 5">
              <div class="output-head"><span>EVIDENCE → GAP</span><b>{{ report.gaps.length }} GAPS</b></div>
              <div class="gap-list">
                <article v-for="gap in report.gaps" :key="gap.title">
                  <span :class="gap.severity">{{ gap.severity }}</span>
                  <div><h3>{{ gap.title }}</h3><p>{{ gap.evidence[0] }}</p></div>
                </article>
              </div>
            </template>

            <template v-else>
              <div class="output-head"><span>ACTION PLAN</span><b>{{ report.recommendations.length }} RECOMMENDATIONS</b></div>
              <div class="recommendation-list">
                <article v-for="item in report.recommendations" :key="item.action">
                  <span :class="item.priority">{{ item.priority }}</span>
                  <div><h3>{{ item.action }}</h3><p>{{ item.reason }}</p></div>
                  <b>{{ item.effort }}</b>
                </article>
              </div>
            </template>
          </div>

          <Suspense v-else>
            <TechnicalPanel
              :report="report"
              :active-stage="activeStage"
              :command="stageCommand"
              :payload="stagePayload"
            />
            <template #fallback><div class="stage-output panel-loader">正在加载技术视角…</div></template>
          </Suspense>
        </div>
      </section>

      <Suspense v-else>
        <LivePanel api-base="/api" @exit="showLive = false; restartReplay()" />
        <template #fallback><section class="lazy-panel-skeleton">正在加载实况模块…</section></template>
      </Suspense>

      <section class="method-strip">
        <div><span class="section-index">MEASUREMENT HONESTY</span><h2>这不是一张“看起来很高”的分数表。</h2></div>
        <div class="method-points">
          <article><b>01</b><h3>品牌词不混算</h3><p>“Deli 怎么样”里的品牌提及不算主动推荐竞争力。</p></article>
          <article><b>02</b><h3>来源不等于证据</h3><p>70 个 URL 证明联网检索发生，不证明每句话已人工核验。</p></article>
          <article><b>03</b><h3>单轮不冒充趋势</h3><p>真实重复采样已观察到 0%~33.3% 波动，正式测量需要更大样本。</p></article>
        </div>
      </section>

      <footer>
        <div class="brand-lockup"><span class="brand-mark">J</span><span><b>聚路 GEO Lab</b><small>Prototype delivery · 2026</small></span></div>
        <p>真实数据：DeepSeek run {{ report.meta.run_id }} · 主回答 {{ report.answers.length }} · 主来源 {{ mainSourceCount }} · Fanout 来源 {{ fanoutSourceCount }}</p>
        <a href="./full-report.html" target="_blank" rel="noopener">完整诊断报告 ↗</a>
      </footer>
    </template>

    <section v-else class="app-skeleton" aria-label="诊断报告加载中" aria-busy="true">
      <div class="skeleton-copy">
        <i></i><i></i><i></i><i></i>
      </div>
      <div class="skeleton-board">
        <i></i><i></i><div><i></i><i></i><i></i><i></i></div>
      </div>
      <span class="sr-only">正在加载真实诊断数据</span>
    </section>
  </main>
</template>
