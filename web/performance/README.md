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

原始机器可读报告见 `lighthouse-desktop-fast3g.report.json`，可视化报告见
`lighthouse-desktop-fast3g.report.html`；二者都包含 Lighthouse 最终截图与完整审计明细。

## 结果

| 指标 | 预算 | 实测 | 结论 |
|---|---:|---:|---|
| LCP | ≤ 2500ms | 1871.325ms | 通过 |
| 首屏 JS（gzip） | ≤ 300KB | 33.74KB | 通过 |
| 首屏请求数 | ≤ 15 | 5 | 通过 |
| CLS | — | 0.0014 | 记录 |
| 总阻塞时间 | — | 126.879ms | 记录 |
| 首屏总传输 | — | 约 90KiB | 记录 |

说明：首屏预加载演示数据后，连续两次同口径 LCP 为 1871.325ms、1872.442ms。公网服务器延迟、缓存和代理配置仍会影响线上结果；部署后应按同一口径再跑一次。Nginx 已启用 `gzip_static`，构建会为 HTML/CSS/JS/JSON 生成 `.gz` 文件。
