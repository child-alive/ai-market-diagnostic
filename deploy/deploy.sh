#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"
PUBLIC_PORT="${2:-8080}"
APP_DIR="${APP_DIR:-/opt/ai-market-diagnostic}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "$TARGET" ]]; then
  echo "用法: ./deploy/deploy.sh <user@server-ip> [public-port]"
  echo "示例: ./deploy/deploy.sh ubuntu@203.0.113.10 8080"
  exit 2
fi
if [[ ! "$PUBLIC_PORT" =~ ^[0-9]+$ ]] || (( PUBLIC_PORT < 1 || PUBLIC_PORT > 65535 )); then
  echo "public-port 必须是 1~65535 的整数"
  exit 2
fi
if [[ ! -f "$ROOT_DIR/web/dist/index.html" ]]; then
  echo "缺少 web/dist/index.html，请先在 web/ 运行 npm ci && npm run build"
  exit 2
fi

echo "[1/3] 准备远端目录 $APP_DIR"
ssh -t "$TARGET" "sudo mkdir -p '$APP_DIR' && sudo chown -R \$(id -un):\$(id -gn) '$APP_DIR'"

echo "[2/3] 同步代码与已构建网页（不会上传或覆盖 .env）"
rsync -az \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.venv/' \
  --exclude 'web/node_modules/' \
  --exclude '.pytest_cache/' \
  --exclude '__pycache__/' \
  --exclude '.DS_Store' \
  --exclude 'data/diagnostic.db' \
  --exclude 'data/report.json' \
  --exclude 'data/report.html' \
  "$ROOT_DIR/" "$TARGET:$APP_DIR/"

echo "[3/3] 安装服务并配置 Nginx"
ssh -t "$TARGET" "cd '$APP_DIR' && sudo bash deploy/install_remote.sh '$APP_DIR' '$PUBLIC_PORT'"

echo "部署完成: http://<server-ip>:$PUBLIC_PORT/"
echo "若需开启实况模式，请按 deploy/部署手册.md 在服务器创建 .env 后重启服务。"
