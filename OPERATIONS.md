# Open WebUI Anon 运维配置

## 项目关联
- 项目名称: `open-webui-anon`
- 项目路径: `~/Dev/open-webui-anon/`
- 生产服务器: `43.160.238.95` (腾讯云)
- 默认运行端口: `8081` (本地)

## 腾讯云服务器认证信息

### SSH 访问
- 操作系统: `Ubuntu Server 24.04 LTS 64bit`
- 服务器: `ubuntu@43.160.238.95`
- 密码: `4Uuk*~PW.(/37V$j`
- 推荐方式: 密码 SSH，显式禁用公钥认证，避免本机 agent/key 干扰

### 推荐 SSH 命令
```bash
PASSWORD='4Uuk*~PW.(/37V$j'
SERVER='ubuntu@43.160.238.95'

sshpass -p "$PASSWORD" ssh \
  -o StrictHostKeyChecking=no \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no \
  "$SERVER"
```

### 单条远程命令
```bash
PASSWORD='4Uuk*~PW.(/37V$j'
SERVER='ubuntu@43.160.238.95'

sshpass -p "$PASSWORD" ssh \
  -o StrictHostKeyChecking=no \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no \
  "$SERVER" "pwd"
```

## 部署建议目录

建议在服务器上使用单独目录，避免和 VelvetChat/Airi 项目混用:

```bash
/var/www/open-webui-anon
```

建议的远端结构:

```bash
/var/www/open-webui-anon/
  backend/
  data/
  frontend/
  .env
  logs/
```

## 本项目当前本地运行要点

### 本地服务地址
- 首页: `http://127.0.0.1:8081`
- 匿名会话接口: `http://127.0.0.1:8081/api/v1/auths/`

### 匿名模式
- 默认 `WEBUI_AUTH=False`
- 未登录用户会自动拿到 `guest@localhost` 会话
- 前端旧登录流也已兼容匿名访客

## 已知本地运行约定

当前项目不是完整官方源码 checkout，而是基于可运行包整理出的工作区，因此:

- 前端静态资源当前通过 `.env` 中的 `FRONTEND_BUILD_DIR` 指向本机已有 build
- 启动阶段跳过了 embedding/base-model 预热，避免首开被 Hugging Face 阻塞
- 工具表 schema 不一致时，启动阶段会跳过 tool dependency preload，保证主链路先可用

## 后续部署前建议

1. 为 `open-webui-anon` 准备独立远端目录，不复用 VelvetChat 目录。
2. 为远端准备独立 `data/` 和日志目录。
3. 确认远端 Python 版本、虚拟环境、反向代理和 systemd/pm2 方案。
4. 明确对外访问域名或至少规划一个 Nginx 入口。

## 参考来源

以下文件提供了当前腾讯云服务器的现成经验:

- `/Users/shang/Dev/VelvetChat/OPERATIONS.md`
- `/Users/shang/Dev/VelvetChat/deploy-backend.sh`
- `/Users/shang/Dev/VelvetChat/deploy-airi-web.sh`
- `/Users/shang/.codex/skills/tencent-cloud-password-ssh/SKILL.md`
