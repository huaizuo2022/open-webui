# Redeem Code Credit Design

## Goal

为当前 `open-webui-anon` 增加一套可运营的兑换码积分体系：

- 淘宝售卖兑换码
- 管理员后台按批次生成兑换码，单码只能核销一次
- 登录用户核销后获得自定义积分
- 没有兑换码的用户只能免费聊天 5 次
- 超过免费次数后，按模型固定单价扣积分
- 支持匿名访客和登录用户两套免费次数口径

## Scope

本期仅覆盖：

- 后端积分账户、积分流水、兑换码、免费次数、模型价格配置
- 聊天发送前的额度校验与扣费
- 聊天失败时的免费次数/积分回滚
- 管理员后台：兑换码批次、兑换码明细、模型单价配置
- 前端用户侧：查看积分余额、免费次数状态、兑换码入口、额度不足提示

本期不覆盖：

- 淘宝订单自动回调
- 兑换码禁用、过期时间、渠道标签
- token 级计费
- 积分退款审批流
- 多次可用或部分消费型兑换码

## Product Rules

### 1. 兑换码

- 兑换码由管理员后台创建。
- 每个兑换码只允许使用一次。
- 每个兑换码绑定一个积分值，积分值可在后台创建时自定义。
- 兑换码核销后，积分充值到当前登录账号，不允许转移。
- 未登录用户不可直接核销兑换码。

### 2. 免费聊天次数

- 登录账号和匿名访客都拥有最多 5 次免费聊天次数。
- 已登录时优先按账号维度统计免费次数。
- 未登录时按设备标识统计免费次数。
- 免费次数只在真正发送一次聊天请求时消耗 1 次。

### 3. 积分扣费

- 免费次数用完后，按模型固定单价扣积分。
- 单价由管理员后台配置，单位为整数积分。
- 未配置价格的模型视为不可用付费聊天模型，应阻止发送并提示管理员配置。
- 若用户积分不足，阻止发送并提示兑换码充值。

### 4. 回滚

- 聊天请求在网关层通过后，如果模型调用或后续流程失败，本次免费次数或积分扣费必须回滚。
- 回滚必须可审计，写入积分流水或消耗事件记录。

## Existing Codebase Anchors

### 后端

- 匿名会话入口在 `backend/open_webui/routers/auths.py`，当前匿名用户固定为 `guest@localhost`。
- 会话用户返回接口在 `GET /api/v1/auths/`。
- OpenAI 聊天入口在 `backend/open_webui/routers/openai.py` 的 `POST /chat/completions`。
- Ollama 聊天入口在 `backend/open_webui/routers/ollama.py` 的 `POST /chat/completions`。
- 数据库模型在 `backend/open_webui/models/`。
- Alembic 迁移在 `backend/open_webui/migrations/versions/`。

### 前端

- 会话用户信息通过 `src/lib/apis/auths/index.ts` 的 `getSessionUser` 获取。
- 当前会话用户存储在 `src/lib/stores/index.ts` 的 `user` store。
- 管理后台导航在 `src/routes/(app)/admin/+layout.svelte`。
- 管理后台页面入口在 `src/routes/(app)/admin/**`。
- 聊天输入入口在 `src/lib/components/chat/MessageInput.svelte`。

## Proposed Architecture

### 1. 数据层

新增 5 组持久化对象：

- `credit_account`
  - 每个登录用户一条余额记录
- `credit_transaction`
  - 记录充值、消费、回滚、人工调整
- `redeem_code_batch`
  - 管理员批量创建兑换码的批次
- `redeem_code`
  - 单个兑换码及核销状态
- `usage_quota`
  - 记录 `user` 或 `device` 主体的免费次数

模型单价优先复用现有 `model.meta` 或 `model.params` 扩展字段，避免新增独立价格表。第一版建议在 `model.meta.credit_cost` 存整数积分价。

### 2. 业务服务层

新增一个独立的 billing/redeem 服务模块，职责集中：

- 解析当前计费主体
- 读取并校验免费次数
- 读取模型积分价格
- 进行积分预扣或免费次数预占
- 成功确认或失败回滚
- 核销兑换码并入账

不把这些逻辑散落到 `auths.py`、`openai.py`、`ollama.py` 各处。

### 3. 接入层

聊天发送链路接入一个统一 guard：

1. 识别当前主体
2. 判断该模型是否配置价格
3. 优先消耗免费次数
4. 免费次数不足时扣积分
5. 调用现有聊天逻辑
6. 根据结果确认消耗或回滚

OpenAI 和 Ollama 两条聊天链路都必须接入，避免计费绕过。

### 4. 前端

增加三块前端能力：

- 用户视角
  - 显示积分余额
  - 显示剩余免费次数
  - 提供兑换码输入入口
  - 在额度不足时弹出明确提示
- 管理后台
  - 兑换码批次管理页
  - 兑换码明细页
  - 模型积分价格配置页
- API 封装
  - 新增 credits/redeem/admin 相关接口封装

## Data Model

### credit_account

- `id`
- `user_id` unique
- `balance`
- `total_recharged`
- `total_consumed`
- `created_at`
- `updated_at`

### credit_transaction

- `id`
- `user_id`
- `type` (`redeem`, `consume`, `rollback`, `adjust`)
- `amount`
- `balance_after`
- `model_id` nullable
- `chat_id` nullable
- `redeem_code_id` nullable
- `remark` nullable
- `created_at`

### redeem_code_batch

- `id`
- `batch_name`
- `credit_amount`
- `quantity`
- `created_by`
- `created_at`

### redeem_code

- `id`
- `batch_id`
- `code` unique
- `credit_amount`
- `status` (`unused`, `used`)
- `used_by_user_id` nullable
- `used_at` nullable
- `created_at`

### usage_quota

- `id`
- `subject_type` (`user`, `device`)
- `subject_id`
- `free_chat_used`
- `free_chat_limit`
- `created_at`
- `updated_at`

唯一约束建议为 `(subject_type, subject_id)`。

## Identity Strategy For Anonymous Users

匿名用户免费次数按设备标识统计。第一版可采用以下顺序：

1. 前端本地生成稳定 `device_id`，存于 `localStorage`
2. 每次聊天和会话请求通过请求头透传，如 `X-OWUI-Device-Id`
3. 后端对该值做格式校验和兜底

如果没有 `device_id`，后端可拒绝匿名计费型聊天请求并要求前端刷新会话。

## API Surface

### 用户接口

- `GET /api/v1/credits/me`
  - 返回积分余额、累计充值、累计消费、免费次数状态
- `POST /api/v1/credits/redeem`
  - 当前登录用户核销兑换码

### 管理接口

- `POST /api/v1/admin/redeem-codes/batches`
  - 创建兑换码批次并批量生成兑换码
- `GET /api/v1/admin/redeem-codes/batches`
  - 查询批次列表
- `GET /api/v1/admin/redeem-codes`
  - 查询兑换码明细
- `GET /api/v1/admin/redeem-codes/batches/{id}/export`
  - 导出批次兑换码

模型价格配置优先复用现有模型管理接口，通过模型更新接口写入 `meta.credit_cost`。

## Admin UI

### 1. Redeem Code Batches

- 新建批次
- 输入批次名、积分面额、生成数量
- 查看已用/未用数量
- 导出兑换码

### 2. Redeem Code Details

- 按批次筛选
- 查看兑换码、积分值、状态、使用人、使用时间

### 3. Model Credit Pricing

- 为模型设置固定积分单价
- 支持启用/停用
- 未配置价格时在 UI 标记为不可付费

## Failure Handling

- 兑换码不存在、已使用：返回 400 级业务错误
- 非登录用户核销：返回 401/403
- 模型未配置价格：返回 400 级业务错误
- 免费次数用完且积分不足：返回 402 语义化业务错误或统一 400 + 特定错误码
- 聊天执行失败：必须触发回滚
- 回滚失败：写日志并上报错误，禁止静默吞掉

## Testing Strategy

### 后端

- 新增纯服务级单测，覆盖：
  - 免费次数递减
  - 登录用户积分扣减
  - 匿名设备免费次数
  - 兑换码核销幂等
  - 模型未配置价格时阻止发送
  - 聊天失败时回滚

### 前端

- 为管理 API 封装补基础测试
- 为关键纯函数或表单校验补测试
- 至少执行 `npm run check`

### 集成验证

- 匿名用户前 5 次可发，第 6 次被拦截
- 登录用户前 5 次可发，无积分时第 6 次被拦截
- 登录用户核销兑换码后可继续聊天
- 不同模型按不同价格扣分

## Risks

- 当前仓库匿名模式把未登录流量映射为 `guest@localhost`，若只按用户 ID 计数会导致所有匿名共享 5 次额度，必须显式引入 `device_id`
- 聊天入口有 OpenAI 与 Ollama 两套实现，漏接一边会形成计费绕过
- 若把模型价格藏在任意 JSON 字段但未统一约束，容易出现前后端字段名漂移

## Recommended Delivery Order

1. 数据模型与迁移
2. 计费服务与兑换码服务
3. 聊天入口 guard + 回滚
4. 用户查询/核销 API
5. 管理端 API
6. 管理端页面
7. 用户端余额与提示
8. 回归验证
