# AI 海外市场诊断智能体（原型）

面向出海品牌的 GEO（生成式引擎优化）诊断原型。输入品牌与目标市场，输出问题地图、AI 可见度、竞品话语权、官网可引用性、内容缺口与优先行动建议。

演示用例为 **得力 Deli × 墨西哥 × 西班牙语**。核心指标与聚路国际产品语言对齐：Visibility、Share of Voice、Average Position、Citation Rate、Sentiment；问题按品牌词 / 地区排名词 / 品类排名词与 TOFU / MOFU / BOFU 分类。

## 三步运行

要求 Python 3.10+。以下命令在项目根目录执行。

```bash
# 1. 创建环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 可选：配置 DeepSeek；不配置会自动进入全 Mock 模式
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

## 常用运行方式

| 命令 | 用途 | 数据边界 |
| --- | --- | --- |
| `.venv/bin/python -m src.main --mock` | 最稳定的离线演示 | 问题、AI 回答与网站诊断均使用 fixtures；页面明确标注 Mock / Snapshot |
| `.venv/bin/python -m src.main --mock --live-audit` | 可复现 AI 结果 + 实时官网诊断 | AI 回答为 Mock；官网实时抓取，失败自动回退快照 |
| `.venv/bin/python -m src.main` | 有 key 时运行 hybrid 链路 | DeepSeek 生成问题与回答/抽取；无 key 时自动切 Mock |
| `.venv/bin/python -m src.main --top-n 10` | 调整 AI 可见度检测样本数 | 默认检测价值分最高的 8 个问题 |
| `.venv/bin/python -m src.main --run-id <RUN_ID>` | 重渲染历史报告 | 从 SQLite 恢复完整报告，不重新调用 LLM 或抓取官网 |

每次新运行会打印 `run_id`。例如：

```text
[db]   run_id=148d4739 → .../data/diagnostic.db
```

之后可执行：

```bash
.venv/bin/python -m src.main --run-id 148d4739
```

## 报告包含什么

1. 五项 AI 可见度指标卡与 ECharts 竞品 SOV 对比图；
2. 20 条西语问题地图，含中文对照、分类、漏斗、价值分与检测结果；
3. 逐条 AI 回答的品牌顺位、竞品、引用、情感与证据句；
4. robots.txt、sitemap、`es-MX hreflang`、JSON-LD、西语内容与可抓取性检查；
5. 带证据链的内容/页面/技术信号缺口；
6. P0 / P1 / P2 行动建议，含理由、预期影响与工作量。

ECharts 通过 CDN 加载；断网时竞品排行表与其余全部内容仍可正常阅读。提交示例位于 `data/示例产物/`：DeepSeek 实时生成 22 条问题并回答其中 8 条，8 条结构化抽取均未降级；官网结果为 2026-07-16 对 `deliworld.com` 的 15 页实时检查，报告模式为 `hybrid`。

## 数据与工程约定

- 模块间只通过 `src/models.py` 的 Pydantic 契约传递数据；
- `AnswerProvider` 隔离具体 AI 平台，当前提供 DeepSeek 与 Mock 实现；
- DeepSeek 结构化抽取失败会降级启发式解析并标记 `parse_degraded`；
- DeepSeek 未接搜索工具，回答中的域名属于模型声明来源、未做 URL 真实性核验；
- 官网抓取遵守 robots.txt、限速不高于 1 req/s、最多检查 15 页；
- Mock 在数据层 `is_mock`、报告层角标与文档层三处标注；
- 缺口和建议由指标/网站证据规则驱动，不进行不可追溯的二次 LLM 生成。

## 常见问题

**没有 `DEEPSEEK_API_KEY`？** 直接运行 `--mock`。即使不传 `--mock`，程序在无 key 时也会自动切换到 Mock。

**网络受限或官网反爬？** 使用 `--mock` 可完全离线演示。实时诊断失败会读取 `fixtures/site_snapshot/`，并在报告中标记“快照模式”。

**`--run-id` 提示未找到？** 历史 ID 只存在于本机 `data/diagnostic.db`。先完成一次新运行并复制终端打印的 ID。

**报告中的数字能直接用于客户决策吗？** 不能。提交示例是 DeepSeek 的单轮 8 问真实调用，不等价于 ChatGPT/Gemini 市场表现；其中声明引用域名也未独立核验。商业测量需接入真实海外平台与搜索证据，扩到 100+ 问题并做多轮采样。

**图表没有显示？** 检查能否访问 jsDelivr CDN。即使图表脚本加载失败，右侧竞品排行表仍提供相同数据。

## 运行测试

```bash
.venv/bin/python -m pytest -q
```

当前测试集共 14 个用例，覆盖启发式回答解析、品牌/竞品顺位、引用与情感识别、指标聚合口径、SQLite 报告往返，以及 Deli 消歧不污染通用问题、竞品名称规范化两项真实链路回归场景。

## 项目文档

- `docs/方案说明.md`：需求理解、架构、取舍、官网实测、限制与下一步；
- `PLAN.md`：权威开发规划与数据协议；
- `PROGRESS.md`：任务进度、验证事实与决策记录。
