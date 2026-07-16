# PROGRESS.md — 进度与决策日志

> 本文件是唯一进度真相（协议见 PLAN.md §11）。
> 新接手 agent 必读顺序：`PLAN.md` → 本文件 → `src/models.py`。

---

## 2026-07-16 session-01 (Claude Code)

### 开工前信息核对
- 已完整阅读 `PLAN.md`、测试题 docx、聚路国际产品介绍 PDF（43 页）。
- PDF 确认出题公司指标体系：AI可见度 / Citation 引用率 / SOV 话语权 / 情感倾向 /
  Query Fanouts 问题分支；问题三层分类（品牌词/地区排名词/全国排名词）；
  与 PLAN.md §0 的对齐策略一致，无需修正。

### Stage 0 — 骨架与契约
- [x] Stage0-T1 目录结构 + requirements.txt + .env.example + README.md 初版
- [x] Stage0-T2 models.py 全部契约（在 §6 基础上为 DiagnosticReport 增加 answers/analyses 字段，
      并给 AnswerAnalysis 增加 parse_degraded 降级标记——仅增字段，未改名）
- [x] Stage0-T3 MockProvider + fixtures（20 条问题种子 + 8 条分层模拟回答：
      q05/q07/q08/q13/q16 无得力，q06/q09 得力靠后，q01 得力前列；
      未备 fixture 的问题回放通用兜底回答，保证演示不中断）
- [x] Stage0-T4 main.py --mock 空跑全管道输出占位 JSON
- [x] 验收通过：venv 内 `pip install -r requirements.txt && python -m src.main --mock`
      → 20 问题 / 8 回答（Top-8 恰好命中全部 fixtures）/ data/report.json 正常产出
      analysis/site_audit/gaps/recommend 为占位实现，Stage 1-2 填充

**Stage 0 完成 ✅**

### Stage 1 — MVP 完整链路
- [x] Stage1-T1 question_gen：DeepSeek 实时生成（22 条，含题目指定问题）+ 失败/无 key 回退种子；
      providers/deepseek.py（Client 带 1 次重试 + JSON mode；DeepSeekProvider 扮演 AI 回答引擎）
      ⚠️ 本机无 DEEPSEEK_API_KEY，真实调用路径未经实测，仅验证 mock 回退路径
- [x] Stage1-T2 answer_analysis：双路径抽取（hybrid=DeepSeek JSON-mode，失败降级启发式并标 parse_degraded；
      mock=词典+正则启发式，确定性可单测）+ 指标聚合（Visibility/SOV/AvgPosition/CitationRate/Sentiment/竞品榜）。
      mock 验证：visibility 37.5%, sov 8.8%, avg_pos 3.33, citation 100%, 竞品榜 BIC 领先——分层符合 fixtures 设计。
      决策：SOV 按"回答级提及"计数（每回答每品牌至多 1 次）；零售商(Lumen/Office Depot 等)不计入品牌 SOV
- [x] Stage1-T3 gap_analysis + recommendations：规则驱动。mock 验证产出 5 缺口（3 topic + 2 page，均带证据链
      与关联问题 id）+ 6 建议（P0×2/P1×3/P2×1，理由引用具体指标值）；site_audit signal 缺口留待 Stage 2 接入
- [x] Stage1-T4 最简 report.html：六大板块齐全（指标卡/竞品榜/问题表/回答明细/缺口/建议），
      MOCK 角标与快照模式标注就位；程序化校验 9 项全过（浏览器预览被环境拒绝，改文本校验）
- [x] Stage1-T5 docs/方案说明.md 初稿（需求理解/架构/指标口径/范围取舍/限制与不确定性/下一步；
      §9 六条独立判断已全部写入 §4 章节）
- [x] Stage 1 验收：`python -m src.main --mock` 一条命令产出完整 report.html + report.json；
      无 key/断网纯 Mock 可跑 ✅（真实 DeepSeek 路径已实现但因本机无 key 未实测，见 T1 备注）

**Stage 1 完成 ✅（MVP 达成，满足题目最低交付要求）**

### Stage 2 — 网站诊断 + 指标完备
- [x] Stage2-T1 site_audit 全部检查项：robots/sitemap/es-MX hreflang/JSON-LD/meta/西语内容检测；
      限速 1 req/s、≤15 页、超时 15s；mock 或网络失败降级 fixtures/site_snapshot（得力官网真实快照 2026-07-16 抓取）。
      新增 CLI 旗标 `--live-audit`：mock 模式下仍实抓官网（其余环节维持 mock）
- [x] Stage2-T2 指标补齐（SOV/AvgPosition/Sentiment/竞品榜）——已在 Stage1-T2 一并完成
- [x] Stage2-T3 缺口分析接入 site_audit 证据（high/medium issue → signal 缺口 → P0 技术修复建议）——已在 Stage1-T3 预埋并验证
- [x] Stage2-验收（部分）：`--mock --live-audit` 对得力真实官网实抓 15 页成功，
      确认：无 es-MX hreflang（仅 en/vi/zh-TW/zh-CN/ko/ru/en-EU）、无西语内容、有 JSON-LD、robots/sitemap 正常；
      产物快照已存 data/示例产物/report.{json,html}
- [x] Stage2-T4 SQLite 落库：`runs` 表按 `run_id` 保存完整 report JSON 与检索字段；
      每次新运行自动存档，`--run-id` 可恢复原报告并重渲染 JSON/HTML；不存在的 ID 返回明确 CLI 错误

**Stage 2 完成 ✅**

### 决策记录
- 项目根目录定为 `聚路国际/ai-market-diagnostic/`（PLAN §5 结构），
  业务 PDF 与测试题 docx 留在上层目录、不入库（含公司资料，不适合进代码仓库）。
- DeepSeek API 调用采用 httpx 直连（OpenAI 兼容协议），不引入 openai SDK，
  理由：依赖最小化，且 Provider 抽象层本就要求自行封装重试/降级。

---

## 交接说明（session-01 结束，Claude Code → Codex）

### 当前状态一句话
Stage 0 ✅ / Stage 1 ✅（MVP 达成，已满足题目最低交付要求）/ Stage 2 完成约 3/4，
仅剩 SQLite 落库；工作树干净，全部工作已 commit，无半成品。

### 接手前必做
1. 按 PLAN.md §11 顺序读：`PLAN.md` → 本文件 → `src/models.py`；
2. 跑基线确认未破坏：`cd ai-market-diagnostic && .venv/bin/python -m src.main --mock`
   （或 `pip install -r requirements.txt` 后用系统 python）。
   预期输出：问题 20 条 / 回答 8 条 / 缺口 7 项 / 建议 7 条，data/ 下产出 report.json + report.html。

### 环境要点（踩过的坑）
- 本机 python3 = 3.10.6，项目 venv 在 `ai-market-diagnostic/.venv`（已 gitignore）；
- **session-01 交接时本机没有 DEEPSEEK_API_KEY**：hybrid 真实链路（question_gen LLM 生成、DeepSeekProvider、
  llm_analyze）代码已写但从未实测，拿到 key 后先小规模验证这三处的 JSON 解析；
- 本机网络可直连 deliworld.com，site_audit 实抓已验证（约 20 秒，限速 1 req/s）；
- 上层目录的业务 PDF 与测试题 docx 刻意不入库；
- pandoc/pdftoppm 本机不可用（读 docx/pdf 需用 python zipfile/pypdf）。

### 剩余任务清单（按 PLAN 顺序）
1. **Stage2-T4（下一个）**：`src/storage.py` SQLite 落库——runs 表存每次运行的 report JSON，
   `main.py` 加 `--run-id` 参数从库中重渲染历史报告；完成后 Stage 2 全部验收；
2. **Stage 3**：report.html 视觉升级（指标卡片/ECharts 竞品柱状图/中西双语标签，PLAN §7 Stage3 清单）、
   方案说明定稿（补网站诊断实测结果）、README 定稿、pytest 约 10 个用例
   （重点：analysis.heuristic_analyze 与 aggregate_metrics——纯函数好测）；
3. **Stage 4（可选）**：FastAPI + 前端 / 第二 Provider / Query Fanout / 演示视频。

### 关键设计约定（勿破坏）
- 模块间只经 `src/models.py` 的 Pydantic 契约传数据；字段可增不可改名；
- mock 数据三层标注（is_mock 字段 / 报告 MOCK 角标 / 方案说明）；
- fixtures 的 8 条回答是分层设计的（5 无品牌 / 2 靠后 / 1 前列），改动会破坏演示结论层次；
- visibility 的 Top-N 按 value_score 稳定排序选取，恰好命中 8 条 fixtures，
  改种子分值前先确认不影响命中集合；
- 缺口/建议是规则驱动（不再调 LLM），保证与指标自洽，勿改成二次 LLM 生成。

### 决策记录

---

## 2026-07-16 session-02 (Codex)

### 开工与基线
- [x] 按交接顺序完整阅读 `PLAN.md` → `PROGRESS.md` → `src/models.py`
- [x] 基线通过：`.venv/bin/python -m src.main --mock`
      → 问题 20 条 / AI 回答 8 条 / 缺口 7 项 / 建议 7 条；接手时工作树干净、共 11 个 commit

### Stage 2 — 网站诊断 + 指标完备
- [x] Stage2-T4 SQLite 落库 + `--run-id` 历史重渲染：
      `data/diagnostic.db` 的 `runs` 表保存完整 `DiagnosticReport` JSON；
      已验证新运行写入、按 run_id 重渲染以及无效 run_id 报错三条路径

**Stage 2 完成 ✅**

### Stage 3 — 报告打磨 + 文档冲刺
- [x] Stage3-T1 report.html 视觉升级：五项指标卡、ECharts SOV 对比柱状图、
      中西双语问题明细、回答证据卡、网站诊断矩阵、缺口/建议卡片与响应式/打印样式；
      Mock 标注覆盖全局说明、五个派生指标、问题检测结果与逐条回答
- [x] Stage3-T1 视觉 QA：桌面端 1280px 与移动端 390px 浏览器实测，无横向溢出、无控制台错误，
      ECharts SVG 正常渲染；示例 HTML 已用原有真实官网实抓 JSON 重渲染（15 页、非快照模式）
- [x] Stage3-T2 `docs/方案说明.md` 定稿：补官网实抓结果、SQLite/错误处理、
      当前完成边界与下一步；PLAN §9 六项限制与不确定性全部保留
- [x] Stage3-T3 `README.md` 定稿：三步运行、五种 CLI 用法、`--run-id` 示例、
      产物/数据边界/工程约定与无 key、网络受限、图表 CDN 等常见问题
- [x] Stage3-T4 pytest：14 个用例覆盖启发式解析（别名/顺位/竞品/引用/情感/词边界）、
      指标聚合（空输入/公式/竞品排序）、SQLite 报告往返/未知 ID 与两项真实链路回归场景；`14 passed`
- [x] Stage 3 最终验收：mock 基线保持 20 问题 / 8 回答 / 7 缺口 / 7 建议；
      新 run 写库后按 `--run-id` 重渲染成功；示例报告仍保留实时官网检查 15 页、非快照模式

**Stage 3 完成 ✅**

### DeepSeek 首版真实链路联调（用户配置 API 后）
- [x] 三段小测通过：DeepSeek 实时生成 22 条问题（含题目指定西语问题）、单条真实回答、
      单条 JSON-mode 结构化抽取；`is_mock=false`、无降级
- [x] 首版完整 hybrid 验收通过：22 问题 / 8 条 DeepSeek 回答 / 8 条结构化分析；
      `run_id=c271b6ac`，0 Mock、0 解析降级；SQLite 历史重渲染成功
- [x] 首版真实指标：Visibility 62.5% / SOV 16.13% / Avg Position 1.2 /
      Citation Rate 100%；官网实时检查 15 页，问题仍为 `NO_HREFLANG_ES_MX`、`NO_SPANISH_CONTENT`
- [x] `data/示例产物/report.{json,html}` 当时已升级为 hybrid 真实运行产物；
      当前提交版已由下方 Stage 4 的 V4 + Web Search 产物取代

### 决策记录（真实数据反馈）
- DeepSeek 曾将“Deli”歧义解释为熟食并输出 FUD/Zwan 等食品品牌；修复为仅对原问题已包含 Deli 的问法
  追加“得力文具品牌”消歧。曾尝试全局消歧，但会向通用品类问题泄露目标品牌、污染 Visibility，验证后撤回
- LLM 可能输出 `BIC`/`Bic` 大小写变体；抽取后按既有品牌词典做大小写规范化、去重并过滤零售商，
  不修改数据契约或规则驱动缺口模块
- 首版真实链路未接检索工具，回答域名属于模型声明来源；该限制已在下方 Stage 4
  通过 DeepSeek V4 服务端 Web Search 解决，但仍需保留“未逐句人工核对证据”的边界

### Stage 4 — DeepSeek V4 + 联网搜索增强（用户明确要求）
- [x] 模型切换为 `deepseek-v4-flash`；`.env.example` 新增联网开关与单题最大搜索次数，
      已有 `.env` 只需保留 key，无需额外搜索服务密钥
- [x] `DeepSeekProvider` 回答阶段接入 Anthropic 兼容端点的服务端 Web Search；
      解析 `web_search_tool_result`，将真实返回的 URL 写入 `AIAnswer.source_urls`
- [x] 搜索失败降级路径完成：显式输出警告，普通回答明确说明无联网，不伪造 URL；
      无 key / `--mock` 链路保持原有可复现性
- [x] 数据契约和报告升级：记录模型、Web Search 开关、单条 grounded 状态与来源 URL；
      报告显示 Web Search 标记、联网引用率与可点击来源
- [x] 真实完整验收：`run_id=f141d182`，22 问题 / 8 回答 / 5 缺口 / 5 建议；
      8/8 回答 `search_grounded=true`，共 64 个来源 URL / 38 个域名，0 Mock、0 解析降级
- [x] 真实指标：Visibility 50% / SOV 17.39% / Avg Position 1.5 /
      Citation Rate 100%；官网实时检查 15 页，非快照模式
- [x] 回归与视觉 QA：17 个 pytest 用例通过；mock 基线保持 20/8/7/7；
      1280px 桌面与 390px 移动端无溢出、无控制台错误；SQLite 历史重渲染成功
- [x] `data/示例产物/report.{json,html}` 已更新为 V4 + Web Search 真实产物

### 决策记录（V4 与联网搜索）
- 偏离 PLAN 原 `deepseek-chat` 设定，改用 `deepseek-v4-flash`：用户明确要求切换模型与联网搜索，
  且当前 DeepSeek 接口实测由 V4 模型支持服务端 Web Search；PLAN 的锁定模型行已同步更新
- 保留 OpenAI 兼容 `/chat/completions` 用于问题生成和 JSON-mode 抽取，仅回答阶段使用
  Anthropic 兼容 `/anthropic/v1/messages`：前者结构化输出已验收，后者能直接返回服务端搜索结果，改动最小
- Citation Rate 改为“至少带一个 Web Search 来源 URL 的回答占比”；URL 来自 API
  返回结果，但仍不宣称已完成逐句证据支持关系的人工审核

### 下一步
1. Stage 4 联网搜索增强已完成；其余可选加分项为 FastAPI、第二 Provider、Query Fanout 或演示视频；
2. 若进入产品化，优先接真实海外平台并扩大到 100+ 问题、多轮采样。

### Stage4-T2 — OpenAI / Gemini 联网 Provider（等待用户配置 Key）
- [x] 数据契约只增字段：`AIAnswer` 记录实际模型、搜索词与
      `SourceAnnotation`（答案文本区间 → 来源 URL），旧 JSON / SQLite 报告可依默认值加载
- [x] `OpenAISearchProvider`：按当前官方 Search in ChatGPT 专用路径调用
      `gpt-5-search-api` + Chat Completions `web_search_options`，解析 `url_citation`
- [x] `GeminiSearchProvider`：按当前官方推荐的 Interactions API 调用
      `gemini-3.5-flash` + `google_search`，解析搜索词与带区间的引用注解
- [x] `.env.example` 新增 OpenAI / Gemini 的 Key、Base URL 和模型配置；
      缺 Key 时不构造对应 Provider，不做隐式伪降级
- [x] 4 个新单测覆盖 Key 门禁、请求契约、URL 去重、文本区间和搜索词传递；
      全量 `21 passed`，全部使用本地伪响应，**未声称 OpenAI/Gemini 真实链路已联调**

### 决策记录（多平台 Provider）
- OpenAI 选 `gpt-5-search-api` 而非通用 Responses `web_search`：官方当前明确该专用模型
  直接访问 Search in ChatGPT 使用的微调模型与搜索工具，更符合“校准客户端体验”目标
- Gemini 选当前官方推荐的 Interactions API，因为它直接返回
  `google_search_call` 与文本区间级 `url_citation`，便于下一任务做逐句证据验证
- 仍用 `httpx` 直连，不引入两套 SDK；与已验收 DeepSeek Provider 的依赖策略保持一致

### Stage4-T3 — 多平台调度与分平台指标
- [x] CLI 新增 `--providers`：支持 `deepseek,openai,gemini` 显式列表与 `auto`；
      显式选中但缺 Key 时立即报错，`--mock` 与 `--providers` 互斥
- [x] 同一份问题地图依次运行多个 Provider；`PlatformResult` 对每个平台独立保存
      answers / analyses / VisibilityMetrics，`AnswerAnalysis` 通过 provider + question_id 区分同题多平台结果
- [x] 向后兼容：顶层 `answers/analyses/metrics` 仍是主平台切片；旧运行
      `f141d182` 可从 SQLite 恢复并重渲染，旧字段无需迁移
- [x] 只有 OpenAI/Gemini Key 时也可进入 hybrid；问题生成与结构化抽取在无 DeepSeek Key
      时分别使用稳定问题种子与启发式抽取，不错把其他平台 Key 当成 DeepSeek Key
- [x] 多平台单测覆盖 auto 选择、缺 Key 报错、主平台兼容与独立指标；
      全量 `23 passed`，mock 基线保持 20/8/7/7

### 决策记录（多平台调度）
- 不把三平台回答直接混成一个 Visibility/SOV，而是各自聚合；否则平台样本量与回答分布
  会被掩盖，无法回答“得力在 ChatGPT 和 Gemini 中分别如何”
- 缺口和建议规则暂时继续使用主平台切片，并写入 `meta.notes`；等报告完成跨平台
  对比后再设计“共识缺口”规则，避免未验收就改动已通过的推荐模块

### Stage4-T4 — 引用证据预审与跨平台报告
- [x] 新增可选 `--verify-evidence`：抓取平台 API 返回的公开来源页面，保存回答陈述、
      最佳页面证据片段、来源 URL、支持状态、词面分数与 `requires_human_review=true`
- [x] OpenAI/Gemini 优先使用原生 `url_citation` 文本区间；DeepSeek 无区间时拆分答案陈述，
      每条回答默认最多 3 条陈述、最多 3 个搜索来源，页面缓存避免重复请求
- [x] 状态分层完成：supported / partial / not_found / inaccessible / unmapped；
      `contradicted` 仅为后续语义或人工核验预留，当前词面算法不会伪造矛盾判断
- [x] 报告新增多平台横向表与来源证据预审表；所有文案已从 DeepSeek 专属修正为对应平台，
      明确区分“API 返回来源”和“来源支持结论”，并固定显示“机器预审 · 需人工复核”
- [x] 回归通过：`28 passed`；mock 基线保持 20/8/7/7；旧报告无新字段时仍可依默认值渲染
- [x] 桌面端 1280px 本地浏览器 QA：无横向溢出、ECharts SVG 正常、双平台与证据表正常，
      控制台无错误；合成报告测试固定校验双平台名称、人工复核警示和来源链接

### 决策记录（证据预审）
- 偏离原 Stage 4 清单，增加“引用证据预审”：用户明确要求验证来源是否支撑结论；已同步写入
  `PLAN.md` Stage 4 第 6 项，不改动已验收的缺口/建议模块
- 预审默认关闭且设置请求上限：真实多平台运行本身已消耗 API，若默认再抓取数十个来源页面，
  会放大延迟、失败率和对外站请求；需要时显式加 `--verify-evidence`
- 当前采用可复现的词面覆盖而非再调用 LLM 做“裁判”：避免用一个不可审计模型替另一个模型背书；
  结果用于把人工审核排优先级，不能表述为已完成人工核验
- OpenAI/Gemini Provider 与跨平台报告代码已完成，但 Stage 4“第二个真实 Provider”仍不勾选，
  直到用户配置真实 Key 并完成至少单题冒烟与同题跨平台验收

### Stage4-T5 — OpenAI / Gemini 真实 Key 额度诊断
- [x] 三平台 Key 均被本地配置正确识别；测试过程只输出布尔状态、模型和错误类型，未输出 Key
- [x] OpenAI `gpt-5-search-api` 单题请求到达官方 `/v1/chat/completions`，返回
      `429 insufficient_quota`：认证和请求端点有效，但 API 账户无可用额度；ChatGPT 免费/订阅额度不等于 API 额度
- [x] Gemini 官方 `/v1beta/models` 返回 200，确认 Key 有效且项目可见
      `gemini-3.5-flash`、`gemini-3-flash-preview`、`gemini-3.1-flash-lite` 等模型
- [x] Gemini `gemini-3.5-flash` Interactions 请求返回 `429`；另以官方
      `generateContent + google_search` 小测 `gemini-3-flash-preview` 与 `gemini-3.1-flash-lite`，均返回
      `429 RESOURCE_EXHAUSTED`；`gemini-2.5-flash` 对新用户返回 404 已停用
- [x] 用户提供 AI Studio rate-limit 截图后复核：Gemini 2.5 Flash / 2.5 Flash Lite / 3 Flash
      显示非零免费推理额度；`gemini-3-flash-preview` 不带工具的最小 `generateContent` 请求返回 200，
      证明 Key 与普通文本生成可用，429 的阻塞点是 `google_search` 联网工具而非整个 Gemini 项目
- [x] 进一步测试截图中有免费额度的 `gemini-2.5-flash-lite + google_search`，官方接口对新用户返回 404
      “no longer available”；因此不能用旧模型绕过联网工具限制
- [x] 当前结论：OpenAI 被 API 余额阻塞；Gemini 普通生成可用、Google Search Grounding 被额度/权限阻塞。
      两者都**未记录为联网真实链路通过**

### 决策记录（官方 API 与代理）
- 暂不直接切换未知中转站：本项目要求平台原生联网搜索与文本区间引用；普通 OpenAI 兼容代理即使能聊天，
  也可能不支持 `gpt-5-search-api`、`web_search_options`、Google Search Grounding 或原生引用注解，届时测到的不是同一条链路

### Stage4-T6 — FreeModel 中转站兼容性诊断
- [x] 根据 Key 前缀与服务商公开文档确认 Base URL 为 `https://api.freemodel.dev/v1`；测试只在内存中使用 Key，
      未写入 `.env`、源码、日志、Git 或进度文档
- [x] `GET /v1/models` 返回 200，共 7 个 `gpt-5.x-*` / codex 命名的路由模型；列表中没有项目要求的
      `gpt-5-search-api`，公开文档仅声明 OpenAI/Anthropic 格式兼容与开放模型自动路由，未声明 Search in ChatGPT 链路
- [x] `model=auto` 普通 Chat Completions 与携带 `web_search_options` 的测试均返回
      `401 Insufficient balance`；因此当前 Key 不能完成回答测试，也无法验证搜索参数是否被执行或忽略

### 决策记录（FreeModel）
- 不将 FreeModel 接入本项目：即使充值后普通聊天可用，其自动路由开放模型也不等于 OpenAI 官方
  `gpt-5-search-api`，现有证据不足以证明它会返回原生 `url_citation`；接入会破坏“按真实平台分别测量”的口径

---

## 交接说明（session-02 结束，Codex → Claude Fable5）

### 当前状态一句话
Stage 0~3 全部完成；Stage 4 已完成 DeepSeek V4 原生联网、OpenAI/Gemini Provider 代码、
多平台数据切片与报告、引用证据预审。**DeepSeek 联网真实链路已完整验收；OpenAI/Gemini 因官方额度/
工具权限尚未完成联网真实验收。** 工作树应为干净状态，无未提交半成品。

### 接手前必做（仍按原协议）
1. 完整阅读：`PLAN.md` → `PROGRESS.md` → `src/models.py`；本章节不能替代前文决策记录；
2. `git status --short`：预期无输出；
3. `.venv/bin/python -m pytest -q`：交接时为 `28 passed`；
4. `.venv/bin/python -m src.main --mock`：预期 `20 问题 / 8 回答 / 7 缺口 / 7 建议`；
5. 可用 `.venv/bin/python -m src.main --run-id f141d182` 验证 DeepSeek V4 真实历史报告重渲染，
   不会重新调用 API。

### 已真实验收与只完成代码的边界

| 平台/链路 | 当前事实 | 可否对外声称真实通过 |
| --- | --- | --- |
| DeepSeek V4 普通生成/JSON 抽取 | 已真实联调 | 是 |
| DeepSeek V4 服务端 Web Search | 完整 Top-8 真实运行，`run_id=f141d182`，8/8 grounded，64 URL | 是 |
| OpenAI `gpt-5-search-api` | 请求到官方端点但返回 `429 insufficient_quota` | 否，仅代码+伪响应单测通过 |
| Gemini `gemini-3.5-flash` Interactions + Search | Key 有效，联网请求返回 `429 RESOURCE_EXHAUSTED` | 否，仅代码+伪响应单测通过 |
| Gemini 3 Flash 普通 `generateContent` | 不带工具最小请求返回 200 | 只能声称普通生成可用，不能声称联网可用 |
| Gemini `google_search` Grounding | 3/3.1 系列返回 429；2.5 系列对新用户返回 404 停用 | 否 |
| FreeModel 中转 | 模型列表可读，Chat/Search 均余额不足；模型池不含 `gpt-5-search-api` | 不接入，不算 OpenAI 平台 |

### 本机配置与保密
- `.env` 已存在、权限 `600`、被 gitignore；DeepSeek/OpenAI/Gemini 三个平台字段均已填写，**禁止读取、
  打印、复制或提交任何 Key**；接手只可输出 `bool(key)` 之类的配置状态；
- 用户曾在对话中提供 FreeModel Key，但本项目没有把它写入 `.env`、源码或 Git；不要从聊天复制进仓库；
- 不传 `--providers` 时仍优先 DeepSeek 单平台，不会意外消耗三份额度；`--providers auto` 会调用全部
  已配置平台，当前会因 OpenAI/Gemini 额度问题中途失败，修复额度前不要跑全量；
- 上层目录的业务 PDF/docx 继续保持不入库。

### 代码地图（继续开发先看这些）
- `src/main.py`：Provider 选择、`--providers`、证据预审开关、多平台组装、存储与渲染；
- `src/providers/deepseek.py`：唯一完成真实联网验收的 Provider；不要重构；
- `src/providers/openai_search.py`：Search in ChatGPT 专用请求与 `url_citation` 解析；
- `src/providers/gemini_search.py`：Interactions API + `google_search` 与文本区间引用解析；
- `src/pipeline/evidence.py`：页面抓取、陈述拆分、词面证据匹配；结果永远要求人工复核；
- `src/report/templates/report.html.j2`：主平台指标、跨平台表、来源证据预审与限制文案；
- `src/storage.py`：完整 `DiagnosticReport` JSON 的 SQLite runs 存档；
- `tests/test_openai_search.py` / `test_gemini_search.py` / `test_multiplatform.py` /
  `test_evidence.py`：新 Stage 4 行为的回归边界。

### 必须保持的设计约定
- Pydantic 契约字段可增不可改名；旧 SQLite/JSON 必须能靠默认值加载；
- 顶层 `answers/analyses/metrics` 永远是主平台兼容切片；完整平台结果在 `platform_results`；
- 不把多平台指标混成平均值；缺口/建议目前只基于主平台，并在 `meta.notes` 明示；
- 缺口与建议继续规则驱动，禁止改成不可追溯的二次 LLM 生成；
- 只有原问题出现 Deli 时才加“得力文具”消歧；禁止向通用品类问题泄露目标品牌；
- Citation Rate 仅表示“API 返回来源”，不等于来源支撑结论；
- `--verify-evidence` 默认关闭、有限额、只做词面机器预审；禁止把结果表述为人工事实核查；
- 不因代理能返回普通 Chat Completions 就把它记为 ChatGPT/Gemini 平台结果；必须验证原生搜索与引用契约。

### 建议 Claude Fable5 先讨论、再选择的继续路径
1. **先确认交付目标**：如果目标是尽快提交求职测试，当前 DeepSeek 真实示例 + 多平台可扩展代码已足够，
   不建议为了可选 Stage 4 无限追逐免费 Key；
2. **若必须完成第二真实平台**：优先确认 `.env` 的 Gemini Key 所属项目是否与用户截图中的
   AI Studio project 一致，并查 Google Search Grounding 的独立额度/权限；只做 1 题 Search 冒烟，成功后再改
   `GEMINI_MODEL` 或 Provider；
3. **OpenAI**：官方 Key 已确认缺 API credits；ChatGPT 免费/Plus 与 API 账单分离。没有官方额度时保持
   “代码完成、真实未验收”，不要用普通中转结果冒充；
4. **若暂不解决平台额度**：按 PLAN 剩余可选项中，Query Fanout 比 FastAPI 前端更贴近题目业务；但开始前
   必须与用户确认是否值得继续扩大范围；
5. 任一新任务完成后继续更新本文件并按 `stage4: 完成 xxx` 提交；禁止在工作树留下半成品。

### 推荐的最小真实验证顺序（额度修复后）
```bash
# 先单平台、单题；不要直接 auto / Top-8
.venv/bin/python -m src.main --providers gemini --top-n 1
.venv/bin/python -m src.main --providers openai --top-n 1

# 单题联网成功后再带页面证据预审
.venv/bin/python -m src.main --providers gemini --top-n 1 \
  --verify-evidence --evidence-max-claims 1 --evidence-max-sources 1

# 两个平台均单题通过后，最后才运行全平台
.venv/bin/python -m src.main --providers auto --verify-evidence
```

### 交接时最终验证事实
- pytest：`28 passed`；
- mock：`20 / 8 / 7 / 7`；
- Key 配置状态：DeepSeek/OpenAI/Gemini 均为已配置（不代表均有额度）；
- 最新真实完整报告仍是 DeepSeek `run_id=f141d182`；
- 交接前最后一次 mock 基线会把工作输出 `data/report.{json,html}` 覆盖为 Mock；仓库中用于提交展示的
  DeepSeek V4 真实样例是 `data/示例产物/report.{json,html}`，不要混淆；
- 交接前共 24 个 commit；本交接 commit 完成后应为 25 个。

---

## 2026-07-17 session-03 (Codex，提交前冲刺)

### 冲刺-P0 品牌词 / 无品牌词分层核查
- [x] 交接基线：HEAD `98d00f9`、工作树干净；`28 passed`；mock 为 20 问题 /
      8 回答 / 7 缺口 / 7 建议。Fable5 只完成追加指令入库和 PLAN 冲刺章节，无半成品代码。
- [x] `run_id=f141d182` 真实样本核查：Top-8 中仅 3 题原始 `tier=brand`，但 q02
      “Dónde comprar productos Deli...”虽被标为 regional，文本含 Deli，也必须按 branded 计。
      因此有 4 branded + 4 unbranded；旧头版 50% Visibility 和 1.5 Avg Position
      **全部由 branded 问题贡献**，不能表述为主动推荐竞争力。
- [x] 修正后指标：unbranded = Visibility 0% / SOV 0% / Avg Position 无 /
      Citation 100% / 4 题；branded = Visibility 100% / SOV 40% / Avg Position 1.5 /
      Citation 100% / 情感 3 正面·0 中性·1 负面 / 4 题。顶层旧口径仍保留仅为向后兼容。
- [x] 数据契约只增字段：`UserQuestion.query_scope`、`VisibilityMetrics.branded`、
      `VisibilityMetrics.unbranded`；旧 JSON / SQLite 依默认值可加载，`--run-id` 渲染前
      基于旧 answers/analyses 自动补算分层，不重新调用 API。
- [x] 报告头版改用 Unbranded Visibility；新增“品牌认知与情感诊断”，
      将 branded 问题的提及、顺位、情感和原文证据句单列，并明示描述准确性/
      时效性需人工复核；头版所有数字显式关联 RUN ID。
- [x] 报告与方案说明将官网结论收敛为“本次抓取的 15 页范围内未发现”，
      不再从小样本推导全站绝对结论；方案说明新增 branded vs unbranded
      的行业共识、vanity metric 风险和运行数字溯源。
- [x] `question_gen` prompt 明确禁止 regional/category 包含品牌名/别名；
      第一次 6 题真实 DeepSeek 小样本仍出现 1 题错标，证明不能只信 prompt。
      新增确定性后置契约：文本命中品牌的非 brand tier 自动纠正为 brand；
      brand tier 却无品牌名时拒绝 LLM 输出并降级。第二次 6 题真实验证为
      `unbranded_leaks=0` / `branded_missing_name=0`，全程未输出密钥。
- [x] 新增 5 个回归用例，覆盖短品牌词边界、错 tier 纠正、双分层独立聚合、
      旧 JSON 默认加载和 prompt 约束；当前全量 `33 passed`。

### 决策记录（查询分层）
- 不删除/改名顶层 VisibilityMetrics 旧字段：它们继续保存全样本口径以兼容
  已有缺口/建议规则与外部读取方；新报告和新平台对比只使用 `unbranded`
  切片作为推荐竞争力。
- 分层以“tier=brand **或**任一语言文本命中品牌名/别名”为硬规则；
  不依赖 LLM 的 tier 单一字段，是因为 f141d182 的 q02 和真实小样本都证明
  模型会错标。这是对冲刺指令的可复现加固，不改动已验收 Provider 和推荐规则。

### 下一步
1. 按追加指令第七部要求，本部分验收并 commit 后暂停向用户汇报；
2. 用户确认后再进入第二部：密钥历史审计、干净环境彩排和 README 现状注记。

### 用户续行授权与浏览器复试（2026-07-17）
- 用户明确决定：不等待 Fable5 额度恢复，由 Codex 继续按《追加指令》顺序开发；
  Fable5 恢复后再做独立复核，不把其当作当前阻塞条件。
- 用户要求重试报告视觉检查。复试事实：`file://` 被内置浏览器 URL 安全策略禁止；
  `http://127.0.0.1:8765` 在浏览器隔离环境中连接超时；改用 Mac 局域网地址后返回
  `ERR_BLOCKED_BY_CLIENT`。这是 Codex 内置浏览器的本地资源/网络隔离，不是 macOS
  桌面文件权限，也不是 report.html 加载失败的证据；用户无需额外提供文件权限。
- 因上述隔离，当前只能声称模板渲染、HTML 内容、JSON 溯源与回归测试通过；
  未把 Codex 内置浏览器的桌面/移动视觉 QA 冒充为通过。本机普通浏览器可由用户
  双击 `data/示例产物/report.html` 复核。

### 冲刺-P0 安全与可复现彩排
- [x] `.env` 历史审计：`git log --all -- .env` 命中 0 个 commit；任意层级 `.env`
      历史路径数为 0；当前 `.env` 未被跟踪且 `git check-ignore` 确认被忽略。
- [x] 三类密钥特征全历史审计：首次宽正则在 17 个 commit 中命中，没有直接打印内容；
      仅输出文件路径定位到 `fixtures/site_snapshot/robots.txt`，再经脱敏上下文确认是
      公开 URL slug 中的 `sk-` 子串误报，不是 key。加入“前一字符不能是字母数字”的
      边界后，OpenAI/DeepSeek `sk-...`、Gemini `AIza...`、FreeModel `fe_oa_...`
      在 `git rev-list --all` 全部历史中命中 **0 commit**；结论为零泄漏。
- [x] 干净环境彩排：从 commit `64b24ba` clone 到新的临时目录，使用 Python 3.10.6，
      严格按 README 新建 `.venv` 并重新安装 `requirements.txt`，复制 `.env.example`
      且不填 key，执行 `--mock` 得到 20/8/7/7；随后 `33 passed`，clone 工作树为干净。
      仅出现 pip 版本升级提示，不影响三步运行，无 README 摩擦点。
- [x] README 在 `--providers auto` 命令后增加当前真实边界：OpenAI 官方 API
      账户无 credits，Gemini 普通生成可用但 Search Grounding 429；无对应额度/权限时
      优先 `--mock` 或显式选择已可用平台，避免评审者直接跑 `auto` 遇到可预知 429。

### 下一步（用户已授权连续执行）
1. 提交安全与可复现彩排的独立 commit；
2. 直接进入第三部：新建 `SUBMISSION.md` 评审导览页，不再等待 Fable5 确认。
