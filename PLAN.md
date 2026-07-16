# AI 海外市场诊断智能体 — 总体开发规划（PLAN.md）

> 本文档是本项目的唯一权威规划。任何执行本计划的 AI 编码助手（Claude Code / Codex / 其他）
> 必须先完整阅读本文档与 `PROGRESS.md`，再开始工作。
> 所有工作按 Stage 顺序推进，**每完成一个任务立即更新 `PROGRESS.md`**（协议见 §11）。

---

## 0. 项目背景（30 秒版）

这是一道求职开放测试题：为出海企业构建"AI 海外市场诊断智能体"原型。
输入品牌 + 目标市场，系统需回答三个问题：

1. 目标市场用户在问什么，哪些问题品牌尚未覆盖（问题发现 + 缺口分析）
2. 品牌在 ChatGPT / Google 等 AI 回答中是否出现、竞品是谁、引用来源是什么（AI 可见度）
3. 品牌官网是否适合搜索引擎与 AI 抓取、理解、引用（网站诊断）

演示用例（题目给定）：品牌 = 得力 Deli，市场 = 墨西哥，语言 = 西班牙语，品类 = 文具/办公/学生用品。
示例问题：`¿Cuáles son las mejores marcas de papelería en México?`

出题公司（聚路国际）的商业产品就是 GEO（生成式引擎优化）诊断报告，其产品指标体系为：
**Visibility（可见度）、Citation Rate（引用率）、Share of Voice（话语权）、Sentiment（情感倾向）、
Average Position（平均排名）、Query Fanouts（问题分支）**，问题分类采用
**品牌词 / 地区排名词 / 全国(品类)排名词** 三层，漏斗标注 **TOFU / MOFU / BOFU**。
👉 **本项目的指标命名与报告结构刻意对齐上述体系**——这是核心差异化策略之一。

---

## 1. 总体策略（为什么这样做）

**策略 A｜评分导向开发。** 一切优先级服从题目"第六部分：重点观察什么"，映射表见 §2。
功能多不加分，命中评分点才加分。

**策略 B｜MVP 先行，每个 Stage 结束时项目都处于"可演示"状态。**
预算/额度随时可能中断，因此绝不允许出现"做了一半、无法演示"的中间态。

**策略 C｜三板斧差异化：**
1. 报告指标体系与出题公司产品对齐（证明业务理解，而非堆砌技术）；
2. Provider 抽象层 + 显式标注 Mock（证明工程意识与诚实取舍）；
3. 交付一份自包含 `report.html` 诊断报告（零部署、可直接发给面试官打开，前端能力展示）。

**策略 D｜"独立判断"单独成章。** 方案说明中必须有专门章节指出数据与平台限制（清单见 §9），
这是评分点中最容易被其他候选人忽略的一条。

---

## 2. 评分点 → 交付物映射表（开发时对照自检）

| 题目考察点 | 在本项目中的落点 |
| --- | --- |
| 真正理解业务问题，不堆砌技术名词 | 指标体系对齐 GEO 行业术语；方案说明用"客户视角"叙述 |
| 把模糊需求拆成清晰的模块、数据和流程 | §4 架构图 + §6 数据契约 + 六个独立 pipeline 模块 |
| 合理控制范围，并解释为什么先做这些 | 方案说明"范围与取舍"章节 + 本文档 Stage 划分 |
| 交付物清楚、可查看、可运行、可迭代 | README 一条命令跑通；report.html 双击可看；模块化可扩展 |
| 代码结构、数据设计、错误处理、工程意识 | Pydantic 全链路 schema；Provider 抽象；重试/降级/缓存 |
| 独立判断（不确定性、数据限制、平台限制） | 方案说明"限制与不确定性"章节（§9 清单） |

---

## 3. 锁定的技术决策（执行者不得擅自更换，除非记录理由到 PROGRESS.md）

| 项 | 决策 | 理由 |
| --- | --- | --- |
| 语言/框架 | Python 3.10+，FastAPI（仅 Stage 4 暴露 API；此前以 CLI pipeline 为主） | 候选人已有 FastAPI + LLM 项目经验，叙事一致 |
| LLM | DeepSeek API（`deepseek-v4-flash`） | 当前可用的 V4 模型；国内可直连，候选人已有使用经验 |
| LLM/搜索抽象 | `AnswerProvider` 接口：`DeepSeekProvider`（V4 + 原生 Web Search）+ `MockProvider`（fixtures 回放） | 真实回答携带搜索来源，演示仍可复现；未来接 ChatGPT/Gemini 只需新增实现类 |
| 存储 | SQLite（单文件 `data/diagnostic.db`）+ JSON 产物落盘 | 零依赖、可提交示例数据库 |
| 报告 | Jinja2 模板渲染自包含 `report.html`（内嵌 JSON + CDN 引入 ECharts） | 零部署可演示；Stage 4 才考虑 Vue 交互版 |
| 抓取 | `httpx` + `selectolax`（或 BeautifulSoup），限速 ≤1 req/s，仅抓 ≤15 页 | 轻量、礼貌抓取；失败自动降级到本地快照 |
| 配置 | `.env`（提供 `.env.example`），`DEEPSEEK_API_KEY` 缺失时全链路自动切 Mock | 评审者没有 key 也能跑通 demo |
| 依赖管理 | `requirements.txt` + venv，不用 poetry | 降低评审者运行门槛 |

---

## 4. 系统架构与数据流

```
输入: BrandProfile(品牌, 品类, 目标市场, 语言, 官网URL, 竞品种子[可选])
  │
  ├─① question_gen      DeepSeek 生成 20~30 条西语用户问题
  │                      按三层分类(品牌词/地区排名词/品类排名词) + 漏斗(TOFU/MOFU/BOFU)
  │                      + 商业价值评分(1~5, 附一句理由)
  │
  ├─② visibility_check  对 Top-N(默认8~10)问题逐条调用 AnswerProvider 获取"AI回答"
  │                      MockProvider: 回放 fixtures/answers/*.json
  │
  ├─③ answer_analysis   对每条回答做结构化抽取(用 DeepSeek 二次解析, JSON mode):
  │                      品牌是否被提及/排名位置/竞品清单/引用来源/情感倾向
  │                      → 聚合指标: Visibility% / SOV / Avg Position / Citation / Sentiment
  │
  ├─④ site_audit        对官网做轻量诊断(robots.txt, sitemap, hreflang es-MX,
  │                      schema.org/JSON-LD, title/meta, 是否存在西语内容, 可抓取性)
  │                      网络失败 → 读取 fixtures/site_snapshot/ 并在报告标注"快照模式"
  │
  ├─⑤ gap_analysis      综合 ①②④ → 内容缺口清单(缺少的页面类型/主题, 各附证据链)
  │
  ├─⑥ recommendations   优先级行动建议 P0/P1/P2, 每条 = 行动 + 理由 + 预期影响 + 工作量
  │
  └─⑦ report            全部结果汇成 DiagnosticReport(JSON) → 渲染 report.html
```

模块间只通过 §6 的 Pydantic 模型传递数据；每个模块可独立运行、独立测试。

---

## 5. 目录结构（Stage 0 建立，此后保持稳定）

```
ai-market-diagnostic/
├── PLAN.md                  # 本文档
├── PROGRESS.md              # 进度与决策日志(交接核心)
├── README.md                # 运行说明(评审者视角, 3步跑通)
├── docs/方案说明.md          # 需求理解/架构/取舍/限制(最终提交主文档)
├── .env.example
├── requirements.txt
├── src/
│   ├── models.py            # 全部 Pydantic 数据契约
│   ├── config.py            # env 加载, mock/real 模式判定
│   ├── providers/           # base.py / deepseek.py / mock.py
│   ├── pipeline/            # question_gen.py / visibility.py / analysis.py
│   │                        # site_audit.py / gaps.py / recommend.py
│   ├── report/              # render.py + templates/report.html.j2
│   ├── storage.py           # SQLite 读写
│   └── main.py              # CLI 入口: python -m src.main --brand deli --mock
├── fixtures/                # mock 数据(答案样本/官网快照/问题种子)
├── data/                    # 运行产物(db, json, report.html) — gitignore, 但提交一份示例
└── tests/                   # Stage 3 起补充; 至少覆盖 analysis 的解析逻辑
```

---

## 6. 核心数据契约（models.py，字段可增不可随意改名）

```
BrandProfile:    brand_name, brand_aliases[], category, market, language,
                 website_url, seed_competitors[]
UserQuestion:    id, text_local, text_zh, tier(brand|regional|category),
                 funnel(TOFU|MOFU|BOFU), value_score(1-5), value_reason
AIAnswer:        question_id, provider, raw_text, retrieved_at, is_mock(bool)
AnswerAnalysis:  question_id, brand_mentioned(bool), brand_position(int|null),
                 competitors[{name, position}], citations[{domain, url?}],
                 sentiment(pos|neu|neg), evidence_quote
VisibilityMetrics: visibility_rate, sov, avg_position, citation_rate,
                 sentiment_summary, competitor_ranking[]
SiteAuditResult: crawlable(bool), robots_ok, sitemap_found, pages_checked(int),
                 has_es_mx_hreflang, has_structured_data, spanish_content_found,
                 issues[{severity, code, detail}], snapshot_mode(bool)
ContentGap:      gap_type(page|topic|signal), title, evidence[], related_questions[]
Recommendation:  priority(P0|P1|P2), action, reason, expected_impact, effort(S|M|L)
DiagnosticReport: brand_profile, questions[], metrics, site_audit, gaps[],
                 recommendations[], meta{generated_at, mode(mock|real|hybrid)}
```

---

## 7. 分阶段计划

### Stage 0 — 骨架与契约（预计 0.5 天 / 一个 session 内必须完成）
**目标：** 仓库可运行空管道，契约锁定，mock 数据就位。
- [ ] 建目录结构、`requirements.txt`、`.env.example`、`README.md` 初版
- [ ] `models.py` 全部契约落地
- [ ] `MockProvider` + fixtures：手工准备 8 条西语问题的模拟 AI 回答
      （其中约 5 条不含得力、竞品出现 BIC/Norma/Scribe/Pelikan/Faber-Castell 等，
      2 条含得力但排名靠后，1 条含得力排名前列——保证报告结论有层次）
- [ ] `main.py --mock` 能空跑全管道并输出占位 JSON
- **验收：** `pip install -r requirements.txt && python -m src.main --mock` 无报错出 JSON
- **若在此中断：** 已具备可讲解的架构 + 契约，可仅凭文档提交"方案说明型"答卷

### Stage 1 — MVP：一条完整真实链路（预计 1 天）⭐ 最重要
**目标：** 题目第七部分点名的最小链路完整跑通：
输入品牌和市场 → 生成问题 → 分析一组回答 → 输出缺口和页面建议。
- [ ] `question_gen`：DeepSeek 生成 20+ 问题（三层分类 + 漏斗 + 价值分）；无 key 时回退 fixtures
- [ ] `visibility_check`：Top-8 问题走 Provider（真实 DeepSeek 或 Mock，逐条标注 `is_mock`）
- [ ] `answer_analysis`：DeepSeek JSON-mode 结构化抽取 + 指标聚合；解析失败重试 1 次后降级记录
- [ ] `gap_analysis` + `recommendations`：综合生成缺口与 P0/P1/P2 建议
- [ ] 最简 `report.html`（先不追求美观，数据完整即可）
- [ ] `docs/方案说明.md` 初稿（需求理解 / 架构 / 范围取舍）
- **验收：** 一条命令产出包含真实 LLM 结果的 report.html + JSON；断网/无 key 时纯 Mock 也能跑
- **若在此中断：** 已满足题目"最低交付要求"，可以提交

### Stage 2 — 网站诊断 + 指标完备（预计 0.5~1 天）
- [ ] `site_audit` 全部检查项（见 §4 ④），限速与超时处理，失败降级快照模式
- [ ] 指标补齐：SOV、Avg Position、Sentiment 汇总、竞品排名表
- [ ] 缺口分析接入 site_audit 证据（例："官网无 es-MX hreflang" → 对应缺口）
- [ ] SQLite 落库：每次运行存 run 记录，支持 `--run-id` 重渲染历史报告
- **验收：** 报告含完整六大板块；对得力真实官网跑一次并提交产物快照

### Stage 3 — 报告打磨 + 文档冲刺（预计 1 天）⭐ 决定"碾压感"
- [ ] report.html 视觉升级：指标卡片（Visibility/SOV/Citation/Sentiment/Avg Position）、
      ECharts 竞品对比柱状图、问题明细表（分类/漏斗/价值分/是否命中）、
      缺口与建议卡片；整体风格干净专业（蓝白、留白、中西双语标签）
- [ ] 每处 Mock 数据在页面上有明确角标标注
- [ ] `docs/方案说明.md` 定稿：补"限制与不确定性"章节（§9）+"下一步规划"章节
- [ ] `README.md` 定稿：3 步运行 + 常见问题（无 key / 网络受限怎么办）
- [ ] `tests/`：answer_analysis 解析与指标聚合的单元测试（pytest，10 个用例左右）
- **验收：** 把 report.html 发给一个不懂技术的人，能看懂"得力在墨西哥的问题和该做什么"

### Stage 4 — 超预期加分项（可选，按剩余时间/额度取舍，逐项独立）
按性价比排序：
1. [x] DeepSeek V4 + 原生 Web Search：真实回答携带 API 返回的可点击来源 URL
2. [ ] FastAPI 暴露 `POST /diagnose` + 极简 Vue3+TS 前端页（输入品牌 → 展示报告）——呼应简历技术栈
3. [ ] 第二个真实 Provider（如可访问的 Gemini API 或 SERP API），报告呈现跨平台对比
4. [x] Query Fanout：每个高价值问题自动派生 3~5 个子问法并抽样检测
5. [ ] 5 分钟演示视频/GIF
6. [x] 引用证据预审：来源页面抓取、回答陈述映射、支持状态与人工复核标记
- **原则：任何一项做不完就整项回滚，不留半成品。**

---

## 8. Mock 与真实数据策略

- 模式判定：有 `DEEPSEEK_API_KEY` → hybrid（DeepSeek V4 问题生成/回答/抽取均为真实调用，回答默认联网搜索）；无 → 全 mock。
- **诚实原则：** 所有 mock 产物在数据层（`is_mock`）、报告层（角标）、文档层（方案说明）三处标注。
  这不是遮丑，而是主动展示——题目明确允许模拟数据，"清晰的取舍解释"本身是评分项。
- fixtures 一旦被真实数据验证过格式，不再修改结构。

## 9. "独立判断"清单（必须写入方案说明的限制与不确定性）

1. AI 回答不可复现：同一问题多次询问结果不同，单次采样≠稳定可见度，正式产品需多轮采样取均值；
2. 平台覆盖限制：国内网络环境下 ChatGPT/Gemini API 不可直连，本原型用 DeepSeek 代理"AI 回答引擎"角色并做了抽象层，接入真实海外平台只需新增 Provider；
3. 样本量限制：8~10 个问题是演示规模，商业结论需要 100+ 问题、多地区多语言采样；
4. 抓取伦理与限制：遵守 robots.txt、限速、仅抓公开页面；对方反爬时降级为快照模式；
5. LLM 结构化抽取存在误差：品牌别名（Deli/得力/DeliMex）、西语变体可能漏检，生产环境应加实体词典校验；
6. "商业价值评分"是模型主观判断，正式产品应结合搜索量/转化数据校准。

## 10. 最终提交物清单（对照题目"最低交付要求"）

| 题目要求 | 对应文件 |
| --- | --- |
| 方案说明 | `docs/方案说明.md` |
| 可查看成果 | 代码仓库 + `data/示例产物/report.html` + `report.json` |
| 运行说明 | `README.md` |
| （加分）完成/未完成边界与下一步 | 方案说明"范围取舍"+"下一步规划"章节 |

## 11. 交接协议（Claude Code ⇄ Codex 无缝切换）

1. `PROGRESS.md` 是唯一进度真相，格式：
   ```
   ## 2026-07-16 session-01 (Claude Code)
   - [x] Stage0-T1 目录结构  - [x] Stage0-T2 models.py
   - [ ] Stage0-T3 MockProvider  ← 进行中: fixtures 已建 3/8 条
   - 决策记录: selectolax 安装失败, 改用 bs4 (原因: ...)
   - 下一步: 补完 fixtures 后跑 --mock 验收
   ```
2. 每完成一个任务勾选一项并提交 git commit（信息格式 `stage1: 完成 question_gen`）；
3. 任何偏离本 PLAN 的决策必须写入 PROGRESS.md 的"决策记录"；
4. 新接手的 agent 开工前必读顺序：`PLAN.md` → `PROGRESS.md` → `src/models.py`；
5. 禁止重构已验收模块，除非 PROGRESS.md 记录了明确理由。

## 12. 时间与额度预算建议

- 总时间盒：3~4 天。Stage 0+1 必须最先完成（它们独立构成合格答卷）；
- 额度分配：Stage 1 占大头；Stage 3 的报告美化多为模板/前端工作，token 消耗低，适合额度紧张时手工介入；
- 每个 session 开始先跑 `python -m src.main --mock` 确认基线未破坏，再继续开发。

## 13. 冲刺阶段（2026-07-17 起，提交前最后阶段）

用户下达追加指令，全文见仓库根目录 **`追加指令_冲刺阶段.md`**，与本 PLAN 冲突之处以追加指令为准。
核心内容：P0 品牌词/无品牌词分层核查与指标重构 → P0 安全与可复现彩排 → P0 SUBMISSION.md
评审导览 → P1 GEO 领域概念补齐（AI 爬虫分项/llms.txt/JS渲染/提及vs推荐/来源分层）→
P1 Query Fanout → P2 双受众演示网页 + ECS 部署。执行顺序与验收标准见该文档第七部分。
