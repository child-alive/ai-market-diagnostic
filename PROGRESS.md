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
