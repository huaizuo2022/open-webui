# 萤火 运维配置

## 项目关联
- 项目名称: `firefly`
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

### 本地重启脚本

前端 `build` + 后端重启的标准入口:

```bash
bash scripts/restart-local.sh
```

脚本会执行:

1. `npm run build`
2. 停掉本地 `8081` 旧进程
3. 使用 `.venv/bin/uvicorn open_webui.main:app --app-dir backend --host 127.0.0.1 --port 8081 --forwarded-allow-ips "*"` 重启后端
4. 轮询 `http://127.0.0.1:8081/api/version` 做健康检查

日志路径:

```bash
.runlogs/open-webui-8081.log
```

### 匿名模式
- 默认 `WEBUI_AUTH=False`
- 未登录用户会自动拿到 `guest@localhost` 会话
- 前端旧登录流也已兼容匿名访客

## 已知本地运行约定

当前项目不是完整官方源码 checkout，而是基于可运行包整理出的工作区，因此:

- 前端静态资源当前通过 `.env` 中的 `FRONTEND_BUILD_DIR` 指向本机已有 build
- 启动阶段跳过了 embedding/base-model 预热，避免首开被 Hugging Face 阻塞
- 工具表 schema 不一致时，启动阶段会跳过 tool dependency preload，保证主链路先可用

## 内部资料检索流程

本项目面向公司内部场景。遇到“查资料”“查内部知识”“排查内部问题”“核对内部数据/配置/流程”时，默认采用多源聚合检索，而不是单点优先。

### 默认检索顺序

1. 先判断问题类型：业务知识、产品规则、日志排查、配置排查、数据核对、接口联调、发布运维、源码实现。
2. 按问题类型并行组合内部来源：
   - `company-help-center`：业务知识、产品规则、内部流程
   - 对应内部 skill：日志、RDS、Redis、Apollo、Dubbo、Kibana、Xiaolv、ES、HBase、DP、JIRA、OPS
   - `lark-cli`：飞书 wiki、docx、多维表格
   - 本地源码与仓库文档：实现细节、约定、接口行为
3. 对多个来源做统一归并，输出综合结论，而不是只复述某一个来源。
4. 只有内部来源不足时，才补充公网资料。

### 输出要求

- 明确最终结论
- 标注关键证据来自哪些内部来源
- 若多个来源冲突，明确冲突点与当前更可信的依据
- 若仍缺信息，明确下一步需要的最小必要信息，例如 traceId、订单号、配置 key、表名、应用名、环境、飞书链接

### 飞书查询入口

飞书是内部资料的重要来源之一，但不是唯一来源。本项目统一通过 `lark-cli` 使用飞书查询能力。

常用 `lark-cli` 命令示例：

```bash
# 关键字搜索 Docs / Wiki / 表格文件
lark-cli docs +search --query "订单 类型" --format pretty

# 获取 wiki 节点信息
lark-cli wiki spaces get_node --params '{"token":"WIKI_TOKEN","obj_type":"wiki"}'

# 读取 docx 正文
lark-cli api GET "/open-apis/docx/v1/documents/DOC_TOKEN/raw_content"

# 查询 wiki 子节点
lark-cli api GET "/open-apis/wiki/v2/spaces/get_node" \
  --params '{"token":"WIKI_TOKEN","obj_type":"wiki"}'
```

说明：

- `lark-cli docs +search` 适合做飞书全文召回入口
- `lark-cli api` 适合补齐 CLI 子命令未封装的 OpenAPI 查询
- 受文档权限和当前登录态影响，部分私有文档可能无法直接读取

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
