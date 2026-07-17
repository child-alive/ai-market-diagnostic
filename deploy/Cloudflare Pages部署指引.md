# 国际静态版 · Cloudflare Pages 部署指引

国际版只包含真实数据回放与完整报告，不部署 FastAPI、不包含 API key，也不会发起 `/api` 请求。

## 1. 本机生成待上传目录

```bash
cd web
npm ci
npm run build:intl
```

产物是 `web/dist-intl/`。若国内动态版已经有公网地址，可在构建时回填国际版引导链接：

```bash
VITE_DOMESTIC_URL=https://<国内动态版域名或 IP:端口>/ npm run build:intl
```

它只用于页面右上角“线路说明”中的动态线路链接，不是密钥。未设置时页面会明确说明
另一条公网线路尚未配置，不展示无效跳转。

## 2. 优先方案：控制台直接拖拽

按 [Cloudflare Pages 官方 Direct Upload 指引](https://developers.cloudflare.com/pages/get-started/direct-upload/)：

1. 登录 Cloudflare Dashboard，进入 **Workers & Pages**；
2. 选择 **Create application → Get started → Drag and drop your files**；
3. 输入项目名，把整个 `web/dist-intl/` 文件夹拖入上传区域；
4. 选择 **Deploy site**，完成后会得到 `<项目名>.pages.dev`；
5. 更新版本时进入该项目，选择 **Create a new deployment**，上传新 `dist-intl/` 并
   **Save and Deploy**。

Direct Upload 项目后续不能直接切换成 Git integration；如果将来要自动部署，需要新建
Git integration 项目。这一限制来自 Cloudflare 官方说明。

## 3. 本地预验收

```bash
cd web
npm ci
npm run build:intl
npm run preview:intl -- --port 4174
```

检查：

1. 首页产品视角正常；切到技术视角后明确显示当前为静态环境，且不出现实况启动按钮；
2. 浏览器 Network 中没有 `/api` 请求；
3. `/report/` 可直接打开完整诊断报告；
4. 产品 / 技术两套视图可切换，技术视角与原始 JSON 按需加载；
5. 移动端无横向溢出，控制台无报错。

## 4. 可选方案：连接 Git 自动构建

如果一开始就确定要自动部署，可新建 Git integration 项目：

| 项目 | 值 |
|---|---|
| Root directory | `web` |
| Build command | `npm ci && npm run build:intl` |
| Build output directory | `dist-intl` |
| Node.js | 20 或更新 |

在 Pages 项目的环境变量中设置可选的 `VITE_DOMESTIC_URL`，然后重新部署。

## 5. 上线后回填

Cloudflare Pages 首次部署会分配 `*.pages.dev` 地址。将它填入 `SUBMISSION.md` 的“国际静态版”行；
再将 ECS/Nginx 地址填入“国内动态版”行。若绑定自定义域名，在 Pages 的 Custom domains 中
添加域名并按提示设置 DNS 即可。

两个版本都支持：

- `/`：双受众回放首页；
- `/report/`：自包含完整报告。

国际版没有 `/api` 服务，这是有意的部署边界，不是故障。
