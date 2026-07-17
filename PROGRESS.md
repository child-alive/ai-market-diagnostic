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

### 冲刺-P0 SUBMISSION.md 评审导览
- [x] 新建仓库根目录 `SUBMISSION.md`，以“打开真实示例报告 → 读方案说明 →
      可选三步运行 Mock → 可选在线演示”组织 10 分钟评审动线；在线 URL 明示为
      第六部署后回填，当前不伪造链接。
- [x] 直答题目第八部分四问：完成了什么 / 为什么这样设计 /
      哪些是真实、模拟或简化 / 下一步做什么；边界表明确列出 DeepSeek `f141d182`
      真实链路、Mock fixtures、OpenAI/Gemini 429、15 页抓取范围、机器证据预审与单轮样本限制。
- [x] 增加范围叙事：最低交付已独立完成；Stage 4 与冲刺阶段各项为可选增强、
      彼此独立完整，避免评审者把增强路线误读为主链路未完成。
- [x] README 项目文档索引增加 `SUBMISSION.md`，评审者从仓库首页可直接找到导览。

### 下一步
1. 验证导览页的相对链接、mock 命令与回归基线后提交独立 commit；
2. 进入第四部 A/B：site_audit 领域能力补齐与指标/文档层升级。

### 冲刺-P1 第四部 A：GEO 站点审计增强
- [x] `SiteAuditResult` 只增带默认值字段，新增 8 个 AI 访问 token 的 robots.txt
      逐项状态、规则来源（专用 / `User-agent: *` / 未声明）与用途分类；旧 JSON / SQLite
      因 `advanced_checks_completed=false` 继续兼容，历史报告不会用默认 false 冒充实测。
- [x] 用途区分为训练/数据采集、搜索/引用，以及“训练 + Grounding”混合控制。
      GPTBot、ClaudeBot、Bytespider、CCBot 归训练/数据采集；OAI-SearchBot、
      ChatGPT-User、PerplexityBot 归搜索/引用；Google-Extended 单列为混合控制 token。
- [x] 增加 `/llms.txt` 与 `/llms-full.txt` 检测，并拒绝把返回 200 的 HTML soft-404
      误判为有效文本文件；报告明确说明该约定非强制标准，缺失不等于 AI 无法抓取。
- [x] 增加原始 HTML 正文字符量、品牌实体、可能依赖客户端 JS、直接回答式段落与
      FAQPage/details/标题结构启发式；报告全部标注 HEURISTIC，不把预警写成确定事实。
- [x] 2026-07-17 实时官网验收：`run_id=a7ec0a37`，AI 回答为 Mock、网站为实时抓取，
      `pages_checked=15`、`snapshot_mode=false`；8 项均继承 wildcard 允许，未发现两个
      llms 文件；首页原始 HTML 正文约 24,824 字符且含品牌实体，未触发 JS 依赖预警；
      发现直接回答式段落，未发现 FAQ 结构。
- [x] 新增 4 个站点审计测试并扩展报告渲染断言；全量 `37 passed`；Mock 基线保持
      20 问题 / 8 回答 / 7 缺口 / 7 建议。

### 决策记录（AI crawler 口径）
- Google 官方文档确认 `Google-Extended` 同时控制未来 Gemini 模型训练与 Gemini Apps /
  Vertex AI 的部分 Grounding，且不是独立 HTTP user-agent。因此偏离最初“仅分两组”的
  简化清单，增加 `CrawlerPurpose.BOTH` 并在报告单列，避免错误归为纯训练爬虫。
- robots.txt 只证明声明规则的解析结果，不能证明 WAF/CDN、IP allowlist、验证码或运行时
  网络一定放行；报告不把 `ALLOW` 扩大解释为端到端抓取成功。
- OpenAI 官方文档 MCP 本会话不可用；按 `openai-docs` 技能尝试安装时，本机 Codex CLI
  内部二进制路径报 `ENOENT`，随后仅使用 OpenAI 官方 Help Center 页面作来源核验。
  这是文档工具环境问题，不影响项目代码、API key 或 Provider 状态。

### 交接连续性（Fable5 尚未复核）
- 用户再次明确：当前继续按《追加指令》开发，不等待 Fable5 额度恢复；Fable5 恢复后
  对本节及后续 commit 做独立复核即可，不需要猜测为何中途继续。
- Codex 内置浏览器无法访问 `file://`、loopback 与局域网本地服务的事实已在上文记录；
  这不是用户权限缺失。第四部 A 的验收依据为真实 HTTP 官网抓取、HTML 内容检查、
  模板渲染与自动化测试，不声称完成本地浏览器视觉 QA。

### 下一步
1. 提交第四部 A 的独立 commit；
2. 进入第四部 B：提及 vs 推荐、来源质量分层、采样方法论与术语对齐。

### 冲刺-P1 第四部 B：指标语义、来源结构与重复采样
- [x] `AnswerAnalysis` 只增默认字段 `brand_recommended` / `recommendation_assessed`；
      新分析明确区分“进入答案”与“被建议/进入推荐列表”。启发式采用保守证据句与
      推荐列表规则；普通事实描述不算推荐，否定建议优先排除；LLM JSON prompt 同步新增定义。
- [x] `VisibilitySegmentMetrics` 新增可空 `recommendation_rate`。新运行按 checked answers
      计算；旧 JSON 默认 `None` 不冒充 0，`--run-id` 可从已存回答原文确定性补算，
      不重新调用 API。报告头版、多平台表、问题地图与回答卡均同时展示 Mention / Recommendation。
- [x] `Citation.source_type` 增加规则分层：目标品牌官网、权威媒体/政府、电商、目录、
      论坛、其他；报告新增无品牌词 Source Mix，并明确“类型不是质量评分、不是证据支持”。
      SOV 文案同步说明它按回答级提及计算，不与 Share of Answer 混用。
- [x] 对 `run_id=f141d182` 历史原文重渲染：Unbranded Mention / Recommendation / SOV
      均为 0%；64 个来源的整体结构为官网 1、权威媒体/政府 9、电商 11、目录 25、
      论坛 3、其他 15；其中 38 个无品牌词来源中官网 0、权威 5、电商 7、目录 21、
      论坛 0、其他 5。结论限定为透明域名规则与该 run，不冒充逐句人工核验。
- [x] 新增独立 `python -m src.sampling_demo`：只允许 fixtures 中的无品牌词问题，
      默认 q05/q07/q08 各重复 3 次，保存每轮完整回答、Web Search URL、提及/推荐/
      顺位、来源类型与失败记录；不改主报告、不调用 OpenAI/Gemini、不写入密钥。
- [x] 2026-07-17 真实重复采样：DeepSeek `deepseek-v4-flash` 共 9/9 成功且 grounded，
      返回来源合计 61 URL、0 失败。三轮 Prompt Set 的 Mention Rate 与 Recommendation Rate
      均在 0%~33.3% 波动；q08 仅第 2 轮命中并推荐 Deli，顺位第 15，另两轮未提及。
      产物为 `data/示例产物/repeat_sampling.json`，明确标注 small demo / 非置信区间。
- [x] 新增推荐判定、否定/竞品误归防护、六类来源、推荐聚合与重复采样波动测试；
      全量 `45 passed`，Mock 基线继续为 20 / 8 / 7 / 7。

### 决策记录（第四部 B）
- Recommendation Rate 采用保守定义：宁可漏掉跨句代词式建议，也不把同段内对竞品的
  推荐错误归给目标品牌；这适合作为人工复核队列的稳定基线。生产环境可用标注集校准。
- Source Mix 按引用“条目”计数，不去重成域名数，因为同一来源在多题重复被检索本身就是
  叙事集中度信号；但报告同时避免把目录/媒体类别写成来源可信度结论。
- 追加指令写“若额度允许”再做重复采样。DeepSeek 已有验收额度且用户要求继续冲刺，
  因此实际执行 9 次请求；所有请求成功。该演示独立于主 `f141d182`，不回写或混算主指标。

### 下一步
1. 验证历史/新报告、示例产物、Mock 基线和 45 个测试后提交第四部 B；
2. 进入第五部 Query Fanout，只对无品牌词派生 3~5 个子问法并计算 Coverage。

### 冲刺-P1 第五部：Query Fanout
- [x] 数据契约只增向后兼容字段：`FanoutQuery` 保存父问题、双语文本、分支类型与
      Mock 标记；`FanoutMetrics` 独立保存父问题数、已生成/已检测分支、Mention /
      Recommendation 命中、Parent / Branch Coverage 与 Grounded Rate。历史报告缺少
      Fanout 字段时仍按空列表 / `None` 正常加载。
- [x] 父问题只从高价值 **unbranded** Prompt Set 中选取；真实模式用 DeepSeek JSON
      生成每题 3~5 个分支，至少覆盖 paraphrase / scenario / follow_up 三类，并在
      Pydantic 校验后执行品牌名和别名泄漏硬拦截、父问题归属/数量/类型/重复文本校验。
      生成或校验失败时使用确定性分支并标记 `is_mock=true`，不把降级内容伪装成真实生成。
- [x] Fanout 回答真实模式只由 DeepSeek Web Search 采样，Mock 模式只用 MockProvider；
      回答、分析、指标与主 Prompt Set 分开存储和展示，不改变顶层 Visibility、缺口或建议。
      CLI 新增显式开关 `--query-fanout`、`--fanout-parents`、`--fanout-branches`，默认关闭，
      因而普通运行不会增加 API 消耗。
- [x] 报告增加 Query Fanout 板块：4 张 Coverage / Grounded 指标卡、父问题、分支类型、
      双语问法、提及/推荐/顺位、来源数和真实/Mock 标记；文案明确 Coverage 不是搜索量、
      不是统计置信区间，也不混入主 Prompt Set 指标。
- [x] 2026-07-17 完整真实验收 `run_id=37b442ec`：主链路实时生成 22 问并回答 Top-8，
      3 branded + 5 unbranded；8/8 `search_grounded=true`，70 个来源 URL，0 Mock、
      0 结构化解析降级。Unbranded Mention / Recommendation / SOV 均为 0%，Citation
      Rate 100%；Branded Visibility 100%、Recommendation 66.7%、Average Position 1.0。
- [x] 同一运行从 q01 / q02 两个价值分 4 的无品牌词父问题派生 6 个真实分支，三类各 2；
      西语和中文文本中 Deli / 得力 / 别名泄漏为 0。6/6 分支完成 Web Search，返回
      66 个来源 URL，0 Mock；Parent Fanout、Branch Mention、Branch Recommendation
      Coverage 均为 0%，Grounded Rate 100%。
- [x] 同一运行的无品牌词主回答共 37 个来源条目：目标品牌官网 0、权威媒体/政府 3、
      电商 0、目录 5、论坛 0、其他 29。主无品牌词与 Fanout 同时未命中，支持“当前
      DeepSeek 小样本中尚未进入通用需求叙事”的限定判断；两组样本仍是同平台同日观测，
      不冒充 ChatGPT/Gemini 结果、独立重复验证或统计置信区间。
- [x] SQLite 历史恢复实测：`.venv/bin/python -m src.main --run-id 37b442ec` 成功，
      原生成时间、Fanout 数据、指标和报告板块均保留，不重新调用 LLM / Web Search / 官网。
- [x] 新增 5 个测试，覆盖父问题选择、三类分支、品牌泄漏拦截、Coverage 公式与 Mock
      主链路隔离；全量 `50 passed`。默认 Mock 基线继续为 20 / 8 / 7 / 7；显式 Mock
      Fanout 为 2 父问题 / 6 分支，主回答仍为 8 条。
- [x] `data/示例产物/report.json` / `report.html` 已固化为 `37b442ec`；JSON 闸门逐项验证
      22/8 主链路、70 主来源、0 Mock/降级、5 条无品牌词、6/6 真实 Fanout、66 分支来源、
      0 品牌泄漏、15 页非快照进阶官网审计。默认 Mock 再跑通过且保持 20 / 8 / 7 / 7；
      `git diff --check` 通过，密钥特征扫描只有 `desk-organizer` 路径触发宽松 `sk-` 子串
      误报，增加非字母左边界后为 0 命中。

### 决策记录（第五部）
- Query Fanout 采用“独立切片”而不是追加进主 `questions/answers/metrics`。原因是它是
  围绕少量高价值父问题的扩展抽样；若混入主分母会让同一父意图获得额外权重并破坏不同
  run 的可比性。该决定与追加指令的“输出 Fanout Coverage 并入报告”一致，仅改变存储位置。
- 真实分支生成失败时允许回退确定性模板，是为了让一次生成格式错误不拖垮主诊断；但回退
  必须逐条标记 Mock，报告显示 FANOUT MOCK，不能把真实回答建立在未披露的 seed 上。
- `37b442ec` 取代 `f141d182` 作为提交主示例：新 run 在同一可追溯报告内同时具备分层指标、
  进阶站点审计与真实 Query Fanout；旧 run 继续保留为“品牌词混算导致虚高”的审计案例。
- 用户已明确无需等待 Fable5 恢复额度；Fable5 后续应从本节及对应 commit 开始独立复核，
  无需重复运行真实 API。浏览器无法访问本机文件/端口仍是 Codex 浏览器隔离，不是用户权限。

### 下一步
1. 提交第五部独立 commit；
2. 进入第六部：回放模式优先的 Vue 3 + TypeScript 双受众演示网页，随后增加隔离的
   FastAPI 实况端点、限流/并发/超时降级与部署手册；不得破坏 CLI 和静态报告主件。

### 冲刺-P2 第六部：双受众演示网页与 ECS 部署交付
- [x] 新增独立 `web/` Vue 3 + TypeScript + Vite 项目并提交生产构建 `web/dist/`；
      `base=./`，静态资源与完整报告可在 IP:端口和子目录回放。`web/public/demo-report.json`
      完整复制真实 `37b442ec`，`full-report.html` 保留提交主件入口；前端不重算或改写指标。
- [x] 默认回放模式按 7 阶段自动推进：Prompt discovery → AI retrieval → Signal extraction
      → Site audit → Query Fanout → Gap analysis → Recommendations；提供暂停、继续、重置、
      逐阶段选择。首屏直接呈现“AI 认识 Deli，但不会主动推荐它”及 5 个主无品牌词 /
      6 个 Fanout 均 0 命中的限定洞察，不使用旧混算数字。
- [x] 产品 / 技术双视角：产品视角展示双语问题、回答摘要、分层指标、站点信号、Fanout、
      缺口和 P0/P1/P2；技术视角展开同阶段原始 JSON、run/provider/mode/mock 标记、来源链接
      与等价 CLI / 模块调用。窄屏与桌面响应式、键盘焦点和 reduced-motion 已处理。
- [x] `src.demo_api` 提供只读静态托管、`GET /api/health` 与
      `POST /api/live-diagnose/stream`；实况请求只接受 3~5 数量，不接受任意 Prompt 文本，
      固定从版本内高价值无品牌词选择，Key 只读服务端环境。前端只有显式点击后才调用。
- [x] `src.demo_worker` 在独立 Python 子进程中逐题调用 DeepSeek Web Search，以 JSON Lines
      送入 SSE；回答采用本地启发式分析，避免额外 LLM 抽取调用。总超时会 terminate / kill
      子进程，不出现客户端已失败但后台线程仍耗额度的情况；失败、断连和缺 Key 均引导回放。
- [x] 防护：每 IP 每小时 2 次滑动窗口、全局并发 1、默认 180 秒总超时、SSE no-store /
      no-buffer、64KB Nginx body 上限、安全响应头；部署固定 Uvicorn 单 worker，FastAPI
      只监听 `127.0.0.1:8000`。实况不写 SQLite、不覆盖示例产物、不混入主指标。
- [x] 新增 5 个零额度测试：固定高价值 unbranded Prompt Set 与品牌泄漏、Mock Worker
      JSON Lines 事件、缺 Key 503 fail-closed、3~5 输入上限、每小时两次滑动窗口。全量
      `55 passed`，测试不调用真实 API。
- [x] 本地 HTTP 验收：Uvicorn `127.0.0.1:8765` 下 `/`、`demo-report.json`、
      `full-report.html`、`/api/health` 均 200；健康页报告 replay/live 可用与 3~5 限制。
- [x] Codex 内置浏览器再次尝试后成功访问本机端口；默认窄屏与 1440×900 桌面均完成
      实际渲染，产品/技术视角与实况开关均可操作，控制台 0 error。首轮桌面截图发现标题
      末字孤行，收窄橙色副标题字号并重构建后修复。这说明先前失败是当时浏览器会话的
      隔离/连接状态，不是用户缺少 macOS 文件或网络权限；用户无需再授权。
- [x] 真实网页实况验收：2026-07-17 固定 q05 / q07 / q06，浏览器逐题收到 SSE；
      3/3 `WEB GROUNDED`，来源分别 3 / 7 / 10、合计 20，三题均未提及 Deli，最终状态
      `DONE`。该运行只验证网页链路，不保存原文、不回写 `37b442ec`、不混入任何主指标。
- [x] 新增 1200×630 社交预览图 `web/public/og.png`，文字、run_id、0% 指标与网站首屏
      人工核对一致；Vite 构建会复制到 dist，并在 Open Graph / X meta 中引用。
- [x] 新增 `deploy/deploy.sh`、`install_remote.sh` 与 `deploy/部署手册.md`：rsync 不上传/
      覆盖 `.env`，远端使用 Nginx 静态托管 + Systemd 单 worker FastAPI，支持 IP:端口、
      UFW 已启用时只追加必要端口，并给出 server-only Key 配置、健康检查与排错步骤。

### 决策记录（第六部）
- 追加指令原先写“实况 3~5 个无品牌词”，旧 PLAN 可选项曾写“输入品牌”。对公网演示
  采用更窄的固定 Prompt Set，不开放任意品牌/问题输入：可预测额度、防 Prompt 注入，也避免
  评审者把一次临场输入误解为可复现市场测量。PLAN Stage 4 对应项已同步为实际实现。
- 总超时使用可终止子进程而非 `asyncio.to_thread`：Python 无法可靠取消已进入 httpx 的
  后台线程，若超时后释放并发锁会形成隐藏并发；子进程才能在超时/断连时真正停止上游工作。
- 回放数据提交完整 `report.json` 而不是人为裁剪 JSON：技术视角和完整报告可追溯到同一
  run，避免回放层出现第二套口径；代价是 dist 较大，但 2 核 2G 静态托管可轻松承受。
- 使用站点构建技能后，首屏强化产品故事、补响应式/无障碍/生产构建与社交预览验收；没有
  引入 Sites 托管或 `.openai/hosting.json`，因为用户明确要求自有 ECS、IP:端口与用户执行
  部署。擅自发布到另一平台会偏离追加指令并产生未经请求的外部状态。
- 在线 URL 当前明确标为“用户部署后回填”，不把本机 `127.0.0.1` 冒充公网交付；静态
  `report.html` 继续是主件，网页是彼此独立的 Stage 4 / 冲刺增强。
- Fable5 恢复后应从 commit `39572fa` 与本节对应网页 commit 开始独立复核；无需重复
  真实 3 题实况，否则会额外消耗额度并触发每 IP 限流。

### 下一步
1. [x] 最终闸门完成：从 `npm ci` 干净安装后 Vite 生产构建成功；`55 passed`；默认
   Mock 为 20 / 8 / 7 / 7；两个 shell 脚本 `bash -n` 通过；public/dist 与
   `data/示例产物` 字节一致；dist JSON 为 `37b442ec` 的 8 主回答 / 6 Fanout；OG 图
   为 1200×630；本地 HTTP/health/静态图均成功；密钥特征 0 命中；`git diff --check` 通过。
2. 提交第六部独立 commit；
3. 用户有 ECS 公网 IP / SSH 后执行部署脚本，把 URL 回填 `SUBMISSION.md`。

---

## 2026-07-17 session-04 (Codex，Lumio 中转站兼容性验收)

### 开工与基线
- [x] 按协议重新完整阅读 `PLAN.md` → `PROGRESS.md` → `src/models.py`；接手时工作树干净。
- [x] Mock 基线通过：20 问题 / 8 回答 / 7 缺口 / 7 建议。

### Stage4-T7 — Lumio 中转站兼容性诊断与报告
- [x] 网关 `https://api.lumio.games/` 在线；未鉴权 `/v1/models` 返回 401，并声明支持
      Bearer、`x-api-key` 与 `x-goog-api-key`。测试密钥只经隐藏回显的交互式进程传入，
      未写入 `.env`、源码、日志、报告或 Git。
- [x] GPT 密钥可见 20 个路由模型，`gpt-5.4` 普通 Chat Completions 返回 200 和预期正文；
      Gemini 密钥可见 5 个路由模型，`gemini-3.5-flash` 普通生成返回 200 和预期正文主体。
- [x] GPT `web_search_options` 请求返回 200，但 `annotations=0`，并把 2025-08-07 的文章误报为
      2026-07-17 时点的最新 OpenAI News；OpenAI 官方 News 页已列出 2026-07-16 等新内容，
      该搜索结果被交叉核验明确证伪。正文残留不可解析的内部 citation token。
- [x] GPT `/v1/responses` 对普通请求和 `web_search` 工具请求均返回 200 / `application/json`，
      但正文为 0 字节，当前不可用。
- [x] Gemini 携搜索参数连续两次返回 200，但 message 只有 role，正文为空且无 annotations；
      `/v1/interactions` 与 `/v1beta/interactions` 均为 404，未暴露官方 Google Search Grounding 契约。
- [x] 新增 `docs/Lumio中转站API验收报告.md`，完整记录验收口径、端点、模型列表、逐项结果、
      官方页面交叉核验、风险和给 Fable5 的复核重点；全文不含任何密钥。

### 决策记录（Lumio）
- 不将 Lumio 接入现有 `openai` / `gemini` Provider，也不把普通生成结果记入官方平台切片：
  当前只证明第三方网关能返回对应模型名称与文本，未证明上游身份、联网工具执行、当前信息新鲜度
  或原生引用契约。该决定延续此前“普通代理不得冒充官方平台”的测量口径。
- 若未来使用，只能新增独立的 `lumio_gpt` / `lumio_gemini` 第三方普通生成标签；但它对本项目
  的联网 GEO 目标没有足够增量价值，因此本次不改代码、不扩大范围。
- 用户在对话中直接提供过两把 Lumio 密钥。仓库中未保存；测试完成后建议用户在服务商后台轮换。

### 下一步
1. Fable5 可直接审阅 `docs/Lumio中转站API验收报告.md`，无需重复消耗 API；
2. 若服务商后续提供公开的搜索工具与结构化 citation 契约，只做单题复验，成功前不跑 Top-8；
3. 当前提交主示例继续使用已真实验收的 DeepSeek `run_id=37b442ec`。

---

## 交接说明（session-04 结束，Codex → Claude Fable5 独立复核）

### 当前状态
- [x] 用户决定 Lumio 中转站作为小插曲结束，不接入、不继续研究；验收报告保留供审计。
- [x] 新增根目录 `FABLE5_REVIEW_HANDOFF.md`，汇总 Fable5 在 `98d00f9` 暂停后完成的 8 个 commit、
      真实/模拟边界、测量口径、代码热点、零额度复核命令和期望审核输出格式。
- [x] 交接前最终闸门通过：`55 passed`；Mock `20 / 8 / 7 / 7`；历史真实 run `37b442ec`
      重渲染成功；部署脚本语法通过；`web/dist` 三个主入口存在；工作树在文档修改前为干净状态。

### 给 Fable5 的明确任务
1. 先独立审核，不直接重构；按 P0/P1/P2 给文件级证据和最小修复建议；
2. 优先核对 branded/unbranded、Mention/Recommendation、Citation/证据支持、主样本/Fanout/
   重复采样四组边界，以及 `37b442ec` 在所有交付物中的数字一致性；
3. 零额度复核即可：禁止读取 `.env`、重复真实 API、中转站测试或网页实况；
4. 判断当前是否“可提交 / 小修后提交 / 存在阻断问题”，再由用户决定是否授权修改。

### 当前剩余外部动作
- Fable5 独立审查；
- 用户自行核验报告与网页观感；
- 如需公网展示，等待用户提供 ECS 信息并授权部署后回填 `SUBMISSION.md` URL；
- OpenAI/Gemini 官方联网只在额度/权限恢复后做单题冒烟，成功前不跑全量。

---

## 2026-07-17 session-05 (Claude Fable5，独立复核 + 最终收尾)

### 独立复核结论（复核 Codex session-03/04 全部 8 个 commit）
- [x] 总裁决：**可提交**。P0/P1 发现 0 项；P2 三项（引用率语义易误读、analysis.py 旧注释、
      URL 占位决定），已转化为下方用户批准的收尾任务
- [x] 独立复跑安全审计：`.env` 全历史 0 commit；三类密钥特征（带边界规则）全历史 0 命中
- [x] 零额度基线：55 passed；mock 20/8/7/7；`--run-id 37b442ec` 重渲染成功；部署脚本语法通过；
      `web/dist` 回放数据与 `data/示例产物` 字节一致
- [x] 数字一致性：22/8、3 branded + 5 unbranded、Unbranded 0%、Branded 100%/66.7%/1.0、
      70+66 来源、Fanout 2 父/6 分支 0 泄漏、15 页实抓——在 JSON/README/方案说明/SUBMISSION/网页五处一致
- [x] 确认 37b442ec 的 Fanout 父问题 q01/q02 为无品牌词（与旧 fixtures 同 id 纯属巧合，无泄漏）

### 收尾任务（用户批准清单，逐项独立 commit）
- [x] 收尾-1 消歧"引用率 100%"：确认 citation_rate 定义 = 带 ≥1 个 Web Search 来源 URL 的
      回答占比（与用户推测一致）。显示层统一改为"来源覆盖率 Source Coverage (Citation Rate)"
      并附"非品牌被引用比例"定义：报告指标卡+跨平台表头、网页两处、方案说明 §1/§2.3/§3.1、
      README 术语行+FAQ、SUBMISSION 边界表。JSON 字段名 citation_rate 不动（契约）。
      重渲染 37b442ec（report.json 字节不变）、重建 web/dist 并验证同步；55 passed；mock 20/8/7/7
- [x] 收尾-2 头版"单轮样本"角标：执行摘要卡 + 指标区标题加统一角标
      "单平台单轮采样 · 无品牌词 N 题 (+ Fanout 分支 M 题) · 观测值非定论"，题数随数据自适应
      （37b442ec 显示 5+6，mock 显示 7）；网页 hero scope-note 同步统一措辞并带题数。
      重渲染 37b442ec、重建 dist 并验证同步；55 passed
- [x] 收尾-3 更新 analysis.py 模块注释为分层后口径（旧注释仍是分层前五指标说法）
- [x] 收尾-4 部署方案定稿：核对 Nginx 单端口三路由——根路径 Vue dist ✓、/api 反代 FastAPI(SSE 配置) ✓、
      新增 `location = /report` 302 直达 full-report.html；`.env` 收紧为 root:root 600
      （systemd 以 root 读 EnvironmentFile 后降权，服务进程无需读权限），部署手册同步；
      rsync 继续排除 .env；新增 deploy/上线前检查单.md（安全组/防火墙/自启/限流验证/外网自测五段）
- [x] 收尾-5 SUBMISSION.md 在线演示占位行保留，加 HTML 注释提醒标记：部署后回填 IP:端口，
      最终不部署则删除整个第 4 步（注释不影响 Markdown 渲染，评审者不可见）
- 按用户指令：收尾五项完成后暂停；演示网页视觉/交互调整等用户具体清单，不自行发挥

**收尾五项全部完成 ✅（40 commits，工作树干净）**

---

## 2026-07-17 session-06 (Codex，网页冲刺：性能预算)

### 性能预算与零外部依赖
- [x] 冲刺前基线确认：55 passed；Mock 20/8/7/7；网页生产构建成功
- [x] 移除 Google Fonts 阻塞请求，统一改用系统字体栈；Vue 首屏无外部 CDN/字体依赖
- [x] 移除完整报告中的 ECharts CDN，以无依赖 CSS 条形图保留同一组 SOV 数据和无障碍描述
- [x] 技术视角、实况模块、原始 JSON 查看器改为按需异步加载；首屏增加 CSS 骨架
- [x] 构建后为 HTML/CSS/JS/JSON 生成 gzip 预压缩文件；Nginx 启用 `gzip_static`
- [x] 生产构建预算：首屏主 JS 33.74KB gzip（预算 300KB）；首屏 5 请求（预算 15）
- [x] Chrome Lighthouse 12.8.2 实测：DevTools 实际节流、4× CPU、150ms RTT、1600Kbps、
      1440×900；增加首屏数据 preload 后连续两次 LCP 1871.325/1872.442ms（预算 2500ms），
      CLS 0.0014、TBT 126.879ms、总传输约 90KiB
- [x] 原始性能报告与口径保存至 `web/performance/`；`deploy/install_remote.sh` 语法通过；
      页面 DOM 可读、控制台无已发现的运行时阻断

### 决策记录
- 使用项目内纯 Node 构建后脚本生成 `.gz`，不新增运行时或开发依赖；原因是当前 TypeScript
  配置未引入 Node 类型，为预压缩额外扩展依赖树不划算。
- 完整报告的 SOV 图是固定示例产物，仅需呈现 8 个确定值；改用 CSS 图表比整包加载 ECharts
  更符合性能预算，数值、排序和可访问语义保持不变。

### 下一步
- 网页冲刺第二批：国内/国际双构建、`/report` 路由、Cloudflare Pages 指引与提交入口双 URL。

---

## 2026-07-17 session-07 (Codex，网页冲刺：双版本构建)

### 国内动态版 / 国际静态版
- [x] 新增 `domestic` / `international` 两套 Vite mode：国内版启用 `/api` 实况；国际版在
      构建时关闭实况入口，未生成 LivePanel chunk，也不会主动请求 `/api`
- [x] `npm run build:all` 同时产出 `web/dist` 与 `web/dist-intl`；两者均生成 gzip 预压缩文件
- [x] 构建后将自包含完整报告复制到 `/report/index.html`；国内、国际预览的 `/report/` 均验收通过
- [x] 国内版预览确认实况按钮可用；国际版确认禁用按钮、静态边界说明和国内版引导文案存在
- [x] 新增 Cloudflare Pages 国际版指引；ECS/Nginx 改用国内构建并统一 `/report/` 路由
- [x] `SUBMISSION.md` 拆成国内动态版 / 国际静态版双 URL 占位，保留部署前不虚构公网地址的口径
- [x] 两套生产构建、桌面浏览器 DOM、报告路由与控制台检查通过；国际版构建未发现 `/api` 字面量

### 决策记录
- 国际版不提供“点了再报错”的假实况按钮，而是在构建期关闭功能并解释如何前往国内版；这样
  Cloudflare Pages 无需后端或密钥，部署边界与用户预期一致。
- `/report/` 由构建脚本复制自同一份 `full-report.html`，不维护第二套报告模板，避免数据漂移。

### 下一步
- 网页冲刺第三批：评审者证据卡、问题式叙事、产品/技术 URL 状态、回放速度与跳过、移动端与元信息。

---

## 2026-07-17 session-08 (Codex，网页冲刺：评审叙事与视觉交互)

### 评审者语言与问题式叙事
- [x] Hero 增加产品定义，保留“AI 认识 Deli，但不会主动推荐它”结论；首屏同步展示
      无品牌词提及 0%、品牌词可见度 100%、官网西语内容 0 页及单轮样本边界
- [x] Hero 后新增“写给评审者”六张证据卡：业务理解 / 拆解能力 / 范围控制 / 交付物 /
      工程意识 / 独立判断，一项不少，每卡直达对应证据锚点
- [x] 新增“范围与取舍”：核心链路优先真实验收，网页、SQLite、多平台、部署均为独立可拔插增强
- [x] 页面按自然问题重排：这是什么与结论 → 六项评分证据 → 怎么得出 → 范围与取舍 →
      交付物/工程保障 → 边界 → 下一步；板块标题均为问题句或直接答案
- [x] 产品视角的指标补人话副标签与原生悬浮解释；明确来源覆盖率不是逐句事实核验，
      Fanout 仍保持主样本之外的独立小样本口径

### 交互、移动端与细节
- [x] 产品/技术视角写入 `?view=product|technical`；浏览器点击实测技术面板懒加载且 URL 可分享
- [x] 回放增加 1×/2× 加速与“跳到结论”，实测状态切换成功；动效仅使用 transform/opacity，
      保留 `prefers-reduced-motion` 降级
- [x] 390×844 手机竖屏检查：document/body scrollWidth = 390，无横向溢出；证据卡、范围卡、
      路线图均单列，工具栏自动换行；QA 截图保存至 `web/qa/`
- [x] 桌面 1280px 检查：六卡 3×2、页面 scrollWidth = clientWidth；国内/国际版控制台零报错零警告
- [x] 新增本地 SVG favicon、强化 title/meta description、自包含 404；Nginx 未知路径落到 404，
      `/report/` 保持独立路由
- [x] Cloudflare 指引按 2026-07-17 官方文档改为 Direct Upload 拖拽优先，并保留 Git 自动构建备选
- [x] 全部视觉增量后重新过性能闸门：LCP 1971.537ms、初始 JS 36.37KB gzip、5 请求、
      总传输约 94KiB、TBT 122.739ms、CLS 0.0014

### 直观性验收边界
- 代码/浏览器代理检查通过：首屏同时出现产品定义与核心洞察；下一屏首标题即“写给评审者”，
  六卡和完整报告入口可在 DOM/截图中直接定位。
- **真人 10 秒/20 秒复述仍待用户找一位不懂技术的人执行。** Codex 不冒充真实受试者；
  复述目标分别为“这是诊断工具，发现 AI 认识 Deli 但不主动推荐”和“指出评审者板块与报告入口”。

### 下一步
- 最终 QA、网页冲刺完成报告、全量回归与提交前移交。

---

## 2026-07-17 session-09 (Codex，网页冲刺最终 QA 与移交)

### 最终闸门
- [x] 输出 `deploy/网页冲刺完成报告.md`：改动、前后体积、双线路产物、验收与遗留事项齐全
- [x] 国内 / 国际 `build:all` 通过；`dist/`、`dist-intl/`、两端 `/report/`、404 与 gzip 产物完整
- [x] 55 passed；Mock 基线 20/8/7/7；部署脚本语法与 Git diff 空白检查通过
- [x] 国内/国际桌面控制台零 error/zero warning；国际版无 LivePanel chunk、主资源无 `/api`
- [x] 最终性能：LCP 1971.537ms、JS 36.37KB gzip、5 请求，全部在预算内
- [x] QA 图：桌面 hero、六项评审证据、390px 手机首屏均已入库

### 移交状态
- 网页冲刺代码任务完成；部署仍由用户执行，待两个公网 URL 后回填 `SUBMISSION.md`
- 真人 10/20 秒复述待用户外部执行；机器代理检查不冒充真人结果
- Fable5 可从 commits `8b934d5` → `d4c39ef` → `60c4683` 及本节继续独立审核，无需猜测中间状态

---

## 2026-07-17 session-10 (Codex，用户评审后的双视角重构)

### 反馈核查与根因
- [x] 按用户指定重新核对测试题 DOCX，第六部分六项考察原文成为产品视角的信息架构；
      不再用内部开发判断代替 HR 的查看目标。
- [x] 定位“报告仍跳到 5173”为旧 Vite 开发进程残留：5173 已停止，当前只保留 8766
      生产预览；页面报告链接改为当前页面同源绝对 `/report/`，浏览器实测命中
      `http://127.0.0.1:8766/report/` 并加载自包含完整报告。
- [x] 明确国内 / 国际不是按访问者网络自动判断。它们是同一前端的两个显式部署 URL，
      内容和报告相同，仅实况 API 能力不同；另一条 URL 未回填时不展示无效跳转。

### 双受众重构
- [x] 新增独立 `ProductView.vue`：只保留产品定义、核心洞察、测试题六项原地下拉、
      七步业务流程、前三项行动建议与完整报告入口。
- [x] 新增独立 `TechnicalView.vue`：只保留七模块架构、数据追踪、可靠性边界、部署能力、
      实况入口与复现命令；切换后产品 Hero / 内容不会残留在 DOM。
- [x] 顶部改为固定吸顶受众导航，清楚标注“给 HR / 产品经理”与“给技术评审”；
      `?view=product|technical` 继续支持分享指定视角。
- [x] 删除产品视角中独立的“核心链路先完成，增强项不反客为主 / 范围与取舍”等内部自述；
      范围控制只在测试题对应下拉中用一句结论和两条证据回答。

### 交互与线路修复
- [x] Hero“从头播放诊断过程”重置为 1/7、恢复播放、触发内容过渡并滚动到流程区；
      浏览器从第 4 步点击后实测回到第 1 步且按钮变为“暂停”。
- [x] 六项考察改为原生 `details` 下拉；点击“合理控制范围”原地展开对应回答，不再锚点跳转。
- [x] 进度条按第一个与第七个节点圆心绘制；1280px 实测左右端点偏差均为 0px、垂直偏差 1px；
      节点增加 hover 抬升、光晕和 active 状态。
- [x] 线路说明改为右上角可展开状态菜单；当前能力、非自动切换规则与 URL 未配置状态均直接可见。

### 最终闸门
- [x] `npm run build:all` 通过；国际静态产物未生成 LivePanel chunk；国内 / 国际 `/report/` 齐全。
- [x] Vue TypeScript 检查通过；55 passed；Mock 基线 20 / 8 / 7 / 7；部署脚本语法通过。
- [x] 浏览器实测：产品 / 技术 DOM 完全互斥；报告链接全为 8766 同源；六项下拉、重播、
      线路说明成功；1280px 与 390×844 均无横向溢出；报告页标题和真实 run 正确。
- [x] 双视角重构后 Lighthouse 同口径复测：LCP 2154.995ms、TBT 31.838ms、CLS 0、
      5 请求、约 92KiB；主 JS 34.36KB gzip、CSS 6.13KB gzip，全部在既定预算内。

### 决策记录
- 保留国内动态 / 国际静态两套构建产物，但在 UI 中整合为同一套内容与明确线路状态；不做
  客户端 IP/网络嗅探自动切换，因为它不可预测、难解释，也会让静态站错误承诺实况能力。
- 产品与技术不是同页显隐几个字段，而是两个组件、两种叙事和两套视觉系统；共享的只有
  顶部导航与同一份 Report 数据，避免对不同评审者重复或混杂表达。
- 未回填真实公网 URL 时不显示“前往另一版”，防止再次出现评审者不知道链接去哪里的情况。

### 给 Fable5 的复核重点
1. 对照测试题第六部分，检查产品视角六项标题是否逐字覆盖、证据是否直接；
2. 检查产品 / 技术切换是否确为两套信息架构，而非样式级显隐；
3. 检查动态 / 静态线路说明是否诚实，不把本地端口或空 URL 当公网入口；
4. 无需调用任何真实 API；只需构建、Mock、浏览器回放与 `/report/` 路由复核。
