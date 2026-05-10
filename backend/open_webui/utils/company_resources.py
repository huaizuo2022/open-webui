import json
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


STRONG_INTERNAL_SYSTEMS = {"jira", "飞书", "feishu", "天网", "kibana", "xiaolv", "效能平台", "数仓平台", "日志"}
WEAK_TECH_TERMS = {"apollo", "redis", "rds", "dubbo", "hbase", "es", "埋点", "traceid"}
INTERNAL_ACTIONS = {"排查", "发布", "上线", "配置核对", "查日志", "查工单", "查数据", "联调", "回滚", "血缘分析"}
COMPANY_MARKERS = {"内网", "公司内部", "qima", "youzan", "有赞", "qima-inc", "内部系统"}
GENERIC_TERMS = {"环境", "应用名", "配置项", "链路"}


COMPANY_WEB_HOST_PATTERNS = (
    r'https?://[^\s]*\.qima-inc\.com',
    r'https?://[^\s]*\.youzan\.com',
    r'https?://qima\.feishu\.cn',
)


def detect_company_resource_route(user_message: str) -> InternalRouteResult:
    if not user_message:
        return InternalRouteResult(route_type=RouteType.NONE, request=user_message or "")

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
        reason = "weak_term_with_" + ("action" if has_action else "company_marker")
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


def _try_parse_json(value):
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _truncate(text: str, limit: int = 220) -> str:
    text = (text or '').strip()
    return text if len(text) <= limit else f'{text[:limit]}...'


def format_company_route_result(skill_id: str, parsed_result: dict) -> str:
    if skill_id == 'zan-log-query':
        payload = _try_parse_json(parsed_result.get('stdout', '')) or parsed_result
        logs = payload.get('logs', []) if isinstance(payload, dict) else []
        app = payload.get('app') or parsed_result.get('app') or 'unknown'
        total = payload.get('total') or len(logs)
        trace_id = parsed_result.get('trace_id') or (logs[0].get('traceId') if logs else None)

        combined_text = '\n'.join(log.get('message', '') for log in logs[:10])
        order_no_match = re.search(r'E\d{17,}', combined_text)
        kdt_match = re.search(r'kdtId[=:\\"]+(\d+)', combined_text)
        amount_match = re.search(r'REAL_PAY_AMOUNT[=:\\"]+(\d+)', combined_text)
        status_match = re.search(r'orderStatus[=:\\"]+([A-Z_]+)', combined_text)

        lines = [f'已在天网查询到 `app={app}` 的日志，共 `{total}` 条。']
        if trace_id:
            lines.append(f'- traceId: `{trace_id}`')
        if order_no_match:
            lines.append(f'- 订单号: `{order_no_match.group(0)}`')
        if kdt_match:
            lines.append(f'- kdtId: `{kdt_match.group(1)}`')
        if amount_match:
            lines.append(f'- 支付金额: `{amount_match.group(1)}` 分')
        if status_match:
            lines.append(f'- 订单状态: `{status_match.group(1)}`')

        lines.append('')
        lines.append('关键信息：')
        for log_item in logs[:6]:
            lines.append(
                f"- `{log_item.get('time', '')}` `{log_item.get('class', '')}`: {_truncate(log_item.get('message', ''))}"
            )

        return '\n'.join(lines)

    if skill_id == 'feishu-wiki-skill':
        raw_result = parsed_result.get('raw_result', {}) if isinstance(parsed_result, dict) else {}
        raw_data = _try_parse_json(raw_result.get('stdout', '')) or raw_result.get('data') or {}
        content = (((raw_data.get('data') or {}).get('content')) if isinstance(raw_data, dict) else None) or ''
        title = ''
        node_result = parsed_result.get('node_result', {}) if isinstance(parsed_result, dict) else {}
        node_data = _try_parse_json(node_result.get('stdout', '')) or node_result.get('data') or {}
        if isinstance(node_data, dict):
            title = (((node_data.get('data') or {}).get('node')) or {}).get('title', '')

        lines = []
        if title:
            lines.append(f'飞书文档：`{title}`')
        if content:
            lines.append(_truncate(content, 4000))
        return '\n\n'.join(lines) if lines else '已执行飞书查询，但未解析到可展示内容。'

    if skill_id == 'zan-jira':
        view_result = parsed_result.get('view_result', {}) if isinstance(parsed_result, dict) else {}
        stdout = (view_result.get('stdout') or '').strip()
        jira_id = parsed_result.get('jira_id', '')
        if stdout:
            lines = [f'已查询 JIRA：`{jira_id}`', '', _truncate(stdout, 4000)]
            return '\n'.join(lines)
        return f'已执行 JIRA 查询：`{jira_id}`，但没有解析到可展示内容。'

    if parsed_result.get('stdout'):
        return _truncate(parsed_result.get('stdout', ''), 4000)
    return _truncate(json.dumps(parsed_result, ensure_ascii=False), 4000)
