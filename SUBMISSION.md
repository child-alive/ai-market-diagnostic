# AI 海外市场诊断智能体 · 评审导览

> 演示用例：得力 Deli × 墨西哥 × es-MX。提交主件是一份可直接打开的真实联网诊断报告，不需要评审者先配置 API。

## 10 分钟评审动线

1. **0~4 分钟：双击打开 [`data/示例产物/report.html`](data/示例产物/report.html)**
   
   先看执行摘要、无品牌词指标、Query Fanout 和品牌认知板块，再快速浏览问题地图、AI 回答与来源、官网诊断、缺口和 P0/P1/P2 建议。该文件来自 DeepSeek V4 真实联网运行 `37b442ec`；如需验证随机性，再看同目录的 [`repeat_sampling.json`](data/示例产物/repeat_sampling.json)。

2. **4~7 分钟：阅读 [`docs/方案说明.md`](docs/方案说明.md)**
   
   重点看数据流、branded/unbranded 测量口径、范围取舍和“限制与不确定性”。

3. **7~10 分钟：可选运行零配置 Mock 演示**

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m src.main --mock
   ```

   成功标志：`20 问题 / 8 回答 / 7 缺口 / 7 建议`。完整运行说明见 [`README.md`](README.md)。

4. **可选：双受众演示网页**

   - **公网演示（回放 + 显式实况）：[http://101.201.79.59:8080/](http://101.201.79.59:8080/)**

   同一页面顶部可切换产品视角与技术视角；默认回放不消耗 API，现场诊断只在
   评审者显式点击后运行。

   无需 Node.js 的本地预览：`.venv/bin/uvicorn src.demo_api:app --host 127.0.0.1 --port 8765`，
   然后访问 `http://127.0.0.1:8765/`。`/report/` 是固化完整报告。当前的 `report.html` 仍是独立
   完整的提交主件。

## 1. 完成了什么

- 建立了“问题发现 → 联网 AI 回答 → 结构化分析 → 官网审计 → 缺口 → 建议 → 报告”的完整诊断管道；
- 为 DeepSeek V4、OpenAI Search、Gemini Google Search Grounding 和 Mock 实现了统一 Provider 契约，多平台结果独立存储、独立计算；
- 将品牌词与无品牌词分层，并进一步拆分 Mention Rate 与 Recommendation Rate：品牌进入答案不等于被建议购买；
- 保存 API 返回的搜索来源，展示官网/权威媒体与政府/电商/目录/论坛 Source Mix，并提供可选的页面级证据预审，始终区分“来源类型”“有来源”和“来源支持结论”；
- 完成 3 个无品牌词 × 3 轮的真实 DeepSeek 重复采样，保存逐轮回答与来源，展示 0%~33.3% 的实际波动；
- 完成 Query Fanout：高价值无品牌词按同义改写/场景细化/追问式派生 3~5 个分支，强制品牌泄漏检查，并将 Parent / Branch Coverage 与主 Prompt Set 分开统计；
- 完成 15 页上限的官网轻量实抓/快照降级；站点审计细分 8 个 AI 访问 token、`llms.txt`、原始 HTML/JS 依赖与内容可提取性；并提供 SQLite 历史运行存档与静态 HTML/JSON 报告；
- 完成 Vue 3 + TypeScript 双受众网页：真实数据七阶段回放、产品/技术视角、完整报告入口，以及固定 Prompt Set、SSE 流式进度、限流/并发/超时保护的 FastAPI 实况模式；共 57 个回归测试。

## 2. 为什么这样设计

- **先交付决策，再展示工程。** 客户最终需要的是“哪里失分、为什么、先做什么”，所以缺口与建议都必须能回溯到问题、回答或站点信号。
- **将测量诚实性当作产品能力。** 含品牌名的问题几乎必然诱发品牌提及，与无品牌词混算会制造虚高可见度；因此数据契约和报告都强制分层。
- **真实链路与可复现演示同时存在。** 真实报告证明 API/Web Search 链路可行；Mock 保证评审者没有 key、没有额度或网络不稳时仍能一键验收。
- **用契约和规则保住可审计性。** Pydantic 模型是模块间唯一数据边界；缺口/建议由明确规则产生，不让第二次 LLM 调用破坏数据自洽。
- **静态报告是最低摩擦的主交付。** 评审者双击即可查看；SQLite 和 `--run-id` 则保留了后续趋势分析的演进路径。
- **网页是演出层，不是新的测量口径。** 回放只消费固化报告；实况与主 run 隔离且不回写，既让商务评审快速理解故事，也让技术评审看到真实联网过程。

## 3. 哪些是真实、模拟或简化

| 项目 | 边界 |
| --- | --- |
| **DeepSeek 提交示例** | **真实联网运行**：`run_id=37b442ec`，22 条实时生成问题、Top-8 真实回答，8/8 `search_grounded=true`，70 个主回答来源 URL，0 Mock、0 解析降级 |
| **真实核心数字** | Top-8 = 3 branded + 5 unbranded；Unbranded Mention / Recommendation / SOV 均为 0%；Branded Visibility 100%、Recommendation 66.7%、Avg Position 1.0。无品牌词的 37 个来源中目标品牌官网为 0，目录 5、权威媒体/政府 3、其他 29 |
| **Query Fanout** | 从 2 个高价值无品牌词父问题派生 6 个真实分支，品牌名/别名泄漏 0；6/6 DeepSeek Web Search 成功，66 个来源 URL；Parent / Branch Mention / Recommendation Coverage 均为 0%。分支指标未混入主 Prompt Set |
| **官网检查** | 同一 `37b442ec` 运行真实抓取 `deliworld.com` 15 页，`snapshot_mode=false`；“未发现西语内容 / es-MX hreflang”仅限该抓取范围，不是全站绝对结论 |
| **Mock 演示** | `--mock` 使用本地 fixtures，问题、回答、官网结果和派生指标均在数据与报告中明显标注；用于链路验收，不代表市场表现 |
| **OpenAI** | Provider 代码和本地伪响应测试已通过；官方最小真实请求因 API 账户无 credits 返回 `429 insufficient_quota`，**不声称联网真实验收通过** |
| **Gemini** | Key 有效且普通文本生成可用；Google Search Grounding 返回 `429 RESOURCE_EXHAUSTED`，**不声称联网真实验收通过** |
| **来源验证** | Citation Rate（报告中显示为“来源覆盖率”）只表示平台 API 返回了搜索来源，不是“品牌被引用的比例”。可选证据预审只做词面覆盖，所有结果仍需人工复核，不是事实核查 |
| **重复采样演示** | `repeat_sampling.json` 保存 q05/q07/q08 各 3 轮真实 DeepSeek Web Search，9/9 联网成功；三轮 Mention / Recommendation Rate 均在 0%~33.3% 波动。它证明噪声存在，但不是置信区间 |
| **双受众网页** | 回放数据完整来自 `37b442ec`；2026-07-17 浏览器实况验收固定 q05/q07/q06，3/3 Web Search 成功，来源数分别 3/7/10，Deli 均未提及。该实况不回写主报告，也不混入主指标 |
| **采样结论** | 主报告仍是单轮、8 问演示规模；不与 ChatGPT/Gemini 客户端分布等同，也不直接用于客户商业决策 |

## 4. 下一步做什么

1. 将当前 3×3 方法演示扩展为 100+ Prompt Set 和更多轮次，给出分布、波动与置信区间；
2. 在官方额度/权限恢复后，分别完成 OpenAI Search 与 Gemini Grounding 单题冒烟，再运行同一 Prompt Set 的多平台比较；
3. 将当前 ECS 单机演示扩展为带域名和 HTTPS 的正式服务，并将单机内存限流迁移到共享存储；
4. 在历史 runs 数据上增加时间、地区与平台趋势，并用人工标注集校准推荐和实体抽取。

> **范围说明：** 最低交付要求已由 CLI + 真实示例报告 + 方案说明独立满足；Stage 4 与冲刺阶段各项均为可选增强，彼此独立完整，不应被读成“主链路尚未做完”。

---

安全与可复现记录见 [`PROGRESS.md`](PROGRESS.md)；`.env` 从未进入 Git 历史，评审者不需要提供任何 key 即可运行 Mock 验收。
