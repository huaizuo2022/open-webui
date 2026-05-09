# Internal-First Assistant Design

## Goal

把当前 `open-webui-anon` 调整为更明确的内网专用助手：

- 优先识别用户问题是否属于公司内部资源或内部排障场景
- 能直接命中已落地内网 skill 的请求，优先走内网 skill 查询
- 暂时无法命中具体 skill 的内网问题，也要先按“内网优先”策略回答，而不是直接退回通用互联网式回答
- 保持现有匿名聊天主链路可用，不破坏普通聊天、流式响应和消息持久化

## Scope

本期覆盖：

- 扩展内网问题识别逻辑
- 将路由结果分成“强制内网 skill 执行”和“仅注入内网优先提示”两类
- 为聊天链路增加仓库级的内网优先 system prompt 注入能力
- 保持当前已支持的强制 skill 执行体验：飞书文档、JIRA、天网日志
- 为更多内网问题建立统一识别入口，即使第一版还不直接执行对应 skill

本期不覆盖：

- 扩展 `builtin.py` 去直接执行所有有赞内部 skill
- 新增前端专门的“内网助手模式”切换 UI
- 重构现有工具系统或 skill 加载机制
- 对所有内部系统做结构化参数抽取和自动补参

## User Intent

用户要把这个项目的默认定位从“通用匿名聊天”进一步收敛成“内网专用助手”，并要求：

- 内网问题优先查内网资源
- 若无法准确匹配具体内网工具，也应先尝试以内网知识和内部排障语境处理
- 只有内网路径不足时才退回普通回答

## Existing Codebase Anchors

### Chat Routing

- `backend/open_webui/main.py:1854` 已在聊天主链路最前面调用 `detect_company_resource_route(...)`
- `backend/open_webui/main.py:1862` 已支持 `execute_internal_skill_request(...)` 强制执行内网 skill
- `backend/open_webui/main.py:1873` 已支持把 skill 结果格式化后直接返回给用户

### Resource Detection

- `backend/open_webui/utils/company_resources.py:13` 当前只识别少量公司资源场景
- 当前识别结果本质上是“是否强制路由到某个 skill”

### Prompt Injection

- `backend/open_webui/utils/payload.py:16` 提供 `apply_system_prompt_to_body(...)`
- `backend/open_webui/utils/middleware.py:2922` 会把当前 system message 保存到 `metadata['system_prompt']`
- OpenAI/Ollama 聊天请求都会走现有的 system prompt 注入链路

### Built-in Internal Skills

- `backend/open_webui/tools/builtin.py:53` 当前仅支持 3 个直接执行的内部 skill：
  - `zan-log-query`
  - `feishu-wiki-skill`
  - `zan-jira`

### Anonymous Mode Context

- `backend/open_webui/utils/auth.py:298` 匿名会话固定映射到 `guest@localhost`
- `OPERATIONS.md:66` 已说明当前项目默认处于匿名模式

## Design Summary

第一版采用“双层内网优先”策略：

1. 高置信度且当前后端可直接执行的内网请求，继续走“强制 skill 路由”
2. 其余被识别为内网问题的请求，不强制短路，而是在发给模型前注入更强的“内网优先”系统提示

这样可以同时满足两件事：

- 对已经打通的内网资源查询，直接返回可信结果
- 对尚未直接接入执行器的内部问题，也能稳定改变模型默认行为，让回答先以内网语境组织，再在必要时自然补充通用信息

## Proposed Architecture

### 1. 路由分类升级

把 `detect_company_resource_route(...)` 从单一“返回 skill 或 None”升级为统一的内网路由分类器。

返回结构分两类：

- `forced_skill_route`
  - 含义：已明确识别到具体内部资源，且后端当前能够直接执行对应 skill
  - 行为：立即执行 skill，跳过后续模型推理主链路
- `internal_priority_route`
  - 含义：用户问题明显属于内网场景，但当前没有可直接执行的内置 skill 适配
  - 行为：继续走聊天主链路，但注入更强的内网优先系统提示

建议统一返回结构：

```python
{
    "route_type": "forced_skill" | "internal_priority",
    "skill_id": "zan-jira" | None,
    "request": "原始用户问题",
    "resource_type": "jira" | "feishu_wiki" | "tianwang" | "apollo" | ...,
    "confidence": "high" | "medium",
    "reason": "命中的关键词或链接类型"
}
```

这一结构允许后续继续扩展，而不需要反复改主聊天流程。

### 2. 强制 skill 路由边界

第一版只把当前已经在 `builtin.py` 里落地执行的 3 类场景继续作为强制路由：

- JIRA / `zan-jira`
- 飞书 wiki / `feishu-wiki-skill`
- 天网日志 / `zan-log-query`

原因：

- 这 3 类已经具备本地命令适配和结果格式化逻辑
- 继续复用现有链路，改动最小，风险最低
- 避免为了“覆盖更多 skill 名称”而在第一版引入大量新的执行适配和失败面

这意味着像 Redis、RDS、Apollo、Dubbo、Kibana、Xiaolv、ES、HBase、DP 这类内部问题，第一版可以被识别为“内网优先问题”，但不会在后端直接强制执行对应 skill。

### 3. 内网优先提示层

为 `internal_priority_route` 新增一段仓库级提示模板，例如 helper：

- `build_internal_priority_system_prompt(...)`
- 或 `get_internal_assistant_policy_prompt(...)`

提示核心原则：

- 当前环境是公司内网专用助手
- 遇到内部排障、内部系统、内部数据核对、内部知识库问题时，优先按内网资源思路处理
- 优先使用内部系统名、内部术语、内部排查路径来组织回答
- 若缺少定位所需信息，要明确提出需要哪些内部信息，例如 traceId、JIRA 编号、飞书链接、配置 key、表名、应用名、环境等
- 只有在内部资源无法支撑时，才允许退回通用知识回答
- 不要一开始就给互联网通用教程式答案，除非用户问题本身不是内网场景

提示应尽量是“行为约束”，而不是绑定具体产品逻辑，避免和业务知识耦合过深。

`internal_priority_route` 第一版不做真正的二次模型调用，也不增加机器可解析的输出协议。第一版只做两件事：

- 在模型输入前注入一段更强的内网优先系统提示
- 通过提示约束模型先按内部资源、内部系统、内部排障语境组织回答

如果内网线索不足，模型应优先向用户索取最小必要的内部信息，而不是直接给出泛泛的互联网通用答案。但第一版不要求后端去解析模型输出状态，也不引入额外的响应协议。

### 4. 主聊天链路改造

在 `backend/open_webui/main.py` 的 `process_chat(...)` 中：

1. 先抽取用户文本
2. 调用升级后的内网路由分类器
3. 若命中 `forced_skill_route`
   - 保持现有逻辑：执行内网 skill、格式化结果、持久化消息、支持流式返回
4. 若命中 `internal_priority_route`
   - 不短路
   - 在调用 `process_chat_payload(...)` 之前，向 `form_data['messages']` 注入内网优先 system prompt
5. 未命中任何内网路由时，保持现有行为

关键约束：

- 不覆盖用户原有 system prompt，而是合并为单一最终 system message
- 避免重复注入；如果请求生命周期里已经注入过一次，应有幂等保护
- 不影响当前 `sources`、RAG、工具调用等后续流程
- 注入发生在 `process_chat_payload(...)` 之前，这样：
  - `metadata['system_prompt']` 记录的是最终生效的 prompt 版本
  - 现有 RAG/source-context/system-message merge 流程仍然只处理一份最终 system message
  - 若需要审计原始 system prompt，可额外在 `metadata['original_system_prompt']` 中保存注入前内容

最终 system prompt 的合并与落位规则固定如下：

1. 先把请求里已有的多个 system message 按现有顺序合并成单一字符串，记为 `original_system_prompt`
2. 若命中 `internal_priority_route`，生成 `internal_policy_prompt`
3. 按 `internal_policy_prompt + "\n\n" + original_system_prompt` 的顺序拼成最终 prompt
4. 若 `original_system_prompt` 为空，则最终 prompt 仅为 `internal_policy_prompt`
5. 若最终 prompt 已包含固定的内网策略标识文本，则不再重复注入
6. 把最终 prompt 作为单一 system message 写回 `messages[0]`
7. 删除其余已有 system message，确保进入 `process_chat_payload(...)` 前，消息列表里只保留这一条最终 system message

采用“内网策略在前、原始 system 在后”的顺序，是为了保证内网优先约束不会被后续用户自定义提示稀释，同时仍保留用户的任务上下文。

与后续 RAG/source-context merge 的关系固定为：

1. 先完成上述 system prompt 合并
2. 再进入 `process_chat_payload(...)`
3. `process_chat_payload(...)` 内部仍按现有机制保存 `metadata['system_prompt']`、注入 sources、merge system messages

这样系统里始终只有一个“最终待处理的 system message”，避免前后两次拼接造成优先级漂移。

### 5. 识别规则分层

建议把规则分成三层：

- 明确资源标识
  - 例：JIRA 链接、`ONLINE-12345`、`qima.feishu.cn/wiki/...`、traceId 样式串
- 明确系统关键词
  - 例：Apollo、Redis、RDS、MySQL、Dubbo、Kibana、Xiaolv、天网、效能平台、数仓、HBase、ES
- 泛内网语境词
  - 例：内网、公司内部、线上排查、发布、配置项、工单、知识库、埋点、链路、环境、应用名

路由判定优先级：

1. 明确资源标识 + 当前支持 skill：`forced_skill_route`
2. 明确系统关键词，且同时满足内部语境约束：`internal_priority_route`
3. 泛内网语境词达到阈值，且同时满足公司标识约束：`internal_priority_route`
4. 否则不处理

为避免误判，第一版增加以下收敛规则：

- 仅出现通用技术词但没有任何公司标识、内部系统名、内部动作语义时，不进入内网路由
  - 例：`Redis 原理是什么`、`MySQL 索引怎么建`
- `internal_priority_route` 至少满足以下条件之一：
  - 出现 1 个明确内部域名
  - 出现 1 个明确内部系统名，并同时出现 1 个内部动作语义或 1 个公司标识词
  - 出现 1 个通用技术词或内部对象词，并同时出现 1 个内部动作语义和 1 个公司标识词
  - 出现公司标识词，并同时出现 2 个来自不同桶的泛内网语境词
- 建议的“内部动作语义”包括：排查、发布、上线、配置核对、查日志、查工单、查数据、联调、回滚、血缘分析
- 建议的“内部系统名”包括：JIRA、飞书、天网、Kibana、Xiaolv、效能平台、数仓平台
- 建议的“通用技术词/内部对象词”包括：Apollo、Redis、RDS、Dubbo、HBase、ES、埋点、traceId
- 建议的“公司标识词”包括：内网、公司内部、qima、youzan、有赞、qima-inc、内部系统

额外负约束：

- `环境`、`应用名`、`配置项`、`链路` 这类高频工程词，单独出现时不计入内网命中分
- 通用数据库/中间件名只有在与内部动作语义和公司标识词同时共现时，才可计入内网命中
- `Redis`、`MySQL`、`RDS`、`Dubbo`、`Apollo`、`ES`、`HBase` 这类词单独出现时，不足以命中内网路由
- `traceId 怎么查`、`Dubbo 联调怎么做`、`排查 Redis 连接问题` 这类没有公司专属信号的问题，默认仍视为普通工程问答，不进入内网路由

### 6. 识别覆盖范围

第一版建议识别这些资源类型：

- `jira`
- `feishu_wiki`
- `tianwang`
- `kibana_httpgateway`
- `redis`
- `rds`
- `apollo`
- `dubbo`
- `dubbo_app`
- `xiaolv`
- `es`
- `hbase`
- `dp_platform`
- `user_behavior`
- `generic_internal`

其中：

- `jira`、`feishu_wiki`、`tianwang` 为强制 skill 路由候选
- 其余资源类型默认归入 `internal_priority_route`

### 7. 失败与回退策略

对 `forced_skill_route`：

- 若 skill 执行成功，直接返回结构化结果
- 若 skill 执行失败，不应直接报错终止整个聊天
- 应降级为 `internal_priority_route`，继续走模型回答，并附带“优先使用内网思路”的提示

第一版把“skill 执行失败”统一定义为任一条件成立：

- 返回结果存在顶层 `error`
- 主命令执行结果 `exit_code != 0`
- 能拿到结构化结果，但格式化后的展示文本为空、全空白、或不可展示

这样能满足用户的要求：“先尝试内网路径，失败后再普通回答”。

对 `internal_priority_route`：

- 模型应优先基于内部系统、内部流程、内部资源来组织回答
- 若缺少足够的内部定位信息，应优先向用户索取最小必要内部信息
- 不要一上来就退化成普通泛泛回答
- 第一版不做“输出状态机解析”，因此这里的“回退”不是后端协议，而是 system prompt 约束下的回答策略

因此，第一版真正有明确程序化回退闭环的只有 `forced_skill_route`：

1. 先尝试执行已接入的内网 skill
2. skill 失败后，降级为 `internal_priority_route`
3. 再继续走普通聊天主链路，但保留内网优先提示

## Prompt Strategy

建议新增一段统一模板，内容大致应包括：

- 角色：你运行在公司内网专用环境
- 目标：优先借助内网资源和内部排障语境帮助用户
- 优先级：内部信息、内部知识库、内部系统路径优先于公开互联网知识
- 行为：若用户问题显然属于内网问题，先围绕内部系统、日志、配置、工单、数据、发布、链路进行分析
- 缺失信息处理：缺少关键字段时，明确向用户索取最小必要信息
- 回退：只有在确认内部路径无法覆盖时，才使用通用常识补充

实现上应保持最小改动：

- 首选新增 helper 并复用 `apply_system_prompt_to_body(...)`
- 避免把长 prompt 字符串直接硬编码在 `main.py` 的流程分支里

## Data Flow

### A. 强制 skill 路由

1. 用户发起聊天
2. 提取用户文本
3. 分类器识别为 `forced_skill_route`
4. 执行内网 skill
5. 格式化结果并写入聊天消息
6. 直接返回响应

### B. 内网优先提示路由

1. 用户发起聊天
2. 提取用户文本
3. 分类器识别为 `internal_priority_route`
4. 注入内网优先 system prompt
5. 继续原有 `process_chat_payload(...)`
6. 走模型/工具/RAG 正常主链路
7. 返回带有内网优先语境的回答

## Failure Handling

- 内网分类器误判为普通问题：影响有限，维持现状
- 内网分类器误判为内网问题：主要影响是 system prompt 更偏内网，需要控制关键词阈值，避免过宽
- 强制 skill 超时/失败：降级到 `internal_priority_route`，不阻断主链路
- system prompt 重复注入：需通过 marker 或已有内容检测避免重复
- 流式响应路径：强制 skill 成功时继续沿用现有 SSE 返回逻辑

## Testing Strategy

建议新增或补充以下测试：

- `company_resources` 单测
  - JIRA 编号命中 `forced_skill_route`
  - 飞书 wiki 链接命中 `forced_skill_route`
  - traceId + 日志关键词命中 `forced_skill_route`
  - Apollo/Redis/RDS/Dubbo/Xiaolv 等关键词只有在满足收敛规则时才命中 `internal_priority_route`
  - 普通通用问题不命中任何内网路由
- 主聊天流程测试
  - 强制 skill 成功时直接返回 skill 结果
  - 强制 skill 失败时能回退到普通聊天流程
  - `internal_priority_route` 会注入内网优先 prompt
  - 非内网问题不注入该 prompt

还需要补充以下关键场景：

- prompt 注入幂等测试
  - 同一请求链路不会重复注入内网优先 prompt
- prompt 合并测试
  - 已有用户 system prompt 与内网策略合并后，最终 system message 顺序和内容符合预期
  - `metadata['original_system_prompt']` 与 `metadata['system_prompt']` 分别记录注入前后内容
  - 多个分散的 system message 会先折叠，再写回单一的 `messages[0]`
- 负例识别测试
  - 仅含 Redis/MySQL 等通用技术词，但没有内部语境时，不进入内网路由
  - `traceId 怎么查`、`Dubbo 联调怎么做`、`排查 Redis 连接问题` 这类问题默认不进入内网路由
- 强制 skill 失败一致性测试
  - 失败回退后，非流式和流式路径都能继续得到正常响应
  - 消息持久化与事件发射行为不因强制 skill 失败而中断
  - 顶层 `error`、`exit_code != 0`、格式化结果为空这 3 类失败都能稳定触发降级

## Implementation Notes

第一版实现建议坚持最小正确改动：

- 优先改 `company_resources.py`
- 在 `main.py` 加一层分支和降级处理
- 新增一个小型 prompt helper
- 暂不扩展 `builtin.py` 到更多内部 skill

这样可以先把“项目设定已经变成内网优先”的核心行为落地，再根据实际使用情况决定是否扩更多直接执行器。

## Out Of Scope Follow-ups

后续若验证效果稳定，可继续做：

- 为 Apollo、Redis、RDS、Kibana、Dubbo 等 skill 增加后端直接执行适配
- 在前端增加“内网专用助手”文案或模式标识
- 对不同内部问题类型生成更细分的 system prompt
- 引入可配置的内网路由规则表，而不是纯代码正则
