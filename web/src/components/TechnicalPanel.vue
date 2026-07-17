<script setup lang="ts">
import { defineAsyncComponent, ref } from 'vue'
import type { Report } from '../types'

const props = defineProps<{
  report: Report
  activeStage: number
  command: string
  payload: unknown
}>()

const showRaw = ref(false)
const JsonViewer = defineAsyncComponent(() => import('./JsonViewer.vue'))

function sourceDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
</script>

<template>
  <div class="stage-output technical-output">
    <div class="output-head"><span>TECHNICAL TRACE</span><b>READ-ONLY</b></div>
    <div class="tech-command"><span>$</span><code>{{ command }}</code></div>
    <div class="tech-meta">
      <span>run_id <b>{{ props.report.meta.run_id }}</b></span>
      <span>provider <b>{{ props.report.meta.providers.join(', ') }}</b></span>
      <span>mode <b>{{ props.report.meta.mode }}</b></span>
      <span>mock <b>false</b></span>
    </div>
    <button class="raw-toggle" type="button" @click="showRaw = !showRaw">
      {{ showRaw ? '收起原始 JSON' : '按需加载原始 JSON' }}
    </button>
    <Suspense v-if="showRaw">
      <JsonViewer :value="payload" />
      <template #fallback><div class="panel-loader">正在加载 JSON 查看器…</div></template>
    </Suspense>
    <div v-else class="raw-placeholder">
      原始数据默认不进入首屏渲染；需要审计时再展开。
    </div>
    <div v-if="activeStage === 1 && props.report.answers[0]" class="source-strip">
      <a
        v-for="url in props.report.answers[0].source_urls.slice(0, 6)"
        :key="url"
        :href="url"
        target="_blank"
        rel="noopener"
      >{{ sourceDomain(url) }} ↗</a>
    </div>
  </div>
</template>

