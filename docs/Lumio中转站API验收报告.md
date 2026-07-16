# Lumio 中转站 API 兼容性验收报告

> 验收日期：2026-07-17  
> 网关地址：<https://api.lumio.games/>  
> 验收目标：判断该中转站能否作为本项目更接近 ChatGPT Search / Gemini Google Search 的真实模拟链路。  
> 保密边界：测试密钥仅在交互式进程内短暂使用，未写入 `.env`、源码、日志、报告、Git 或 `PROGRESS.md`。

## 1. 结论摘要

**该中转站可以提供带 GPT / Gemini 名称的普通文本生成，但截至本次验收，不能作为本项目的联网搜索 Provider。**

主要原因：

1. GPT 与 Gemini 的普通 Chat Completions 均能返回文本，说明密钥和基础路由可用；
2. GPT 搜索参数请求虽返回 HTTP 200，但没有结构化引用，并给出了已被官方页面证伪的过期“最新新闻”；
3. GPT `/v1/responses` 路由对普通请求和 Web Search 请求都返回 HTTP 200、`application/json`，但响应正文为 0 字节；
4. Gemini 搜索参数请求连续两次只返回 `role`，没有正文和引用；
5. Gemini 原生 Interactions / Google Search Grounding 端点未暴露，相关路径返回 404；
6. 网关响应中的模型名称只能证明“网关声明的路由名”，不能作为上游确为 OpenAI / Google 官方模型或官方搜索链路的独立证明。

因此，不应把 Lumio 返回结果记为本项目的 `openai` 或 `gemini` 平台实测结果，也不应据此勾选 PLAN Stage 4 的“第二个真实 Provider”。

## 2. 验收口径

本项目测量的不是“能不能调用某个大模型回答问题”，而是“是否复现目标平台的联网回答与来源证据链”。通过标准必须同时满足：

| 验收项 | 通过标准 |
| --- | --- |
| 鉴权与模型发现 | 密钥有效，能取得可用模型列表 |
| 普通生成 | 能稳定返回非空正文和明确错误状态 |
| 联网工具执行 | 请求参数确实触发搜索，而不是被忽略或仅靠提示词模拟 |
| 新鲜度 | 能回答训练截止后或近期变化的问题，并与当前官方页面一致 |
| 来源可追溯 | API 返回可解析的 URL / citation / annotation，而非不可解析占位符 |
| 证据可复核 | 能把回答结论映射到实际来源，供机器预审和人工逐条核验 |
| 平台身份诚实 | 第三方路由必须单独标识，不冒充官方 ChatGPT / Gemini 客户端结果 |

只通过前两项，最多说明它是一个普通文本生成网关，不足以成为 GEO 联网测量 Provider。

## 3. 测试环境与安全措施

- 使用项目现有 macOS / Python 3.10 环境；
- 使用系统 `curl` 发起 HTTPS 请求，避免本地虚拟环境 CA 证书链差异干扰判断；
- 密钥通过隐藏回显的交互式输入传入，仅保存在进程内存中；
- 输出只保留 HTTP 状态、模型名、响应结构、非敏感正文与引用数量；
- 没有修改项目 `.env`，没有把第三方 Base URL 接入现有 Provider；
- 测试结束后 Git 工作树保持干净，随后仅新增本报告和进度记录。

由于密钥曾直接出现在对话记录中，建议用户在测试完成后到 Lumio 后台轮换密钥。

## 4. 端点与模型发现

### 4.1 网关基础行为

| 请求 | 结果 | 判断 |
| --- | --- | --- |
| `GET /` | HTTP 200，页面标题为 LumioAPI / AI API Gateway | 网关在线 |
| 未鉴权 `GET /v1/models` | HTTP 401，提示支持 Bearer、`x-api-key`、`x-goog-api-key` | 存在 OpenAI / Google 风格鉴权兼容层 |
| 未鉴权 `POST /v1/responses` | HTTP 401 | 路由存在，但不代表功能可用 |
| 未鉴权 `POST /v1/interactions` | HTTP 404 | 未暴露该路径 |
| 未鉴权 `POST /v1beta/interactions` | HTTP 404 | 未暴露 Gemini 原生 Interactions 路径 |

### 4.2 GPT 密钥可见模型

`GET /v1/models` 返回 HTTP 200，共 20 个路由名：

```text
codex-auto-review
gpt-4o-audio-preview
gpt-4o-realtime-preview
gpt-5.2
gpt-5.2-2025-12-11
gpt-5.2-chat-latest
gpt-5.2-pro
gpt-5.2-pro-2025-12-11
gpt-5.3-codex
gpt-5.3-codex-spark
gpt-5.4
gpt-5.4-2026-03-05
gpt-5.4-mini
gpt-5.5
gpt-5.6-luna
gpt-5.6-sol
gpt-5.6-terra
gpt-image-2
gpt-image-2-2k
gpt-image-2-4k
```

列表中没有项目当前官方 Provider 约定的 `gpt-5-search-api`。模型名由网关返回，不能单独证明上游模型身份或能力等价。

### 4.3 Gemini 密钥可见模型

`GET /v1/models` 返回 HTTP 200，共 5 个路由名：

```text
gemini-3.1-flash-image-preview
gemini-3.1-pro-preview
gemini-3.5-flash
gemini-3.5-flash-high
gemini-3.5-flash-low
```

可见模型列表不等于已开放 Google Search Grounding；搜索能力必须通过工具调用和引用响应另行验收。

## 5. 普通生成测试

统一通过 `POST /v1/chat/completions` 发起最小、确定性输出测试。

| 路由 | HTTP | API 返回模型 | 结果 |
| --- | ---: | --- | --- |
| GPT | 200 | `gpt-5.4` | 成功返回指定测试文本，`finish_reason=stop` |
| Gemini | 200 | `gemini-3.5-flash` | 返回指定文本的主体，受较小 token 上限影响以 `finish_reason=length` 结束 |

结论：两把密钥都可用于普通文本生成；这部分通过。

## 6. GPT 联网搜索测试

### 6.1 Chat Completions + `web_search_options`

使用 `gpt-5.4`，问题要求联网查询 OpenAI 官方 News 页面截至 2026-07-17 的最新文章，并提供官方 URL 与引用。

API 结果：

- HTTP 200；
- `response_model=gpt-5.4`；
- `message` 只有 `role` 与 `content`；
- `annotations=0`，没有 `url_citation`；
- 正文称最新文章是 2025-08-07 的 “Introducing GPT-5 for developers”；
- 正文残留 `turn2open0` / `turn3open0` 一类调用方无法解析的内部引用占位符。

官方交叉核验：

- OpenAI 官方 News：<https://openai.com/news/>
- 页面在测试日已列出 2026-07-16、2026-07-15、2026-07-14 等新内容；
- 因此网关回答把 2025-08-07 文章称为“截至现在最新”是明确错误。

判断：**失败。** 不能证明 `web_search_options` 被正确执行；即使网关内部触发了某种检索，返回结果也不满足新鲜度和可追溯引用要求。

### 6.2 Responses API + Web Search 工具

测试 `POST /v1/responses`，分别发送：

1. 普通文本生成请求；
2. `tools=[{"type":"web_search"}]` 的搜索请求。

两次结果一致：

- HTTP 200；
- `Content-Type: application/json`；
- 下载正文大小为 0 字节。

判断：**失败。** 路由虽然存在并通过鉴权，但当前无法返回可解析的 Responses API 数据；问题并非只发生在 Web Search 工具上。

## 7. Gemini 联网搜索测试

### 7.1 OpenAI 兼容 Chat Completions + 搜索参数

使用 `gemini-3.5-flash`，要求通过 Google Search 查询 Google DeepMind 官方 News 的最新文章并提供引用。连续测试两次，其中第二次显式提高输出 token 上限。

两次结果：

- HTTP 200；
- `response_model=gemini-3.5-flash`；
- `finish_reason=stop`；
- `message` 仅包含 `role`；
- `content=None`；
- `annotations=0`。

判断：**失败。** 搜索请求没有返回正文或任何来源结构。

### 7.2 Gemini 原生 Interactions / Google Search Grounding

项目的官方 Gemini Provider 使用 Interactions API，并依赖：

- `tools=[{"type":"google_search"}]`；
- `google_search_call`；
- 文本区间级 `url_citation`。

Lumio 的 `/v1/interactions` 与 `/v1beta/interactions` 均返回 404，无法复用该原生契约。

官方交叉核验页：Google DeepMind News <https://deepmind.google/blog/>。该页面测试日已有 2026 年 7 月内容，但 Lumio 搜索请求没有产生可供比对的正文。

判断：**失败。** 当前网关未提供本项目需要的 Google Search Grounding 链路。

## 8. 验收矩阵

| 能力 | GPT 路由 | Gemini 路由 |
| --- | --- | --- |
| 密钥鉴权 | 通过 | 通过 |
| 模型列表 | 通过，20 个路由名 | 通过，5 个路由名 |
| 普通文本生成 | 通过 | 通过 |
| 搜索工具可验证执行 | 未通过 | 未通过 |
| 当前信息新鲜度 | 未通过，样题被官方页面证伪 | 无正文，无法验证 |
| 结构化来源 URL | 0 条 | 0 条 |
| 原生引用区间 | 不存在 | 不存在 |
| 可进入证据预审 | 否 | 否 |
| 可等价标记为官方平台 | 否 | 否 |

## 9. 对项目的建议

### 当前建议

1. **不接入现有 `openai` / `gemini` Provider。** 两个 Provider 的核心价值正是原生搜索和引用契约；用普通 Chat Completions 代替会改变测量对象。
2. **不把本次结果写入跨平台报告。** 否则读者可能误以为测得的是 ChatGPT Search / Gemini 客户端表现。
3. **继续以 DeepSeek V4 Web Search 的已验收运行 `37b442ec` 作为提交主示例。** 该运行有真实搜索来源、分层指标和 Query Fanout，边界清楚。
4. 若未来确需利用 Lumio，可新增独立名称如 `lumio_gpt` / `lumio_gemini`，并仅标为“第三方路由普通生成”；但对当前求职题的联网 GEO 目标几乎没有增量价值。
5. 第二个真实平台仍应等待 OpenAI 官方 API credits，或 Gemini 官方 Google Search Grounding 权限 / 额度恢复后做单题冒烟。

### 不建议的做法

- 不因 HTTP 200 就把搜索记为成功；
- 不把正文中的裸 URL 或内部 citation token 当成原生引用注解；
- 不用模型自述“我已联网”作为工具执行证据；
- 不用网关返回的模型字符串作为上游身份认证；
- 不为追求“多平台”展示而牺牲现有报告的测量诚实性。

## 10. 给 Fable5 的复核重点

建议 Fable5 复核时优先判断以下三点，无需重复消耗 API：

1. **验收口径是否合理：** GEO 平台测量是否必须要求结构化来源、新鲜度和平台身份边界；
2. **GPT 反例是否足够有判别力：** 网关将 2025 年文章误报为 2026-07-17 的最新内容，且官方 News 页可直接证伪；
3. **项目决策是否应维持：** Lumio 只作为普通生成网关记录，不进入 `openai` / `gemini` 官方平台切片，也不因此修改已验收 Provider。

如果 Fable5 能从 Lumio 的服务商文档中找到明确的搜索工具协议、结构化 citation 返回示例或专用搜索模型，再按该**公开契约**补做一次单题验证即可；在此之前，没有必要运行 Top-8 或全平台测试。

## 11. 最终判定

**普通生成：通过。**  
**联网搜索：未通过。**  
**可作为官方 ChatGPT / Gemini 的接近模拟：否。**  
**是否接入当前项目：否，保留为已评估但不采用的第三方网关。**
