# AGENTS.md

## 项目说明

- 项目目录：`/Users/shang/Dev/open-webui-anon`
- 这是后续要长期定制修改的 **正式源码目录**
- 前端源码在 `src/`
- 后端源码在 `backend/`

## Skill 自动加载约定（重要）

**遇到以下场景时，必须立即加载对应 skill，不得询问用户：**

| 场景关键词 | 应加载的 Skill |
|-----------|---------------|
| 飞书 wiki/docx/bitable 查询、读取飞书文档、解析飞书 PRD 图片 | `feishu-wiki-skill` |
| 查询天网日志、traceId 分析、查报错 | `zan-log-query` |
| 查 HTTP 网关日志、httpgateway 日志 | `zan-kibana-query` |
| 查 Redis 缓存、redis 查询 | `zan-redis-query` |
| 查 MySQL/RDS 数据、执行 SQL | `zan-rds-ops` |
| 查 Apollo 配置 | `zan-apollo-query` |
| 调用 Dubbo 接口、dubbo invoke | `zan-dubbo-invoke` |
| 查询 Dubbo 接口归属应用 | `zan-dubbo-query-app` |
| 查 ES 数据 | `zan-es-query` |
| 查 HBase 数据 | `zan-hbase-query` |
| 查用户行为、埋点数据 | `zan-user-behavior-query` |
| 查大数据平台 Hive/Spark SQL | `zan-dp-platform` |
| 查询 JIRA 工单（如 ONLINE-xxx） | `zan-jira` |
| 效能平台需求查询、xiaolv | `xiaolv-skill` |
| OPS 发布、查询应用详情 | `qima-ops` |
| 获取 OPS Token、配置 zan-tools | `ops-cookie` |
| 查业务术语/数据表血缘 | `zan-dp-platform` |

**执行流程：**
1. 识别到关键词后，立即调用 `skill(name)` 工具加载对应 skill
2. 加载后按照 skill 说明执行，无需用户确认
3. skill 执行前必须先执行 `bash scripts/pre-execute.sh <skill-name>`

## 核心约定

1. 本机源码项目，不涉及远程部署
2. 远程部署在 `/Users/shang/Dev/open-webui-anon-remote/`

## 当前功能约定

- 已实现匿名免登录模式
- 当前匿名用户：`guest@localhost`
- 关键接口：
  - `/api/v1/auths/`：当前会话/匿名会话接口
  - `/api/v1/auths/signin`：前端旧登录链路兼容入口

## 飞书文档读取

使用 `lark-cli` 命令读取飞书文档：

```bash
# 获取 wiki 节点信息
lark-cli wiki spaces get_node --params '{"token":"WIKI_TOKEN","obj_type":"wiki"}'

# 读取 docx 内容
lark-cli api GET "/open-apis/docx/v1/documents/DOC_TOKEN/raw_content"

# 列出 wiki 子节点
lark-cli wiki spaces list_children --params '{"token":"WIKI_TOKEN"}'
```

## 相关文件

- `OPERATIONS.md`：更详细的运维说明