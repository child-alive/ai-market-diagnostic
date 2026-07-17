<script setup lang="ts">
import { computed, defineAsyncComponent, onUnmounted, ref, watch } from 'vue'
import type { Report } from '../types'
import { useScrollReveal } from '../composables/useScrollReveal'

const props = defineProps<{
  report: Report
  reportHref: string
  liveEnabled: boolean
  apiBase: string
}>()

const buildLiveEnabled = import.meta.env.VITE_ENABLE_LIVE === 'true'
const ProductLivePanel = buildLiveEnabled
  ? defineAsyncComponent(() => import('./LivePanel.vue'))
  : null

const journeySection = ref<HTMLElement | null>(null)
const activeStage = ref(0)
const isPlaying = ref(true)
const replaySpeed = ref<1 | 2>(1)
const replayRun = ref(0)
const activeAssessment = ref<number | null>(0)
let replayTimer: number | undefined

useScrollReveal('.product-page')

const mainSourceCount = computed(() => props.report.answers.reduce((sum, item) => sum + item.source_urls.length, 0))
const groundedCount = computed(() => props.report.answers.filter((item) => item.search_grounded).length)
const progressRatio = computed(() => activeStage.value / 6)

const assessmentItems = computed(() => [
  {
    title: '是否真正理解业务问题，而不是只堆砌技术名词',
    answer: '这个产品不是“统计品牌出现几次”，而是找出当地用户需求、AI 推荐与官网承接之间的断点。',
    evidence: [
      `品牌词可见度 ${percent(props.report.metrics.branded.visibility_rate)}，说明 AI 认识 Deli。`,
      `无品牌词提及与推荐均为 ${percent(props.report.metrics.unbranded.visibility_rate)}，说明 Deli 没进入通用需求答案。`,
      `官网实抓 ${props.report.site_audit.pages_checked} 页未发现西语内容，用户即使看到品牌也缺少本地化承接。`,
    ],
  },
  {
    title: '是否能把一个模糊需求拆成清晰的模块、数据和流程',
    answer: '把“诊断海外 AI 市场表现”拆成七步，每一步都有输入、输出和可回查证据。',
    evidence: ['问题生成 → 联网问询 → 回答分析 → 官网诊断 → 问题分支 → 缺口定位 → 行动建议。', '所有模块通过统一数据契约衔接，报告数字可追溯到问题、回答和来源。'],
  },
  {
    title: '是否能合理控制范围，并解释为什么先做这些',
    answer: '先完成一条 DeepSeek 真实联网闭环，再用离线模式保证任何评审环境都能复现；没有为了展示强行做登录或大规模爬虫。',
    evidence: ['真实主样本 8 条回答，8/8 带联网搜索来源。', '离线模式一条命令可运行；多平台代码存在，但未通过官方额度的部分不冒充已验收。'],
  },
  {
    title: '交付物是否清楚、可查看、可运行或可继续迭代',
    answer: '不需要先读代码：网页看结论、完整报告看证据、Mock 命令验收链路，三种入口各自独立。',
    evidence: ['网页提供真实数据回放与完整报告入口。', 'SQLite 保存历史 run，可按 run_id 重渲染；README 与 SUBMISSION 给出运行和评审动线。'],
  },
  {
    title: '代码结构、数据设计、错误处理和工程意识',
    answer: '工程目标是“真实链路能跑，外部服务失败也不会毁掉演示”。',
    evidence: ['55 项自动测试；统一数据契约；历史运行可保存、可回查。', '密钥不进入页面；实况限流、并发 1、超时终止；异常时保留稳定回放。'],
  },
  {
    title: '是否有独立判断，指出需求中的不确定性、数据限制或平台限制',
    answer: '主动拆开容易制造漂亮数字的口径，并把未验证部分明确标出来。',
    evidence: ['品牌词与无品牌词分层；“被提及”不等于“被推荐”。', '有来源链接不等于逐句事实核验；单平台单轮样本不冒充 ChatGPT / Gemini 市场结论。'],
  },
])

const stages = computed(() => [
  { no: '01', label: '发现用户问题', result: `${props.report.questions.length} 个西语需求问题`, explanation: '先模拟当地用户会怎么问，再按购买阶段和商业价值筛选。', proof: '品牌词与无品牌词从问题层就分开。' },
  { no: '02', label: '取得真实回答', result: `${groundedCount.value}/${props.report.answers.length} 条联网成功`, explanation: '调用 DeepSeek 联网搜索，保留回答原文与来源链接。', proof: `${mainSourceCount.value} 个主回答来源可回查。` },
  { no: '03', label: '判断品牌表现', result: `无品牌词提及 ${percent(props.report.metrics.unbranded.visibility_rate)}`, explanation: '分别识别提及、推荐、顺位、竞品和来源，不把“认识品牌”误算成“主动推荐”。', proof: `品牌词可见度 ${percent(props.report.metrics.branded.visibility_rate)}，无品牌词推荐 ${percent(props.report.metrics.unbranded.recommendation_rate)}。` },
  { no: '04', label: '检查官网承接', result: `${props.report.site_audit.pages_checked} 页实抓`, explanation: '检查 AI 与搜索引擎是否能抓取、理解并找到目标市场内容。', proof: '本次抓取未发现 es-MX hreflang 与西语页面。' },
  { no: '05', label: '扩展问题分支', result: `${props.report.fanout_metrics.queries_checked} 个派生问法`, explanation: '把高价值问题换一种问法继续测，避免只靠单一 Prompt 得出结论。', proof: `分支提及覆盖 ${percent(props.report.fanout_metrics.mention_coverage)}，且品牌泄漏为 0。` },
  { no: '06', label: '定位业务缺口', result: `${props.report.gaps.length} 项证据缺口`, explanation: '把回答与官网信号合并，指出品牌为什么没有进入答案、用户下一步在哪里流失。', proof: '每项缺口都关联具体问题、回答或站点检查结果。' },
  { no: '07', label: '给出行动顺序', result: `${props.report.recommendations.length} 条优先建议`, explanation: '按影响与工作量排序，让客户知道先修什么、再建设什么。', proof: '建议覆盖技术地基、本地化承接、内容与长期监测。' },
])

const currentStage = computed(() => stages.value[activeStage.value])

const recommendationTitles = ['补齐墨西哥官网的语言与抓取信号', '上线墨西哥本地购买渠道页', '围绕高价值问题建立西语内容集群']
const recommendationCards = computed(() => props.report.recommendations.slice(0, 3).map((item, index) => ({
  ...item,
  displayTitle: recommendationTitles[index] ?? item.action,
})))

function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

function startReplayTimer(): void {
  if (replayTimer) window.clearInterval(replayTimer)
  if (!isPlaying.value) return
  replayTimer = window.setInterval(() => {
    if (activeStage.value >= stages.value.length - 1) {
      isPlaying.value = false
      return
    }
    activeStage.value += 1
  }, 3600 / replaySpeed.value)
}

function selectStage(index: number): void {
  activeStage.value = index
  isPlaying.value = false
  replayRun.value += 1
}

function restartAndFocus(): void {
  activeStage.value = 0
  isPlaying.value = true
  replayRun.value += 1
  window.requestAnimationFrame(() => journeySection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

function nextStage(): void {
  activeStage.value = Math.min(activeStage.value + 1, stages.value.length - 1)
  isPlaying.value = false
  replayRun.value += 1
}

function skipToConclusion(): void {
  activeStage.value = stages.value.length - 1
  isPlaying.value = false
  replayRun.value += 1
}

function toggleAssessment(index: number): void {
  activeAssessment.value = activeAssessment.value === index ? null : index
}

watch([isPlaying, replaySpeed], startReplayTimer, { immediate: true })
onUnmounted(() => replayTimer && window.clearInterval(replayTimer))
</script>

<template>
  <div class="product-page">
    <section id="top" class="product-hero hero-entrance">
      <div class="product-hero-copy">
        <span class="candidate-byline">刘畅 · AI 研发工程师候选作品</span>
        <span class="view-label">PRODUCT VIEW · 给 HR 与产品经理</span>
        <p class="product-definition">AI 海外市场诊断智能体：输入品牌与目标市场，找出 AI 推荐缺口、官网承接问题与行动优先级。</p>
        <h1>AI 认识 Deli，<br><em>但不会主动推荐它。</em></h1>
        <p class="hero-summary">品牌认知已经存在，但在墨西哥用户不写品牌名的真实需求里，Deli 没有进入答案；官网也缺少西语内容承接这部分机会。</p>
        <div class="hero-actions">
          <button class="primary-action" @click="restartAndFocus">▶ 从头播放诊断过程</button>
          <a class="secondary-action" :href="reportHref" target="_blank" rel="noopener">打开完整报告 ↗</a>
        </div>
        <small class="sample-note">真实联网单平台样本 · 通用需求 {{ report.metrics.unbranded.questions_checked }} 题 + 派生问法 {{ report.fanout_metrics.queries_checked }} 题 · 观测值非市场定论</small>
      </div>

      <div class="outcome-board" aria-label="核心业务结论">
        <article class="outcome-primary"><span>通用需求中主动出现</span><strong>{{ percent(report.metrics.unbranded.visibility_rate) }}</strong><p>不写 Deli 时，AI 没有主动想到它</p></article>
        <article><span>直接问品牌时可见</span><strong>{{ percent(report.metrics.branded.visibility_rate) }}</strong><p>AI 知道 Deli 是谁</p></article>
        <article><span>官网西语内容</span><strong>0<small>页</small></strong><p>{{ report.site_audit.pages_checked }} 页实抓范围内未发现</p></article>
      </div>
    </section>

    <section class="assessment-section" data-reveal>
      <header class="section-intro">
        <span>TEST BRIEF · 直接回应测试题</span>
        <h2>测试题明确会看这六件事，我们逐项回答。</h2>
        <p>点击任意一项，在原地查看项目判断、实现方式与可核验证据。</p>
      </header>
      <div class="assessment-list">
        <article v-for="(item, index) in assessmentItems" :key="item.title" :class="{ open: activeAssessment === index }">
          <button class="assessment-summary" :aria-expanded="activeAssessment === index" @click="toggleAssessment(index)">
            <b>{{ String(index + 1).padStart(2, '0') }}</b><span>{{ item.title }}</span><i>＋</i>
          </button>
          <Transition name="accordion">
            <div v-if="activeAssessment === index" class="assessment-collapse">
              <div>
                <div class="assessment-answer">
                  <h3>本项目的回答</h3><p>{{ item.answer }}</p>
                  <h3>可核验的证据</h3><ul><li v-for="proof in item.evidence" :key="proof">{{ proof }}</li></ul>
                </div>
              </div>
            </div>
          </Transition>
        </article>
      </div>
    </section>

    <section ref="journeySection" class="journey-section" data-reveal>
      <header class="section-intro">
        <span>HOW IT WORKS · 诊断过程</span>
        <h2>这个结论是怎么一步步得出的？</h2>
        <p>点击任意节点查看该环节；蓝线严格连接节点中心，当前步骤会高亮并给出业务解释。</p>
      </header>

      <div class="journey-track" :style="{ '--progress': progressRatio }">
        <i class="journey-line"></i><i class="journey-progress"></i>
        <button
          v-for="(stage, index) in stages"
          :key="stage.no"
          :class="{ active: activeStage === index, done: activeStage > index }"
          :aria-label="`${stage.no} ${stage.label}`"
          @click="selectStage(index)"
        >
          <b>{{ stage.no }}</b><span>{{ stage.label }}</span>
        </button>
      </div>

      <div class="journey-controls">
        <span>REAL DATA REPLAY · {{ activeStage + 1 }}/{{ stages.length }}</span>
        <div>
          <button @click="restartAndFocus">↺ 重播</button>
          <button @click="isPlaying = !isPlaying">{{ isPlaying ? 'Ⅱ 暂停' : '▶ 继续' }}</button>
          <button @click="replaySpeed = replaySpeed === 1 ? 2 : 1">{{ replaySpeed }}× 速度</button>
          <button @click="nextStage">下一步 →</button>
          <button @click="skipToConclusion">跳到建议 ⇥</button>
        </div>
      </div>

      <article :key="`${activeStage}-${replayRun}`" class="journey-detail">
        <div><span>{{ currentStage.no }}</span><small>STEP</small></div>
        <section><p>{{ currentStage.label }}</p><h3>{{ currentStage.result }}</h3><strong>{{ currentStage.explanation }}</strong></section>
        <aside><small>为什么可信</small><p>{{ currentStage.proof }}</p></aside>
      </article>
    </section>

    <section id="live-demo" v-if="liveEnabled && ProductLivePanel" class="product-live-section" data-reveal>
      <header class="section-intro">
        <span>LIVE TRYOUT · 现场体验</span>
        <h2>现场跑一次，看 AI 会不会主动想到 Deli。</h2>
        <p>点击开始后，3 个真实的墨西哥用户问题会依次经过联网搜索，并即时显示回答与来源情况。</p>
      </header>
      <Suspense>
        <component :is="ProductLivePanel" audience="product" :api-base="apiBase" />
        <template #fallback><div class="product-live-loader">正在加载现场诊断模块…</div></template>
      </Suspense>
    </section>

    <section class="recommendation-section" data-reveal>
      <header class="section-intro">
        <span>NEXT ACTION · 客户下一步</span>
        <h2>不是“多做内容”，而是按证据排出先后顺序。</h2>
      </header>
      <div class="recommendation-grid">
        <article v-for="item in recommendationCards" :key="item.action">
          <span>{{ item.priority }} · 工作量 {{ item.effort }}</span><h3>{{ item.displayTitle }}</h3><p>{{ item.expected_impact }}</p>
        </article>
      </div>
    </section>

    <section class="product-report-cta" data-reveal>
      <div><span>FULL EVIDENCE</span><h2>需要逐条问题、回答、来源和建议？</h2><p>完整报告保留真实回答原文、来源 URL、官网诊断和口径说明。</p></div>
      <a :href="reportHref" target="_blank" rel="noopener">打开完整诊断报告 ↗</a>
    </section>

    <footer class="product-footer">真实样本 run {{ report.meta.run_id }} · {{ report.answers.length }} 条回答 · {{ mainSourceCount }} 个主来源 · 结果不等同于 ChatGPT / Gemini 客户端表现</footer>
  </div>
</template>
