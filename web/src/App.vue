<script setup lang="ts">
import { defineAsyncComponent, onMounted, ref, watch } from 'vue'
import ProductView from './components/ProductView.vue'
import type { Perspective, Report } from './types'

const TechnicalView = defineAsyncComponent(() => import('./components/TechnicalView.vue'))

const initialView = new URLSearchParams(window.location.search).get('view')
const perspective = ref<Perspective>(initialView === 'technical' ? 'technical' : 'product')
const report = ref<Report | null>(null)
const loadError = ref('')

const liveEnabled = import.meta.env.VITE_ENABLE_LIVE === 'true'
const apiBase = import.meta.env.VITE_API_BASE
const domesticUrl = import.meta.env.VITE_DOMESTIC_URL
const internationalUrl = import.meta.env.VITE_INTERNATIONAL_URL
const reportHref = new URL(`${import.meta.env.BASE_URL}report/`, window.location.href).href

function selectPerspective(value: Perspective): void {
  perspective.value = value
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

watch(perspective, (value) => {
  const url = new URL(window.location.href)
  url.searchParams.set('view', value)
  url.hash = ''
  window.history.replaceState({}, '', url)
})

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
</script>

<template>
  <main :class="['site-shell', `is-${perspective}`]">
    <header class="audience-nav">
      <a class="brand-lockup" href="#top" aria-label="返回页面顶部">
        <span class="brand-mark">J</span>
        <span><b>聚路 GEO Lab</b><small>AI MARKET DIAGNOSTIC</small></span>
      </a>

      <nav class="audience-switch" aria-label="页面阅读视角">
        <button
          :class="{ active: perspective === 'product' }"
          :aria-pressed="perspective === 'product'"
          @click="selectPerspective('product')"
        >
          <span>产品视角</span><small>给 HR / 产品经理</small>
        </button>
        <button
          :class="{ active: perspective === 'technical' }"
          :aria-pressed="perspective === 'technical'"
          @click="selectPerspective('technical')"
        >
          <span>技术视角</span><small>给技术评审</small>
        </button>
      </nav>

      <details class="line-status">
        <summary><i :class="{ online: liveEnabled }"></i>{{ liveEnabled ? '动态演示环境' : '静态演示环境' }}</summary>
        <div>
          <b>线路说明</b>
          <p>国内版与国际版使用同一套页面和同一份报告，不会按网络自动切换；区别只在是否连接实况 API。</p>
          <a v-if="!liveEnabled && domesticUrl" :href="domesticUrl">打开动态演示线路 ↗</a>
          <a v-else-if="liveEnabled && internationalUrl" :href="internationalUrl">打开国际静态线路 ↗</a>
          <small v-else>另一条公网线路尚未回填，因此不展示无效链接。</small>
        </div>
      </details>
    </header>

    <section v-if="loadError" class="fatal-state">
      <span>DATA LOAD ERROR</span><h1>回放数据没有加载成功</h1><p>{{ loadError }}</p>
    </section>

    <template v-else-if="report">
      <ProductView
        v-if="perspective === 'product'"
        :report="report"
        :report-href="reportHref"
      />
      <Suspense v-else>
        <TechnicalView
          :report="report"
          :report-href="reportHref"
          :live-enabled="liveEnabled"
          :api-base="apiBase"
          :domestic-url="domesticUrl"
        />
        <template #fallback><section class="view-loader">正在加载技术评审视图…</section></template>
      </Suspense>
    </template>

    <section v-else class="app-skeleton" aria-label="诊断报告加载中" aria-busy="true">
      <div><i></i><i></i><i></i><i></i></div><aside><i></i><i></i><i></i></aside>
      <span class="sr-only">正在加载真实诊断数据</span>
    </section>
  </main>
</template>
