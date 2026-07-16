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
- **本机没有 DEEPSEEK_API_KEY**：hybrid 真实链路（question_gen LLM 生成、DeepSeekProvider、
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

### 下一步
1. Stage3-T3 README 定稿；
2. Stage3-T4 补充约 10 个 pytest 用例并跑全量验收。
