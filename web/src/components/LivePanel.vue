<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import type { LiveEvent } from '../types'

const props = withDefaults(defineProps<{ apiBase: string; audience?: 'product' | 'technical' }>(), {
  audience: 'technical',
})
const emit = defineEmits<{ exit: [] }>()

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const message = ref('')
const events = ref<LiveEvent[]>([])
let controller: AbortController | undefined

function concise(text: string, max = 300): string {
  const cleaned = text.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim()
  return cleaned.length > max ? `${cleaned.slice(0, max)}…` : cleaned
}

function parseSseChunk(buffer: string): { events: LiveEvent[]; rest: string } {
  const frames = buffer.split('\n\n')
  const rest = frames.pop() ?? ''
  const parsedEvents: LiveEvent[] = []
  for (const frame of frames) {
    const data = frame
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('')
    if (!data) continue
    try {
      parsedEvents.push(JSON.parse(data) as LiveEvent)
    } catch {
      // 忽略不完整帧；保留缓冲区后继续读取。
    }
  }
  return { events: parsedEvents, rest }
}

async function runLive(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  events.value = []
  message.value = ''
  status.value = 'running'
  const apiBase = props.apiBase.replace(/\/$/, '')

  try {
    const response = await fetch(`${apiBase}/live-diagnose/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_limit: 3 }),
      signal: controller.signal,
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail || `实况服务返回 HTTP ${response.status}`)
    }
    if (!response.body) throw new Error('浏览器未提供流式响应读取能力')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      const parsed = parseSseChunk(buffer)
      buffer = parsed.rest
      events.value.push(...parsed.events)
      const last = parsed.events.at(-1)
      if (last?.type === 'error') throw new Error(last.message || '实况诊断失败')
      if (last?.type === 'completed') status.value = 'done'
      if (done) break
    }
    if (status.value === 'running') status.value = 'done'
  } catch (error) {
    if (controller.signal.aborted) {
      message.value = '本次实况已停止。回放数据不受影响。'
    } else {
      message.value = `${error instanceof Error ? error.message : '实况服务不可用'}。已保留回放模式，你仍可完整查看真实样本。`
    }
    status.value = 'error'
  }
}

function stopLive(): void {
  controller?.abort()
}

onUnmounted(() => controller?.abort())
</script>

<template>
  <section :class="['live-lab', `is-${audience}`]">
    <div class="live-copy">
      <span class="section-index">{{ audience === 'product' ? '3 QUESTIONS · REAL WEB SEARCH' : 'LIVE LAB · EXPLICIT OPT-IN' }}</span>
      <h2>{{ audience === 'product' ? '让 3 个真实问题依次经过联网搜索。' : '用 3 个无品牌词，现场跑一次 DeepSeek Web Search。' }}</h2>
      <p v-if="audience === 'product'">每个问题都会显示 AI 回答、是否提及 Deli，以及找到多少个公开来源。一次体验大约需要 1–3 分钟。</p>
      <p v-else>服务端固定 Prompt Set，不允许输入品牌词；Key 不进入浏览器。每 IP 每小时 2 次，全局同时只跑 1 个任务，超时或额度异常会提示返回回放。</p>
      <div class="guardrails">
        <span>{{ audience === 'product' ? '3 个问题' : '3 questions' }}</span><span>{{ audience === 'product' ? '每小时 2 次' : '2 runs / IP / hour' }}</span><span>{{ audience === 'product' ? '一次只运行 1 项' : 'concurrency 1' }}</span><span>{{ audience === 'product' ? '密钥不进入页面' : 'server-side key' }}</span>
      </div>
      <div class="live-actions">
        <button v-if="status !== 'running'" class="primary-button" @click="runLive">{{ audience === 'product' ? '开始现场诊断' : '开始实况诊断' }}</button>
        <button v-else class="danger-button" @click="stopLive">停止本次诊断</button>
        <button v-if="audience === 'technical'" class="text-button" @click="emit('exit')">返回稳定回放</button>
      </div>
      <p class="scope-note">{{ audience === 'product' ? '这是一次独立体验，不会改变页面中的正式诊断报告。' : '实况回答采用本地启发式提取，避免额外分析调用；结果不回写提交报告。' }}</p>
    </div>
    <div class="live-terminal" aria-live="polite">
      <header><span><i></i><i></i><i></i></span><b>live-diagnostic.stream</b><small>{{ status }}</small></header>
      <div class="terminal-body">
        <div v-if="status === 'idle'" class="terminal-empty">
          <span>READY</span><p>{{ audience === 'product' ? '点击“开始现场诊断”后，结果会逐题出现在这里。' : '等待技术评审显式启动。默认回放不会调用任何 API。' }}</p>
        </div>
        <template v-for="(event, index) in events" :key="index">
          <div v-if="event.type === 'started'" class="terminal-line system"><span>00</span><p>{{ event.message }}</p></div>
          <div v-else-if="event.type === 'question'" class="terminal-line question"><span>{{ String(index).padStart(2, '0') }}</span><p><b>QUERY</b> {{ event.question?.text_local }}</p></div>
          <div v-else-if="event.type === 'result'" class="terminal-result">
            <header><b>{{ event.answer?.question_id }}</b><span>{{ event.answer?.search_grounded ? 'WEB GROUNDED' : 'NO SEARCH' }}</span></header>
            <p>{{ concise(event.answer?.raw_text || '') }}</p>
            <small>{{ event.analysis?.brand_mentioned ? 'MENTIONED' : 'NOT MENTIONED' }} · {{ event.answer?.source_urls.length || 0 }} SOURCES</small>
          </div>
          <div v-else-if="event.type === 'completed'" class="terminal-line success"><span>✓</span><p>诊断完成，已收到 {{ event.completed }} 条回答。</p></div>
        </template>
        <div v-if="status === 'running'" class="terminal-loader"><i></i><span>DeepSeek 正在检索公开网页并生成回答…</span></div>
        <div v-if="message" class="terminal-error"><b>SAFE FALLBACK</b><p>{{ message }}</p></div>
      </div>
    </div>
  </section>
</template>
