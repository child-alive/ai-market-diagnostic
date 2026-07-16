# AI 海外市场诊断智能体（原型）

面向出海品牌的 GEO（生成式引擎优化）诊断原型。输入品牌与目标市场，输出问题地图、AI 可见度、竞品话语权、官网可引用性、内容缺口与优先行动建议。

演示用例为 **得力 Deli × 墨西哥 × 西班牙语**。核心指标与聚路国际产品语言对齐：Mention Rate / Visibility、Recommendation Rate、Share of Voice、Average Position、Citation Rate、Sentiment、Source Mix；问题按品牌词 / 地区排名词 / 品类排名词与 TOFU / MOFU / BOFU 分类。

## 三步运行

要求 Python 3.10+。以下命令在项目根目录执行。

```bash
# 1. 创建环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 可选：配置 DeepSeek V4 + 联网搜索；不配置会自动进入全 Mock 模式
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 运行可复现演示（无需 key、无需访问 AI 服务）
.venv/bin/python -m src.main --mock
```

成功时终端输出应包含：

```text
[done] 问题 20 条 | AI 回答 8 条 | 缺口 7 项 | 建议 7 条
```

打开 `data/report.html` 即可查看蓝白中西双语诊断报告。结构化结果在 `data/report.json`，本次运行同时写入 `data/diagnostic.db`。

## 双受众演示网页（可选增强）

仓库已提交 `web/dist/`，评审者本地查看**不需要安装 Node.js**。完成上面的 Python 依赖安装后：

```bash
.venv/bin/uvicorn src.demo_api:app --host 127.0.0.1 --port 8765
# 浏览器打开 http://127.0.0.1:8765/
```

默认回放模式读取固化的真实运行 `37b442ec`，零 API 消耗；产品视角讲业务洞察，技术视角展示原始 JSON、来源与等价命令。实况模式只有在评审者显式点击后才运行固定的 3~5 个高价值无品牌词，并限制为每 IP 每小时 2 次、全局并发 1、总超时 180 秒；Key 只存在服务端。未配置 DeepSeek 时实况返回友好提示，回放和完整报告仍可用。

如需修改前端源码，在 `web/` 运行 `npm ci && npm run build`。ECS 上线步骤见 [`deploy/部署手册.md`](deploy/部署手册.md)；仓库提供一键脚本，但不包含或上传任何密钥。

## 常用运行方式

| 命令 | 用途 | 数据边界 |
| --- | --- | --- |
| `.venv/bin/python -m src.main --mock` | 最稳定的离线演示 | 问题、AI 回答与网站诊断均使用 fixtures；页面明确标注 Mock / Snapshot |
| `.venv/bin/python -m src.main --mock --live-audit` | 可复现 AI 结果 + 实时官网诊断 | AI 回答为 Mock；官网实时抓取，失败自动回退快照 |
| `.venv/bin/python -m src.main` | 有 key 时运行 hybrid 链路 | DeepSeek V4 生成问题/抽取，回答启用原生 Web Search；无 key 时自动切 Mock |
| `.venv/bin/python -m src.main --providers auto` | 运行全部已配置平台 | 按 DeepSeek / OpenAI / Gemini 分别保存回答、引用与指标；缺 Key 的平台自动略过 |
| `.venv/bin/python -m src.main --providers openai,gemini` | 显式选择平台 | 若所选平台缺 Key 则明确报错，不隐式降级 Mock |
| `.venv/bin/python -m src.main --providers auto --verify-evidence` | 多平台检测 + 来源证据预审 | 额外抓取公开来源页面，将回答陈述标成支持/部分支持/未找到/无法访问；结果始终要求人工复核 |
| `.venv/bin/python -m src.main --top-n 10` | 调整 AI 可见度检测样本数 | 默认检测价值分最高的 8 个问题 |
| `.venv/bin/python -m src.main --query-fanout` | 增加 Query Fanout 抽样 | 选 2 个高价值无品牌词父问题，各派生 3 个分支并由 DeepSeek 联网检测；显式启用才消耗额外额度 |
| `.venv/bin/python -m src.main --run-id <RUN_ID>` | 重渲染历史报告 | 从 SQLite 恢复完整报告，不重新调用 LLM 或抓取官网 |
| `.venv/bin/python -m src.sampling_demo` | 真实重复采样方法论演示 | 固定 q05/q07/q08，各调用 DeepSeek Web Search 3 次；写入独立 JSON，不改变主报告 |
| `.venv/bin/uvicorn src.demo_api:app --host 127.0.0.1 --port 8765` | 本地打开双受众网页 | 直接托管已构建回放页；有 DeepSeek Key 时同时提供受限实况端点 |

> **`--providers auto` 当前现状（2026-07-17 实测）：** 本机的 OpenAI 官方 API 账户因无可用 credits 返回 `429 insufficient_quota`；Gemini 普通文本生成可用，但 `google_search` Grounding 返回 `429 RESOURCE_EXHAUSTED`。因此评审者无相应官方额度/权限时请优先运行 `--mock` 或单独选择已可用平台，不要直接使用 `auto`。

> **重复采样额度提示：** `python -m src.sampling_demo` 默认产生 9 次真实 DeepSeek Web Search 请求，仅在主动运行时消耗额度；Mock 主链路不会触发它。

每次新运行会打印 `run_id`。例如：

```text
[db]   run_id=148d4739 → .../data/diagnostic.db
```

之后可执行：

```bash
.venv/bin/python -m src.main --run-id 148d4739
```

## 报告包含什么

1. 品牌词/无品牌词分层的 Mention Rate、Recommendation Rate、SOV、排名与引用指标卡，品牌认知与情感诊断，以及多平台横向对比表；
2. 20+ 条西语问题地图，含中文对照、分类、漏斗、价值分与检测结果；
3. Query Fanout：高价值无品牌词的同义改写、场景细化与追问式分支，以及 Parent / Branch Mention / Recommendation Coverage；
4. 逐条 AI 回答的“推荐 / 仅提及 / 未提及”、品牌顺位、竞品、引用来源类型、情感与证据句；另汇总官网/权威媒体与政府/电商/目录/论坛/其他 Source Mix，启用预审时再列来源页证据片段和支持状态；
5. robots.txt 中 8 个 AI 访问 token 的分项状态、`llms.txt` / `llms-full.txt`、原始 HTML/JS 依赖、FAQ/直接回答结构，以及 sitemap、`es-MX hreflang`、JSON-LD、西语内容与可抓取性检查；
6. 带证据链的内容/页面/技术信号缺口；
7. P0 / P1 / P2 行动建议，含理由、预期影响与工作量。

ECharts 通过 CDN 加载；断网时竞品排行表与其余全部内容仍可正常阅读。提交示例位于 `data/示例产物/`：真实运行 `37b442ec` 由 `deepseek-v4-flash` 实时生成 22 条问题并回答 Top-8，8/8 主回答均由 Web Search 支撑，共返回 70 个来源 URL，0 Mock、0 结构化解析降级；同时从 2 个高价值无品牌词父问题派生 6 个 Query Fanout，6/6 联网成功并返回 66 个来源 URL。官网结果为 2026-07-17 对 `deliworld.com` 的 15 页实时检查，报告模式为 `hybrid`。同目录的 `repeat_sampling.json` 是 3 个固定无品牌词问题 × 3 轮的独立真实重复采样，9/9 联网成功。

## 数据与工程约定

- 模块间只通过 `src/models.py` 的 Pydantic 契约传递数据；
- `AnswerProvider` 隔离具体 AI 平台，当前提供 DeepSeek、OpenAI Search、Gemini Google Search Grounding 与 Mock 实现；未配置对应 Key 时只运行本地契约测试，不声称真实联调已通过；
- 多平台运行写入 `platform_results`，各平台独立聚合指标；顶层 `answers/analyses/metrics` 保留为主平台切片，兼容历史报告；
- Mention Rate 只判断品牌是否出现；Recommendation Rate 采用保守启发式，只有明确建议或进入“推荐/最佳选项”列表才计入。历史 SQLite 重渲染时可基于已保存原文补算，不重新请求 API；
- 引用来源类型按可解释域名规则分层；“权威媒体/政府”是来源类别而非自动事实背书，Source Mix 与证据支持率不能互相替代；
- OpenAI / Gemini 原生文本区间会直接映射到来源 URL；DeepSeek 没有区间时，从答案拆分陈述并在最多 3 个来源中寻找最佳页面片段；
- `--verify-evidence` 是可选的词面机器预审：默认每条回答最多检查 3 条陈述、DeepSeek 最多检查 3 个来源，避免默认产生大量页面请求；它不是语义事实核查，更不是人工审核；
- DeepSeek 结构化抽取失败会降级启发式解析并标记 `parse_degraded`；
- DeepSeek 回答通过 Anthropic 兼容端点调用服务端 Web Search，搜索返回的 URL 直接写入回答与分析；
- Web Search 失败时会明确告警并降级为普通回答，不伪造 URL；
- 官网抓取遵守 robots.txt、限速不高于 1 req/s、最多检查 15 页；AI 访问项区分搜索/引用、训练/数据采集和同时影响训练与 Grounding 的控制 token；
- `llms.txt`、JS 依赖、直接回答段落与 FAQ 均为轻量启发式信号，不把缺失项表述成“AI 一定无法抓取”；
- Mock 在数据层 `is_mock`、报告层角标与文档层三处标注；
- 缺口和建议由指标/网站证据规则驱动，不进行不可追溯的二次 LLM 生成。
- 网页回放只读固化 JSON，不访问 Provider；实况 API 不接受任意 Prompt，固定选择版本内高价值无品牌词，并在可终止子进程中逐题输出 SSE，超时后不会留下后台请求继续消耗额度。

## 常见问题

**没有 `DEEPSEEK_API_KEY`？** 直接运行 `--mock`。即使不传 `--mock`，程序在无 key 时也会自动切换到 Mock。

**如何切换模型或联网搜索？** 在 `.env` 中设置 `DEEPSEEK_MODEL=deepseek-v4-flash`。`DEEPSEEK_WEB_SEARCH=true` 控制回答阶段是否使用 Web Search，`DEEPSEEK_SEARCH_MAX_USES=3` 控制单题最多搜索次数。示例配置已给出这些默认值，通常只需填 key。

**配置 OpenAI / Gemini 后会自动消耗三份额度吗？** 不会。不传 `--providers` 时优先保持原有 DeepSeek 单平台行为；只有显式传 `--providers auto` 或列出平台名时才会调用多平台。当前 OpenAI/Gemini 联网限制见上方现状注记。

**“有引用”是否等于“来源支持结论”？** 不等于。Citation Rate 只统计平台 API 是否返回搜索来源。加 `--verify-evidence` 后，系统会抓取来源页面并保存最匹配证据片段与支持状态，但这仍是词面机器预审；报告会固定标注“需人工复核”。

**网络受限或官网反爬？** 使用 `--mock` 可完全离线演示。实时诊断失败会读取 `fixtures/site_snapshot/`，并在报告中标记“快照模式”。

**`--run-id` 提示未找到？** 历史 ID 只存在于本机 `data/diagnostic.db`。先完成一次新运行并复制终端打印的 ID。

**报告中的数字能直接用于客户决策吗？** 不能。提交示例是 DeepSeek 的单轮 8 问真实调用，不等价于 ChatGPT/Gemini 市场表现。即使启用页面级证据预审，也仍需人工确认来源、上下文、时间与结论是否一致。商业测量还需用真实海外平台 Key 完成联调，扩到 100+ 问题并做多轮采样与人工抽检。

**为什么还提供重复采样 JSON？** 因为同一 Prompt 的 AI 回答会变化。`python -m src.sampling_demo` 固定同一组无品牌词问题重复联网请求，保存每轮原文和来源并展示波动；它是小样本方法演示，不是置信区间，也不替代 100+ Prompt Set 的正式测量。

**Query Fanout 会自动消耗额度吗？** 不会。只有显式传 `--query-fanout` 才会调用；真实模式只使用 DeepSeek，并把分支回答和 Coverage 与主 Prompt Set 分开保存、分开展示。`--mock --query-fanout` 可零成本验证完整数据链路。

**演示网页会自动调用 DeepSeek 吗？** 不会。页面默认只播放仓库内的真实历史数据；必须切到“实况模式”并点击“开始实况诊断”才会请求服务端。没有 Key、额度不足、并发占用或超时都会安全退回回放。

**图表没有显示？** 检查能否访问 jsDelivr CDN。即使图表脚本加载失败，右侧竞品排行表仍提供相同数据。

## 运行测试

```bash
.venv/bin/python -m pytest -q
```

当前测试集共 55 个用例，覆盖启发式回答解析、提及/推荐区分、来源质量分层、品牌词/无品牌词独立指标、重复采样聚合、Query Fanout 派生约束/品牌泄漏防护/Coverage、品牌/竞品顺位、引用与情感识别、三平台搜索响应解析与 URL/文本区间传递、多平台调度、页面证据预审、AI 爬虫/llms.txt/原始 HTML 可读性、跨平台报告渲染、SQLite 报告往返、实况固定 Prompt Set / 流事件 / 缺 Key fail-closed / 限流，以及已有真实链路回归场景。所有 OpenAI/Gemini Provider 测试和 Demo Worker 测试均使用本地伪响应，不消耗 API 额度。

## 项目文档

- `SUBMISSION.md`：10 分钟评审动线与题目第八部分四问直答；
- `docs/方案说明.md`：需求理解、架构、取舍、官网实测、限制与下一步；
- `deploy/部署手册.md`：2 核 2G ECS 的 Nginx + 单 worker FastAPI 部署与安全边界；
- `PLAN.md`：权威开发规划与数据协议；
- `PROGRESS.md`：任务进度、验证事实与决策记录。
