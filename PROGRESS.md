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
- [ ] Stage0-T1 目录结构 + requirements.txt + .env.example + README.md 初版
- [ ] Stage0-T2 models.py 全部契约
- [ ] Stage0-T3 MockProvider + fixtures（8 条西语模拟回答 + 问题种子）
- [ ] Stage0-T4 main.py --mock 空跑全管道输出占位 JSON
- 验收：`pip install -r requirements.txt && python -m src.main --mock` 无报错出 JSON

### 决策记录
- 项目根目录定为 `聚路国际/ai-market-diagnostic/`（PLAN §5 结构），
  业务 PDF 与测试题 docx 留在上层目录、不入库（含公司资料，不适合进代码仓库）。
- DeepSeek API 调用采用 httpx 直连（OpenAI 兼容协议），不引入 openai SDK，
  理由：依赖最小化，且 Provider 抽象层本就要求自行封装重试/降级。

### 下一步
- 执行 Stage0-T1。
