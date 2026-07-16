# AI 海外市场诊断智能体（原型）

输入品牌 + 目标市场，输出一份 GEO（生成式引擎优化）诊断报告，回答三个问题：

1. **问题发现与缺口**：目标市场用户在问什么？哪些问题品牌尚未覆盖？
2. **AI 可见度**：品牌在 AI 回答中是否出现？竞品是谁？引用来源是什么？
3. **网站诊断**：品牌官网是否适合搜索引擎与 AI 抓取、理解、引用？

演示用例：品牌 = 得力 Deli，市场 = 墨西哥，语言 = 西班牙语，品类 = 文具/办公/学生用品。

## 三步运行

```bash
# 1. 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 2. （可选）配置 DeepSeek key；跳过此步则自动使用全 Mock 模式
cp .env.example .env   # 编辑填入 DEEPSEEK_API_KEY

# 3. 运行诊断
python -m src.main --mock          # 全 Mock 模式，无需任何 key / 网络
python -m src.main                 # 有 key 时使用真实 LLM
```

产物输出到 `data/`：`report.json`（结构化结果）与 `report.html`（双击浏览器打开）。

## 常见问题

- **没有 DeepSeek key？** 直接 `--mock`，全链路使用 fixtures 回放，结果可复现。
- **网络受限？** 官网诊断失败时自动降级为本地快照模式，报告中会明确标注。
- **Mock 数据在哪标注？** 数据层（`is_mock` 字段）、报告层（角标）、文档层（方案说明）三处。

## 文档

- 方案说明（需求理解/架构/取舍/限制）：`docs/方案说明.md`
- 总体规划：`PLAN.md`；进度日志：`PROGRESS.md`
