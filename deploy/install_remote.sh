#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/ai-market-diagnostic}"
PUBLIC_PORT="${2:-8080}"
SERVICE_NAME="ai-market-diagnostic"
NGINX_SITE="/etc/nginx/sites-available/$SERVICE_NAME"

if [[ "$EUID" -ne 0 ]]; then
  echo "install_remote.sh 必须以 root 运行"
  exit 2
fi
if [[ ! -f "$APP_DIR/requirements.txt" || ! -f "$APP_DIR/web/dist/index.html" ]]; then
  echo "远端目录缺少 requirements.txt 或 web/dist/index.html: $APP_DIR"
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv nginx

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

chown -R root:www-data "$APP_DIR"
find "$APP_DIR" -type d -exec chmod 750 {} +
find "$APP_DIR" -type f -exec chmod 640 {} +
# 上一条会统一移除普通文件的执行位；虚拟环境中的控制台命令需要恢复执行权限。
find "$APP_DIR/.venv/bin" -maxdepth 1 -type f -exec chmod 750 {} +
chmod 750 "$APP_DIR/deploy/deploy.sh" "$APP_DIR/deploy/install_remote.sh"
if [[ -f "$APP_DIR/.env" ]]; then
  # systemd 以 root 读取 EnvironmentFile，600 root:root 即可，www-data 无需读权限
  chown root:root "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi

cat > "/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=AI Market Diagnostic Demo API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=DEMO_TRUST_PROXY=true
EnvironmentFile=-$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn src.demo_api:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
Restart=always
RestartSec=5
TimeoutStopSec=10
KillMode=mixed
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
EOF

cat > "$NGINX_SITE" <<EOF
server {
    listen $PUBLIC_PORT;
    listen [::]:$PUBLIC_PORT;
    server_name _;

    root $APP_DIR/web/dist;
    index index.html;
    charset utf-8;
    client_max_body_size 64k;
    gzip on;
    gzip_static on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/css application/javascript application/json image/svg+xml;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-Frame-Options DENY always;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 190s;
        add_header X-Accel-Buffering no;
    }

    location = /report {
        return 302 /report/;
    }

    location ^~ /report/ {
        try_files \$uri \$uri/ /report/index.html;
    }

    location / {
        try_files \$uri \$uri/ /404.html;
    }

    location ~ /\\. {
        deny all;
    }
}
EOF

ln -sfn "$NGINX_SITE" "/etc/nginx/sites-enabled/$SERVICE_NAME"
if [[ "$PUBLIC_PORT" = "80" ]]; then
  rm -f /etc/nginx/sites-enabled/default
fi

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
# 重复部署时服务可能已在运行；enable --now 不会重启旧进程。
# 每次同步新代码后必须显式 restart，否则公网 API 仍执行上一版代码。
systemctl restart "$SERVICE_NAME"
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q '^Status: active'; then
  ufw allow OpenSSH
  ufw allow "$PUBLIC_PORT/tcp"
fi

curl -fsS http://127.0.0.1:8000/api/health
echo
echo "远端安装完成，Nginx 监听端口 $PUBLIC_PORT。"
