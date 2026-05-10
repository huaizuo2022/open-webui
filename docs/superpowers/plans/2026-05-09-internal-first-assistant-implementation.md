# Internal-First Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `open-webui-anon` 项目调整为内网专用助手：强制 skill 路由 3 类已落地 skill，扩展内网识别并为其他内网问题注入内网优先 system prompt

**Architecture:** 双层内网优先策略 - 强制 skill 路由 + 内网优先 prompt 注入。核心改动在 `company_resources.py` 路由分类器 + `main.py` 聊天链路 + 新增 prompt helper

**Tech Stack:** Python (FastAPI), Open WebUI 现有聊天链路, 内置 skill 执行器

---

## File Structure

```
backend/open_webui/utils/company_resources.py  # 扩展内网路由分类器
backend/open_webui/main.py                      # 聊天链路改造
backend/open_webui/utils/internal_priority_prompt.py  # 新增: 内网优先 prompt helper
backend/open_webui/test/test_company_resources.py    # 新增: 路由分类单测
```

---

## Task 1: 扩展 company_resources.py 路由分类器

**Files:**
- Modify: `backend/open_webui/utils/company_resources.py:13-117`
- Test: 需要新增单测文件

- [ ] **Step 1: 阅读现有 company_resources.py 实现**

```bash
read /Users/shang/Dev/open-webui-anon/backend/open_webui/utils/company_resources.py
```

- [ ] **Step 2: 在 company_resources.py 中新增路由分类返回结构**

在文件顶部定义返回结构：
```python
import re
from typing import Optional
from dataclasses import dataclass
from enum import Enum

class RouteType(str, Enum):
    FORCED_SKILL = "forced_skill"
    INTERNAL_PRIORITY = "internal_priority"
    NONE = "none"

@dataclass
class InternalRouteResult:
    route_type: RouteType
    skill_id: Optional[str] = None
    request: str = ""
    resource_type: Optional[str] = None
    confidence: str = "medium"
    reason: str = ""

    def as_dict(self) -> dict:
        """兼容现有调用方 dict.get('skill_id') 方式"""
        return {
            'route_type': self.route_type.value if isinstance(self.route_type, RouteType) else self.route_type,
            'skill_id': self.skill_id,
            'request': self.request,
            'resource_type': self.resource_type,
            'confidence': self.confidence,
            'reason': self.reason,
        }

    def __bool__(self):
        """保持与原 dict 真值行为一致：None route 视为 False"""
        return self.route_type != RouteType.NONE
```

- [ ] **Step 3: 重写 detect_company_resource_route 函数，返回 InternalRouteResult**

```python
def detect_company_resource_route(user_message: str) -> InternalRouteResult:
    # 1. 明确资源标识 + 当前支持 skill -> forced_skill_route
    # 2. 明确系统关键词 + 内部语境约束 -> internal_priority_route
    # 3. 公司标识 + 泛内网语境 -> internal_priority_route
    # 4. 否则 -> none
    pass
```

- [ ] **Step 4: 定义内网识别规则的分桶关键词**

在文件顶部新增：
```python
STRONG_INTERNAL_SYSTEMS = {"jira", "飞书", "feishu", "天网", "kibana", "xiaolv", "效能平台", "数仓平台", "日志"}
WEAK_TECH_TERMS = {"apollo", "redis", "rds", "dubbo", "hbase", "es", "埋点", "traceid"}
INTERNAL_ACTIONS = {"排查", "发布", "上线", "配置核对", "查日志", "查工单", "查数据", "联调", "回滚", "血缘分析"}
COMPANY_MARKERS = {"内网", "公司内部", "qima", "youzan", "有赞", "qima-inc", "内部系统"}
GENERIC_TERMS = {"环境", "应用名", "配置项", "链路"}
```

- [ ] **Step 5: 实现路由判定逻辑**

```python
def detect_company_resource_route(user_message: str) -> InternalRouteResult:
    text = user_message.lower()

    # 规则 1: 明确资源标识 -> forced_skill_route
    if re.search(r'https?://[^\s]*jira\.qima-inc\.com/', text) or re.search(r'\b[A-Z][A-Z0-9]+-\d+\b', user_message):
        return InternalRouteResult(
            route_type=RouteType.FORCED_SKILL,
            skill_id="zan-jira",
            request=user_message,
            resource_type="jira",
            confidence="high",
            reason="jira_id_detected"
        )

    if 'qima.feishu.cn/wiki/' in text:
        return InternalRouteResult(
            route_type=RouteType.FORCED_SKILL,
            skill_id="feishu-wiki-skill",
            request=user_message,
            resource_type="feishu_wiki",
            confidence="high",
            reason="feishu_wiki_link_detected"
        )

    trace_like = re.search(r'\b[a-z0-9]+(?:-[a-z0-9]+){3,}\b', text)
    if trace_like and any(keyword in text for keyword in ('天网', '日志', 'traceid', 'trace id', '报错')):
        return InternalRouteResult(
            route_type=RouteType.FORCED_SKILL,
            skill_id="zan-log-query",
            request=user_message,
            resource_type="tianwang",
            confidence="high",
            reason="trace_id_with_log_keyword"
        )

    # 规则 1b: trace_id + app_name pattern (保留原有第二次检测逻辑)
    if trace_like and re.search(r'\b[a-z][a-z0-9]+(?:-[a-z0-9]+)+\b', text):
        return InternalRouteResult(
            route_type=RouteType.FORCED_SKILL,
            skill_id="zan-log-query",
            request=user_message,
            resource_type="tianwang",
            confidence="high",
            reason="trace_id_with_app_name"
        )

    # 规则 2: 强内部系统名单独出现 -> internal_priority_route
    for system in STRONG_INTERNAL_SYSTEMS:
        if system in text:
            return InternalRouteResult(
                route_type=RouteType.INTERNAL_PRIORITY,
                request=user_message,
                resource_type="generic_internal",
                confidence="medium",
                reason=f"strong_internal_system:{system}"
            )

    # 规则 3: 弱技术词 + 内部动作语义 或 公司标识词 -> internal_priority_route
    has_weak_term = any(term in text for term in WEAK_TECH_TERMS)
    has_action = any(action in text for action in INTERNAL_ACTIONS)
    has_company_marker = any(marker in text for marker in COMPANY_MARKERS)

    if has_weak_term and (has_action or has_company_marker):
        reason = f"weak_term_with_{'action' if has_action else 'company_marker'}"
        return InternalRouteResult(
            route_type=RouteType.INTERNAL_PRIORITY,
            request=user_message,
            resource_type="generic_internal",
            confidence="medium",
            reason=reason
        )

    # 规则 4: 公司标识 + 2 个不同桶的泛内网语境 -> internal_priority_route
    if has_company_marker:
        generic_matches = sum(1 for term in GENERIC_TERMS if term in text)
        if generic_matches >= 2:
            return InternalRouteResult(
                route_type=RouteType.INTERNAL_PRIORITY,
                request=user_message,
                resource_type="generic_internal",
                confidence="low",
                reason="company_marker_with_multiple_generic_terms"
            )

    return InternalRouteResult(route_type=RouteType.NONE, request=user_message)
```

- [ ] **Step 6: 运行测试验证**

```bash
cd /Users/shang/Dev/open-webui-anon/backend
python -c "
from open_webui.utils.company_resources import detect_company_resource_route

# 测试 forced_skill
result = detect_company_resource_route('查一下 ONLINE-12345 这个工单')
print(f'JIRA: {result.route_type} - {result.skill_id}')

result = detect_company_resource_route('看看这个飞书文档 qima.feishu.cn/wiki/ABC123')
print(f'飞书: {result.route_type} - {result.skill_id}')

result = detect_company_resource_route('查下这个 traceId abc-def-ghi-jkl')
print(f'天网: {result.route_type} - {result.skill_id}')

# 测试 internal_priority
result = detect_company_resource_route('Apollo 配置怎么查')
print(f'内部系统: {result.route_type} - {result.reason}')

result = detect_company_resource_route('Redis 连接超时怎么排查')
print(f'弱技术词+动作: {result.route_type} - {result.reason}')

# 测试不命中
result = detect_company_resource_route('Redis 原理是什么')
print(f'普通问题: {result.route_type}')
"
```

Expected: JIRA/飞书/天网 -> forced_skill, Apollo/Redis+动作 -> internal_priority, Redis原理 -> none

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/utils/company_resources.py
git commit -m "feat: 扩展内网路由分类器，区分 forced_skill 和 internal_priority"
```

---

## Task 2: 创建内网优先 prompt helper

**Files:**
- Create: `backend/open_webui/utils/internal_priority_prompt.py`

- [ ] **Step 1: 创建 prompt helper 文件**

```bash
touch /Users/shang/Dev/open-webui-anon/backend/open_webui/utils/internal_priority_prompt.py
```

- [ ] **Step 2: 写入 prompt 生成函数**

```python
"""内网优先 system prompt 生成器"""

INTERNAL_PRIORITY_PROMPT = """你运行在公司内网专用环境，优先借助内网资源和内部排障语境帮助用户。

关键约束：
1. 内部信息、内部知识库、内部系统路径优先于公开互联网知识
2. 若用户问题属于内部排障、内部系统、内部数据核对场景，先围绕内部系统、日志、配置、工单、数据、发布、链路进行分析
3. 若缺少定位所需信息（如 traceId、JIRA 编号、飞书链接、配置 key、表名、应用名、环境），优先向用户索取最小必要信息
4. 只有在确认内部路径无法覆盖时，才使用通用常识补充
5. 不要一开始就给互联网通用教程式答案

记住：你首要是内网排障助手，其次才是通用知识来源。
"""

INTERNAL_MARKER = "你运行在公司内网专用环境"


def build_internal_priority_prompt(original_system_prompt: str = "") -> str:
    """
    构建最终的内网优先 system prompt

    Args:
        original_system_prompt: 用户或上游已有的 system prompt

    Returns:
        合并后的最终 system prompt
    """
    if original_system_prompt:
        # 检查是否已经注入过
        if INTERNAL_MARKER in original_system_prompt:
            return original_system_prompt
        return f"{INTERNAL_PRIORITY_PROMPT}\n\n{original_system_prompt}"
    return INTERNAL_PRIORITY_PROMPT


def has_internal_priority_injected(messages: list) -> bool:
    """检查 messages 中是否已经注入过内网优先 prompt"""
    for msg in messages:
        if isinstance(msg, dict) and msg.get('role') == 'system':
            content = msg.get('content', '')
            if INTERNAL_MARKER in content:
                return True
    return False
```

- [ ] **Step 3: 运行测试验证**

```bash
cd /Users/shang/Dev/open-webui-anon/backend
python -c "
from open_webui.utils.internal_priority_prompt import build_internal_priority_prompt, has_internal_priority_injected

# 测试无 original prompt
result = build_internal_priority_prompt()
print(f'无 original: {len(result)} chars')

# 测试有 original prompt
result = build_internal_priority_prompt('你是一个有帮助的助手')
print(f'有 original: 包含内网标记' if '你运行在公司内网专用环境' in result else 'ERROR')

# 测试幂等
result = build_internal_priority_prompt('你运行在公司内网专用环境')
print(f'幂等: 原样返回' if result == '你运行在公司内网专用环境' else 'ERROR')

# 测试检测
messages = [{'role': 'system', 'content': '你运行在公司内网专用环境'}]
print(f'检测到注入: {has_internal_priority_injected(messages)}')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/utils/internal_priority_prompt.py
git commit -m "feat: 新增内网优先 prompt helper"
```

---

## Task 3: 改造 main.py 聊天链路

**Files:**
- Modify: `backend/open_webui/main.py:1850-1930`
- Test: 现有集成测试

- [ ] **Step 1: 阅读 main.py 相关代码段**

```bash
read /Users/shang/Dev/open-webui-anon/backend/open_webui/main.py:1850-1930
```

- [ ] **Step 2: 在 main.py 顶部导入新模块**

在 import 区域添加：
```python
from open_webui.utils.internal_priority_prompt import build_internal_priority_prompt, has_internal_priority_injected
```

- [ ] **Step 3: 修改 process_chat 函数中的路由处理逻辑**

找到 `process_chat` 函数中 `forced_company_route = detect_company_resource_route(...)` 这一段

```python
# 原代码 around line 1854
from open_webui.utils.company_resources import RouteType

forced_company_route = detect_company_resource_route(extract_user_message_text(form_data, metadata))

# 兼容处理：dataclass 有 as_dict() 方法，调用方仍可用 dict 方式访问
route_dict = forced_company_route.as_dict() if hasattr(forced_company_route, 'as_dict') else forced_company_route

# 区分 forced_skill 和 internal_priority
if forced_company_route.route_type == RouteType.FORCED_SKILL:
    # 现有 forced skill 逻辑... (使用 route_dict 保持兼容)

# 新增: 处理 internal_priority_route
elif forced_company_route.route_type == RouteType.INTERNAL_PRIORITY:
    # 注入内网优先 prompt
    messages = form_data.get('messages', [])
    if not has_internal_priority_injected(messages):
        original_system = ""
        for msg in messages:
            if isinstance(msg, dict) and msg.get('role') == 'system':
                original_system = msg.get('content', '')
                break

        final_prompt = build_internal_priority_prompt(original_system)

        # 替换/合并 system message
        new_messages = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get('role') == 'system':
                continue  # 跳过旧的
            new_messages.append(msg)

        new_messages.insert(0, {'role': 'system', 'content': final_prompt})
        form_data['messages'] = new_messages

        # 记录到 metadata 供审计
        metadata['original_system_prompt'] = original_system
        metadata['system_prompt'] = final_prompt
```

- [ ] **Step 4: 修改强制 skill 失败的降级逻辑**

在强制 skill 执行后的 except 块或 result 检查处，找到 skill 执行失败的判定逻辑，添加降级处理：

```python
# 假设 skill 执行后检查失败的逻辑位置
skill_id = route_dict.get('skill_id')
tool_result = await execute_internal_skill_request(
    skill_id=skill_id,
    request=route_dict.get('request', ''),
)

# 检查是否失败 (三个条件任一成立即失败)
skill_failed = False
try:
    parsed_result = json.loads(tool_result)
    if parsed_result.get('error'):
        skill_failed = True
    if parsed_result.get('exit_code', 0) != 0:
        skill_failed = True
    # 格式化结果为空也算失败
    formatted = format_company_route_result(skill_id, parsed_result)
    if not formatted or not formatted.strip():
        skill_failed = True
except:
    skill_failed = True

if skill_failed:
    # 降级为 internal_priority_route
    log.info(f'Skill {skill_id} failed (exit_code={parsed_result.get("exit_code", 0)}, has_error={bool(parsed_result.get("error"))}), falling back to internal_priority_route')

    # 使用 helper 注入内网优先 prompt
    form_data, metadata = apply_internal_priority_to_form_data(form_data, metadata)

    # 清除 skill_id，标记为非 forced route
    # 然后继续走正常的 process_chat_payload 链路
```

- [ ] **Step 5: 简化实现 - 分离 concerns**

为了避免在 main.py 中写太多逻辑，可以把降级处理提取到 `internal_priority_prompt.py`：

```python
# 在 internal_priority_prompt.py 中新增
def apply_internal_priority_to_form_data(form_data: dict, metadata: dict = None) -> tuple[dict, dict]:
    """
    为 form_data 注入内网优先 prompt

    Returns: (修改后的 form_data, 更新后的 metadata)
    """
    messages = form_data.get('messages', [])
    metadata = metadata or {}

    if has_internal_priority_injected(messages):
        return form_data, metadata

    original_system = ""
    new_messages = []
    for msg in messages:
        if isinstance(msg, dict) and msg.get('role') == 'system':
            original_system = msg.get('content', '')
            continue
        new_messages.append(msg)

    final_prompt = build_internal_priority_prompt(original_system)
    new_messages.insert(0, {'role': 'system', 'content': final_prompt})

    form_data['messages'] = new_messages
    metadata['original_system_prompt'] = original_system
    metadata['system_prompt'] = final_prompt

    return form_data, metadata
```

- [ ] **Step 6: 用简化的 helper 重写 main.py 中的调用**

```python
# 在 main.py 中
elif forced_company_route.route_type == RouteType.INTERNAL_PRIORITY:
    form_data, metadata = apply_internal_priority_to_form_data(form_data, metadata)
```

- [ ] **Step 7: 运行现有测试验证没有破坏原有功能**

```bash
cd /Users/shang/Dev/open-webui-anon/backend
python -m pytest open_webui/test/test_anonymous_auth.py -v
```

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/main.py backend/open_webui/utils/internal_priority_prompt.py
git commit -m "feat: 聊天链路集成内网优先 prompt 注入"
```

---

## Task 4: 编写路由分类单测

**Files:**
- Create: `backend/open_webui/test/test_company_resources.py`

- [ ] **Step 1: 创建测试文件**

```bash
touch /Users/shang/Dev/open-webui-anon/backend/open_webui/test/test_company_resources.py
```

- [ ] **Step 2: 写入测试用例**

```python
import pytest
from open_webui.utils.company_resources import detect_company_resource_route, RouteType


class TestDetectCompanyResourceRoute:

    def test_jira_forced_skill(self):
        result = detect_company_resource_route('查一下 ONLINE-12345 这个工单')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-jira'
        assert result.confidence == 'high'

    def test_jira_link_forced_skill(self):
        result = detect_company_resource_route('看看 https://jira.qima-inc.com/browse/ONLINE-98765')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-jira'

    def test_feishu_wiki_forced_skill(self):
        result = detect_company_resource_route('查下这个飞书文档 qima.feishu.cn/wiki/ABC123')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'feishu-wiki-skill'

    def test_tianwang_forced_skill(self):
        result = detect_company_resource_route('traceId abc-def-ghi-jkl 报错怎么查')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-log-query'

    def test_apollo_internal_priority(self):
        result = detect_company_resource_route('Apollo 配置怎么查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_redis_with_action_internal_priority(self):
        result = detect_company_resource_route('Redis 连接超时怎么排查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_redis_with_company_marker_internal_priority(self):
        result = detect_company_resource_route('我们内网的 Redis 怎么连')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_xiaolv_internal_priority(self):
        result = detect_company_resource_route('Xiaolv 需求怎么查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_redis_principle_no_route(self):
        result = detect_company_resource_route('Redis 原理是什么')
        assert result.route_type == RouteType.NONE

    def test_mysql_basic_no_route(self):
        result = detect_company_resource_route('MySQL 索引怎么建')
        assert result.route_type == RouteType.NONE

    def test_dubbo_question_no_route(self):
        result = detect_company_resource_route('Dubbo 联调怎么做')
        assert result.route_type == RouteType.NONE

    def test_traceid_pure_no_route(self):
        result = detect_company_resource_route('traceId 怎么查')
        assert result.route_type == RouteType.NONE

    def test_traceid_with_app_name_forced_skill(self):
        result = detect_company_resource_route('查下 pay-opcenter 这个应用的 abc-def-ghi-jkl 日志')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-log-query'

    def test_feishu_keyword_internal_priority(self):
        result = detect_company_resource_route('飞书文档怎么查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_feishu_english_internal_priority(self):
        result = detect_company_resource_route('feishu 文档怎么查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_as_dict_compatibility(self):
        """测试 as_dict() 方法保持与原 dict 兼容"""
        result = detect_company_resource_route('查一下 ONLINE-12345')
        d = result.as_dict()
        assert d['skill_id'] == 'zan-jira'
        assert d['route_type'] == 'forced_skill'

    def test_bool_behavior(self):
        """测试 __bool__ 与原 dict 真值行为一致"""
        result_forced = detect_company_resource_route('查一下 ONLINE-12345')
        result_none = detect_company_resource_route('今天天气怎么样')

        assert bool(result_forced) == True  # 有路由
        assert bool(result_none) == False  # 无路由
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/shang/Dev/open-webui-anon/backend
python -m pytest open_webui/test/test_company_resources.py -v
```

Expected: 所有测试 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/test/test_company_resources.py
git commit -m "test: 新增内网路由分类器单测"
```

---

## Task 5: 集成测试验证

**Files:**
- Test: 现有集成测试 + 手动验证

- [ ] **Step 1: 验证普通聊天仍可用**

```bash
# 启动服务后发送普通问题
curl -X POST http://127.0.0.1:8081/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3", "messages": [{"role": "user", "content": "你好"}]}'
```

- [ ] **Step 2: 验证强制 skill 仍工作**

```bash
# 发送 JIRA 请求
curl -X POST http://127.0.0.1:8081/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3", "messages": [{"role": "user", "content": "查下 ONLINE-12345"}]}'
```

- [ ] **Step 3: 验证 internal_priority 注入**

```bash
# 发送 Apollo 请求
curl -X POST http://127.0.0.1:8081/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3", "messages": [{"role": "user", "content": "Apollo 配置怎么查"}]}'
```

检查返回的消息中是否有内网优先 system prompt 的痕迹

- [ ] **Step 4: Commit**

```bash
git status
git add -A
git commit -m "test: 集成测试验证内网优先功能"
```

---

## 总结

实现顺序：
1. Task 1: 扩展 company_resources.py 路由分类器 (3-4 小时)
2. Task 2: 创建内网优先 prompt helper (1 小时)
3. Task 3: 改造 main.py 聊天链路 (2-3 小时)
4. Task 4: 编写路由分类单测 (1-2 小时)
5. Task 5: 集成测试验证 (1-2 小时)

预计总工作量：8-12 小时

实现原则：
- 每个 task 完成后单独 commit
- 先确保强制 skill 路由不受影响
- 再扩展 internal_priority 识别边界
- 最后做集成测试验证