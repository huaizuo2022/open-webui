# AGENTS.md

## 项目说明

- 项目目录：`/Users/shang/Dev/open-webui-anon`
- 这是后续要长期定制修改的 **正式源码目录**
- 前端源码在 `src/`
- 后端源码在 `backend/`

## 腾讯云服务器登录信息

- 操作系统：`Ubuntu Server 24.04 LTS 64bit`
- 服务器：`ubuntu@43.160.238.95`
- SSH 密码：`4Uuk*~PW.(/37V$j`
- 默认优先使用 **密码 SSH**
- 默认禁用公钥认证，避免本机已有 key 导致 `Too many authentication failures`

推荐命令：

```bash
sshpass -p '4Uuk*~PW.(/37V$j' ssh \
  -o StrictHostKeyChecking=no \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no \
  ubuntu@43.160.238.95
```

## 远端部署约定

- 远端项目目录：`/var/www/open-webui-anon`
- 远端源码目录：`/var/www/open-webui-anon/src-current`
- 远端数据目录：`/var/www/open-webui-anon/data`
- 远端日志目录：`/var/www/open-webui-anon/logs`

## 端口约定

### 现有业务端口

以下端口已经被服务器上其他业务占用，**绝对不要动**：

- `8000`
- `8003`
- `8005`
- `8006`
- `8010`
- `8016`
- `80`
- `443`

### open-webui-anon 专用端口

- 新服务专用端口：`18081`
- 除非用户明确要求，不要改成已占用端口

## 当前 open-webui-anon 远端运行文件

- 启动脚本：`/var/www/open-webui-anon/start-18081.sh`
- Python 包装器：`/var/www/open-webui-anon/run_openwebui_18081.py`
- 日志文件：`/var/www/open-webui-anon/logs/openwebui-18081.log`

## 核心约束

1. **不要影响现有服务器业务**
2. **不要停止或覆盖现有服务**
3. **不要复用现有业务端口**
4. 所有新尝试优先使用 `18081`
5. 优先在远端本机 `curl 127.0.0.1:18081` 验证，再做公网验证

## 当前功能约定

- 已实现匿名免登录模式
- 当前匿名用户：`guest@localhost`
- 关键接口：
  - `/api/v1/auths/`：当前会话/匿名会话接口
  - `/api/v1/auths/signin`：前端旧登录链路兼容入口

## 相关文件

- `OPERATIONS.md`：更详细的运维说明
- `deploy-openwebui-tencent.sh`：腾讯云部署骨架脚本
