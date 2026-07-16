# Codex → Claude Fable 5 独立复核交接

> 交接日期：2026-07-17
>
> 功能基线：`54f6568`（本交接文件会作为其后一笔纯文档提交）
>
> Fable 5 上次暂停点：`98d00f9`（追加指令入库并向 PLAN 追加冲刺章节）
>
> 目标：请 Fable 5 独立审核 Codex 在暂停点之后完成的冲刺成果，优先找口径错误、证据不足、范围失控或评审体验问题；本轮先给审查结论，不要直接大规模重构。

## 1. 接手顺序与安全边界

仍按仓库协议完整阅读：

1. `PLAN.md`
2. `PROGRESS.md`
3. `src/models.py`
4. `追加指令_冲刺阶段.md`
5. 本文件

安全约束：

- `.env` 含本机真实配置、已被 Git 忽略且权限受限；不要读取、打印、复制或提交任何密钥。
- 本轮复核不需要调用任何真实 API，也不要运行 `--providers auto`、`src.sampling_demo`、真实 Query Fanout 或网页实况。
- 上层目录的测试题 docx 和业务 PDF 继续保持不入库。
- 不要把 Lumio、FreeModel 等第三方网关结果记成 OpenAI/Gemini 官方平台结果。
- 已验收模块先审后改；若发现问题，请给出文件、证据、严重度和最小修复建议，等用户拍板再实施。

## 2. 当前状态一句话

Stage 0~3 已完成，Stage 4/冲刺增强已完成 DeepSeek V4 原生 Web Search、品牌词/无品牌词分层、Mention/Recommendation 区分、来源结构、重复采样、Query Fanout、双受众演示网页、受限实况 API 与 ECS 部署交付；OpenAI/Gemini Provider 代码已就绪，但官方联网额度/权限未通过，因此没有伪称多平台真实验收。

交接前重新验证：

- Git 功能基线 `54f6568`，仓库共 34 个 commit；工作树干净。
- `.venv/bin/python -m pytest -q`：`55 passed`。
- `.venv/bin/python -m src.main --mock`：`20 问题 / 8 回答 / 7 缺口 / 7 建议`。
- `.venv/bin/python -m src.main --run-id 37b442ec`：历史真实报告成功重渲染，不调用 API。
- 两个部署脚本 `bash -n` 通过；`web/dist/index.html`、`demo-report.json`、`full-report.html` 均存在。

## 3. Fable 暂停后完成了什么

建议按下列 commit 顺序审核；它们与 `PROGRESS.md` session-03/session-04 一一对应。

### 3.1 `64b24ba`：品牌词 / 无品牌词分层核查

- 为问题增加 `query_scope`，将 branded 认知与 unbranded 主动推荐竞争力分开统计。
- 历史真实运行 `f141d182` 被重新审计：原先混算的 50% Visibility 不能表述为通用推荐竞争力；无品牌词 Mention/SOV 实际为 0%。
- 问题生成 Prompt 增加硬约束，通用问题不得泄漏 Deli/得力；运行时再做确定性分类。
- 报告第一屏改成洞察型叙事：AI 在品牌词中认识 Deli，但通用需求中尚未主动带出品牌。
- 旧 JSON/SQLite 通过默认值和重渲染补算保持兼容，没有改名破坏契约。

请重点审核：`src/pipeline/segmentation.py`、`src/pipeline/analysis.py`、`src/main.py` 与报告模板中的分母是否一致；旧 run 补算是否可能误分类。

### 3.2 `09a4b98`：安全与可复现彩排

- 完成密钥特征、Git 历史、忽略规则、干净环境和 Mock 基线核查。
- README 明确 `--providers auto` 的官方额度现状，避免评审者直接撞 429。
- 记录浏览器本地端口曾因会话隔离不可访问，后来已成功复试；不是用户权限问题。

请重点审核：README 是否仍存在会诱发真实额度消耗、误读数据边界或泄露配置的命令。

### 3.3 `c99f0c6`：评审导览

- 新增 `SUBMISSION.md`，按题目要求直接回答“做了什么、为何这样设计、哪些真实/模拟、下一步做什么”。
- 给出 10 分钟评审动线，并把静态真实报告固定为最低摩擦主件。

请重点审核：非技术评审是否能在第一分钟理解结论；四问是否存在重复、夸张或未被产物支持的说法。

### 3.4 `74b44b9`：GEO 站点审计增强

- 将 AI 访问拆为 8 个 crawler/user-agent token，区分搜索/引用、训练/采集和两者兼有。
- 增加 `llms.txt` / `llms-full.txt`、原始 HTML 文本量、品牌是否在原始 HTML、JS 依赖、直接回答内容与 FAQ 信号。
- 报告和方案说明明确这些是启发式可引用性信号，不把缺失写成“AI 一定无法抓取”。

请重点审核：robots.txt 最长匹配/具体规则优先逻辑、crawler purpose 分类，以及 JS/FAQ/llms.txt 文案是否越界。

### 3.5 `c02e49f`：指标语义、来源结构与重复采样

- `AnswerAnalysis` 增加保守的 `brand_recommended` 与 `recommendation_assessed`，避免“被提到”等同“被推荐”。
- 指标增加 `recommendation_rate`；旧报告未评估时默认 `None`，重渲染可依据保存原文补算。
- 来源按官网、权威媒体/政府、电商、目录、论坛、其他分类；文档明确 Source Type 不是来源质量或事实支持评分。
- 新增独立 `src.sampling_demo`；真实产物 `repeat_sampling.json` 为 q05/q07/q08 各 3 轮，9/9 grounded，展示 0%~33.3% 波动，但不冒充置信区间。

请重点审核：推荐启发式的误报/漏报边界、否定句和竞品上下文；来源分类规则是否透明；Source Mix 是否被文案误写为可信度。

### 3.6 `39572fa`：Query Fanout 真实验收

- 只从高价值 unbranded 父问题派生 paraphrase/scenario/follow-up 三类分支。
- 运行时强制检查西语/中文品牌名与别名泄漏、父问题归属、数量、类型与重复。
- Fanout 回答、分析和 Coverage 独立存储，不混入主 Prompt Set 分母。
- 真实提交 run 更新为 `37b442ec`：主链路 22 问、Top-8 回答，8/8 grounded、70 个来源、0 Mock/降级；2 个父问题派生 6 个真实分支，6/6 grounded、66 个来源、品牌泄漏 0。
- 该 run 的 5 个主无品牌词和 6 个 Fanout 分支均未提及或推荐 Deli；这只是同平台同日小样本观察。

请重点审核：`src/pipeline/query_fanout.py` 的品牌泄漏防护、回退 Mock 标记、Coverage 公式和主指标隔离；报告是否把 0% 误写成确定性市场结论。

### 3.7 `1aa2d58`：双受众演示网页与 ECS 交付

- 新增 Vue 3 + TypeScript + Vite 回放页，产品/技术双视角、七阶段过程、完整报告入口；提交 `web/dist/`，评审者无需 Node。
- 回放只读固化的 `37b442ec`，不重算指标、不调用 Provider。
- 新增 FastAPI/SSE 受限实况：只允许 3~5 个版本内固定高价值 unbranded 问题，不接受任意 Prompt；每 IP 每小时 2 次、全局并发 1、180 秒总超时。
- Worker 使用可终止子进程，避免超时/断连后隐藏请求继续耗额度；实况不写 SQLite、不覆盖示例、不混入主指标。
- 浏览器回放和真实网页实况已验收：固定 q05/q07/q06，3/3 grounded、合计 20 个来源，均未提及 Deli；只验证网页链路。
- 提供 `deploy/` 下 Nginx + Systemd + Uvicorn 单 worker 的脚本和手册；尚未部署公网，`SUBMISSION.md` 在线 URL 仍待用户 ECS 回填。

请重点审核：`src/demo_api.py`、`src/demo_worker.py` 的限流、并发锁、断连清理和 fail-closed；前端是否把回放/实况、主 run/临时结果混淆；部署脚本是否可能覆盖远端 `.env` 或开放不必要端口。

### 3.8 `54f6568`：Lumio 中转站小插曲

- 普通 GPT/Gemini 路由生成通过，但联网能力没有通过：GPT 无结构化引用且“最新新闻”被官方页面证伪；Responses API 返回 200/空正文；Gemini 搜索返回空正文且原生 Interactions 路由 404。
- 已新增 `docs/Lumio中转站API验收报告.md`，没有修改 Provider、没有写入任何密钥，也没有把结果纳入平台切片。
- 用户已决定暂时不使用该中转站；后续无需继续研究，除非服务商给出公开搜索工具和 citation 契约。

请重点审核：只需判断“不接入”的证据和口径是否成立；不要重复调用中转站。

## 4. 当前提交主件与事实边界

### 已真实验收

- DeepSeek `deepseek-v4-flash` 普通生成、结构化抽取和服务端 Web Search。
- 提交主运行 `37b442ec`：8/8 主回答 grounded，70 个主来源 URL；6/6 Fanout grounded，66 个分支来源 URL；0 Mock、0 解析降级。
- 官网实时检查 `deliworld.com` 15 页，`snapshot_mode=false`；结论仅限抓取范围。
- 独立重复采样 9/9 grounded；仅用于展示波动，不是置信区间。
- 双受众网页回放、受限实况链路、本地 HTTP 与响应式浏览器 QA。

### 只完成代码或被外部条件阻塞

- OpenAI Search：Provider 和伪响应测试通过；官方请求因 API 账户无 credits 返回 429，不能声称真实联网通过。
- Gemini Search Grounding：Key 和普通生成有效；Google Search 工具因额度/权限返回 429，不能声称真实联网通过。
- Lumio/FreeModel：第三方网关，不接入、不计作官方平台。
- 公网 ECS：构建、脚本和部署手册已完成，但用户尚未提供 ECS 连接信息和授权执行部署。

### 必须保持的测量口径

- Branded 指标衡量认知/召回，Unbranded 才衡量主动发现与推荐竞争力；不得重新混算。
- Mention 不等于 Recommendation；SOV 按回答级品牌提及计算，不等于 Share of Answer。
- Citation Rate 只说明 API 返回来源，不说明来源支持结论。
- Source Type 只说明来源类别，不是质量或可信度打分。
- 证据预审是词面机器队列，永远 `requires_human_review=true`，不能写成已人工事实核查。
- 主报告、重复采样、Fanout 和网页实况是四个独立切片，不得互相混分母。
- 单平台、单日、小样本结果不等于 ChatGPT/Gemini 客户端结果，也不能直接用于商业决策。

## 5. 建议的零额度复核命令

```bash
git status --short
git log --oneline -12
.venv/bin/python -m pytest -q
.venv/bin/python -m src.main --mock
.venv/bin/python -m src.main --run-id 37b442ec
bash -n deploy/deploy.sh
bash -n deploy/install_remote.sh
```

可选网页回放，不调用 API：

```bash
.venv/bin/uvicorn src.demo_api:app --host 127.0.0.1 --port 8765
# 打开 http://127.0.0.1:8765/
```

不要点击“开始实况诊断”；本轮审核只需回放。

## 6. 请 Fable 5 输出的审核格式

请先给独立结论，再决定是否建议修改：

1. **总体等级**：可提交 / 小修后提交 / 存在阻断问题。
2. **发现清单**：按 P0/P1/P2 排序，每项给出文件或模块、可复验证据、影响和最小修复建议。
3. **数字一致性**：核对 `SUBMISSION.md`、README、方案说明、示例 JSON/HTML、网页回放中的 `37b442ec` 数字是否一致。
4. **测量诚实性**：重点判断 branded/unbranded、Mention/Recommendation、Citation/证据支持、主样本/Fanout/重复采样是否被清楚区分。
5. **工程风险**：重点看历史兼容、Mock 可复现、Demo 实况的额度与并发安全、部署边界。
6. **评审体验**：按 10 分钟动线实际浏览，指出第一分钟是否能看懂“AI 认识 Deli，但不会在无品牌词中主动推荐”的核心故事。
7. **是否值得再加功能**：默认答案应是“不加”；只有能直接修复评分风险或阻断提交时才建议扩大范围。

## 7. 当前真正剩余的用户动作

1. 用户自行核验静态报告和演示网页观感。
2. 等 Fable 5 给出独立审查结论，再决定是否做最小修正。
3. 若用户准备公网展示，再提供 ECS 公网 IP/SSH 信息并明确授权部署；部署后回填 `SUBMISSION.md` URL。
4. OpenAI/Gemini 官方额度以后若恢复，只做单题联网冒烟；成功前不要跑全量。

除此之外，当前项目已处于可提交状态，不建议继续堆功能。
