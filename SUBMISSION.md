# AI 海外市场诊断智能体 · 评审导览

> 演示用例：得力 Deli × 墨西哥 × es-MX。提交主件是一份可直接打开的真实联网诊断报告，不需要评审者先配置 API。

## 10 分钟评审动线

1. **0~4 分钟：双击打开 [`data/示例产物/report.html`](data/示例产物/report.html)**
   
   先看执行摘要、无品牌词指标和品牌认知板块，再快速浏览问题地图、AI 回答与来源、官网诊断、缺口和 P0/P1/P2 建议。该文件来自 DeepSeek V4 真实联网运行 `f141d182`。

2. **4~7 分钟：阅读 [`docs/方案说明.md`](docs/方案说明.md)**
   
   重点看数据流、branded/unbranded 测量口径、范围取舍和“限制与不确定性”。

3. **7~10 分钟：可选运行零配置 Mock 演示**

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m src.main --mock
   ```

   成功标志：`20 问题 / 8 回答 / 7 缺口 / 7 建议`。完整运行说明见 [`README.md`](README.md)。

4. **可选：在线演示**
   
   回放/实况双模式网页属提交前冲刺增强项，部署后在此回填 URL。当前的 `report.html` 已是独立完整的提交主件。

## 1. 完成了什么

- 建立了“问题发现 → 联网 AI 回答 → 结构化分析 → 官网审计 → 缺口 → 建议 → 报告”的完整诊断管道；
- 为 DeepSeek V4、OpenAI Search、Gemini Google Search Grounding 和 Mock 实现了统一 Provider 契约，多平台结果独立存储、独立计算；
- 将品牌词与无品牌词分层：头版只用 Unbranded Visibility 衡量主动推荐竞争力，品牌词改用于认知、情感和描述准确性诊断；
- 保存 API 返回的搜索来源，并提供可选的页面级证据预审，始终区分“有来源”和“来源支持结论”；
- 完成 15 页上限的官网轻量实抓/快照降级、SQLite 历史运行存档、静态 HTML/JSON 报告与 33 个回归测试。

## 2. 为什么这样设计

- **先交付决策，再展示工程。** 客户最终需要的是“哪里失分、为什么、先做什么”，所以缺口与建议都必须能回溯到问题、回答或站点信号。
- **将测量诚实性当作产品能力。** 含品牌名的问题几乎必然诱发品牌提及，与无品牌词混算会制造虚高可见度；因此数据契约和报告都强制分层。
- **真实链路与可复现演示同时存在。** 真实报告证明 API/Web Search 链路可行；Mock 保证评审者没有 key、没有额度或网络不稳时仍能一键验收。
- **用契约和规则保住可审计性。** Pydantic 模型是模块间唯一数据边界；缺口/建议由明确规则产生，不让第二次 LLM 调用破坏数据自洽。
- **静态报告是最低摩擦的主交付。** 评审者双击即可查看；SQLite 和 `--run-id` 则保留了后续趋势分析的演进路径。

## 3. 哪些是真实、模拟或简化

| 项目 | 边界 |
| --- | --- |
| **DeepSeek 提交示例** | **真实联网运行**：`run_id=f141d182`，22 条实时生成问题、Top-8 真实回答，8/8 `search_grounded=true`，64 个搜索来源 URL，0 Mock、0 解析降级 |
| **真实核心数字** | Top-8 = 4 branded + 4 unbranded；Unbranded Visibility 0%、Unbranded SOV 0%；Branded Visibility 100%、Avg Position 1.5。数字只代表该 run_id 的 DeepSeek 单轮样本 |
| **官网检查** | 2026-07-16 真实抓取 `deliworld.com` 15 页；“未发现西语内容 / es-MX hreflang”仅限该抓取范围，不是全站绝对结论 |
| **Mock 演示** | `--mock` 使用本地 fixtures，问题、回答、官网结果和派生指标均在数据与报告中明显标注；用于链路验收，不代表市场表现 |
| **OpenAI** | Provider 代码和本地伪响应测试已通过；官方最小真实请求因 API 账户无 credits 返回 `429 insufficient_quota`，**不声称联网真实验收通过** |
| **Gemini** | Key 有效且普通文本生成可用；Google Search Grounding 返回 `429 RESOURCE_EXHAUSTED`，**不声称联网真实验收通过** |
| **来源验证** | Citation Rate 只表示平台 API 返回了搜索来源。可选证据预审只做词面覆盖，所有结果仍需人工复核，不是事实核查 |
| **采样结论** | 当前是单轮、8 问演示规模；不与 ChatGPT/Gemini 客户端分布等同，也不直接用于客户商业决策 |

## 4. 下一步做什么

1. 补齐 GEO 站点审计细节：AI 爬虫分项、`llms.txt`、JS 内容可见性、提及 vs 推荐、来源质量分层；
2. 实现 Query Fanout：高价值无品牌词问题派生 3~5 个子问法，计算 Fanout Coverage；
3. 将单轮样本扩展为 100+ Prompt Set 和多轮采样，给出分布、波动与置信区间；
4. 在官方额度/权限恢复后，分别完成 OpenAI Search 与 Gemini Grounding 单题冒烟，再运行同一 Prompt Set 的多平台比较；
5. 完成回放/实况双模式演示网页与部署手册，但不破坏 CLI 和静态报告主交付。

> **范围说明：** 最低交付要求已由 CLI + 真实示例报告 + 方案说明独立满足；Stage 4 与冲刺阶段各项均为可选增强，彼此独立完整，不应被读成“主链路尚未做完”。

---

安全与可复现记录见 [`PROGRESS.md`](PROGRESS.md)；`.env` 从未进入 Git 历史，评审者不需要提供任何 key 即可运行 Mock 验收。
