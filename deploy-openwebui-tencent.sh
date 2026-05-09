#!/bin/bash

set -euo pipefail

REMOTE_USER="ubuntu"
REMOTE_HOST="43.160.238.95"
REMOTE_PASSWORD='4Uuk*~PW.(/37V$j'
REMOTE_PATH="/var/www/open-webui-anon"
LOCAL_TAR="/tmp/open-webui-anon-deploy.tar.gz"
FRONTEND_SOURCE_DIR="${FRONTEND_SOURCE_DIR:-${FRONTEND_BUILD_DIR:-}}"

SSH_ARGS=(
  -F /dev/null
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o PubkeyAuthentication=no
  -o PreferredAuthentications=password
  -o PasswordAuthentication=yes
  -o KbdInteractiveAuthentication=no
  -o IdentitiesOnly=yes
  -o IdentityFile=/dev/null
)

echo "========================================="
echo "Open WebUI Anon Tencent Cloud Deploy"
echo "========================================="

echo "🧱 Step 0: 构建前端产物..."
if [ -d "build" ]; then
  echo "✅ 复用仓库中的 build/ 目录"
elif [ -n "$FRONTEND_SOURCE_DIR" ] && [ -d "$FRONTEND_SOURCE_DIR" ]; then
  echo "📁 从现有前端目录复制到 build/: $FRONTEND_SOURCE_DIR"
  rm -rf build
  mkdir -p build
  rsync -a "$FRONTEND_SOURCE_DIR"/ build/
else
  npm ci --force
  npm run build
fi

echo "📦 Step 1: 打包当前工作区..."
tar czf "$LOCAL_TAR" \
  --exclude='.git' \
  --exclude='.omx' \
  --exclude='.venv' \
  --exclude='.env' \
  --exclude='backend/data' \
  --exclude='dev.log' \
  --exclude='tmp' \
  .

echo "📤 Step 2: 上传到腾讯云..."
sshpass -p "$REMOTE_PASSWORD" scp "${SSH_ARGS[@]}" \
  "$LOCAL_TAR" \
  $REMOTE_USER@$REMOTE_HOST:/tmp/open-webui-anon-deploy.tar.gz

echo "🚀 Step 3: 解压到远端目录..."
sshpass -p "$REMOTE_PASSWORD" ssh "${SSH_ARGS[@]}" $REMOTE_USER@$REMOTE_HOST <<'ENDSSH'
set -e

APP_USER="$(whoami)"
REMOTE_PATH="/var/www/open-webui-anon"

sudo mkdir -p "$REMOTE_PATH"
sudo mkdir -p "$REMOTE_PATH/backend/data"
sudo mkdir -p "$REMOTE_PATH/logs"
sudo mkdir -p "$REMOTE_PATH/data"

TMP_DIR="/tmp/open-webui-anon-extract-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TMP_DIR"
tar xzf /tmp/open-webui-anon-deploy.tar.gz -C "$TMP_DIR"

sudo rsync -a --delete \
  --exclude 'backend/data' \
  --exclude '.env' \
  "$TMP_DIR"/ "$REMOTE_PATH"/

sudo mkdir -p "$REMOTE_PATH/logs"
sudo mkdir -p "$REMOTE_PATH/data"
sudo touch "$REMOTE_PATH/logs/openwebui-18081.log"

sudo tee "$REMOTE_PATH/.env" >/dev/null <<'EOF'
WEBUI_AUTH=False
ENABLE_BASE_MODELS_CACHE=False
RAG_EMBEDDING_MODEL_AUTO_UPDATE=False
PORT=18081
HOST=0.0.0.0
DATA_DIR=/var/www/open-webui-anon/data
FRONTEND_BUILD_DIR=/var/www/open-webui-anon/build
OPENAI_API_BASE_URL=
OPENAI_API_KEY=
DEFAULT_MODELS=gpt-5.4
EOF

sudo chown -R "$APP_USER:$APP_USER" "$REMOTE_PATH"

rm -rf "$TMP_DIR"
rm -f /tmp/open-webui-anon-deploy.tar.gz

echo "✅ 代码已同步到 $REMOTE_PATH"
echo "⚠️ 当前脚本负责同步代码和生成基础 .env，启动与 systemd 需单独执行"
ENDSSH

rm -f "$LOCAL_TAR"

echo "========================================="
echo "部署骨架执行完成"
echo "远端目录: $REMOTE_PATH"
echo "下一步: 在远端补 venv / 启动命令 / 反向代理"
echo "========================================="
