# 国际静态版 · Cloudflare Pages 部署指引

国际版只包含真实数据回放与完整报告，不部署 FastAPI、不包含 API key，也不会发起 `/api` 请求。

## 1. 构建设置

在 Cloudflare Pages 连接本 Git 仓库后填写：

| 项目 | 值 |
|---|---|
| Root directory | `web` |
| Build command | `npm ci && npm run build:intl` |
| Build output directory | `dist-intl` |
| Node.js | 20 或更新 |

可选环境变量：

```text
VITE_DOMESTIC_URL=https://<国内动态版域名或 IP:端口>/
```

它只用于国际版中的“前往国内动态版”链接，不是密钥。未设置时页面会提示评审者从
`SUBMISSION.md` 获取国内地址。

## 2. 本地预验收

```bash
cd web
npm ci
npm run build:intl
npm run preview:intl -- --port 4174
```

检查：

1. 首页回放正常，实况按钮为禁用状态；
2. 浏览器 Network 中没有 `/api` 请求；
3. `/report/` 可直接打开完整诊断报告；
4. 技术视角与原始 JSON 按需加载；
5. 移动端无横向溢出，控制台无报错。

## 3. 上线后回填

Cloudflare Pages 首次部署会分配 `*.pages.dev` 地址。将它填入 `SUBMISSION.md` 的“国际静态版”行；
再将 ECS/Nginx 地址填入“国内动态版”行。若绑定自定义域名，在 Pages 的 Custom domains 中
添加域名并按提示设置 DNS 即可。

两个版本都支持：

- `/`：双受众回放首页；
- `/report/`：自包含完整报告。

国际版没有 `/api` 服务，这是有意的部署边界，不是故障。
