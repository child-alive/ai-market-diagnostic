# 网页性能预算验收

验收对象：`web/dist` 的生产构建，由 `vite preview` 在本机提供。

测试日期：2026-07-17。

## 测试口径

- Chrome Lighthouse 12.8.2；
- `throttling-method=devtools`（实际 DevTools 节流，不是估算）；
- CPU slowdown multiplier：4；
- 网络：150ms RTT、1600Kbps，按 Fast 3G 下载侧口径；
- Desktop form factor；冷缓存单次验收。
- 显式桌面视口：1440×900、DPR 1。

第一轮原始报告见 `lighthouse-desktop-fast3g.report.json/.html`。双视角重构后的同口径报告见
`lighthouse-redesign.report.json/.html`；两组都包含 Lighthouse 最终截图与完整审计明细。

## 结果

| 指标 | 预算 | 实测 | 结论 |
|---|---:|---:|---|
| LCP | ≤ 2500ms | 1971.537ms | 通过 |
| 首屏 JS（gzip） | ≤ 300KB | 36.37KB | 通过 |
| 首屏请求数 | ≤ 15 | 5 | 通过 |
| CLS | — | 0.0014 | 记录 |
| 总阻塞时间 | — | 122.739ms | 记录 |
| 首屏总传输 | — | 约 94KiB | 记录 |

## 双视角重构后复测

2026-07-17 按完全相同口径重新测试产品视角首屏：LCP 2154.995ms、CLS 0、TBT 31.838ms、
5 个请求、总传输约 92KiB；生产构建首屏主 JS 34.36KB gzip、CSS 6.13KB gzip。
重构后的产品结论、六项原地下拉和独立技术视图均保留在预算内。

## 成品化精简与全局动效后复测

2026-07-17 移除部署/线路说明、完成受众语言精简，并加入视角切换、首屏分层进入、滚动渐显
和卡片反馈后，再按相同口径测试产品视角：LCP 1793.251ms、CLS 0、TBT 43.238ms、
5 个请求、总传输约 95KiB；生产构建首屏主 JS 37.19KB gzip、CSS 6.58KB gzip。
动效增量没有突破性能预算，LCP 反而比上一轮低约 362ms。

本轮机器报告：`lighthouse-clean-presentation.report.json/.html`。

说明：性能批次的连续两次同口径 LCP 为 1871.325ms、1872.442ms；完成全部视觉与叙事增量后复测为 1971.537ms，仍有约 528ms 预算余量。公网服务器延迟、缓存和代理配置仍会影响线上结果；部署后应按同一口径再跑一次。Nginx 已启用 `gzip_static`，构建会为 HTML/CSS/JS/JSON 生成 `.gz` 文件。
