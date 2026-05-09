import json
import re
from typing import Optional


COMPANY_WEB_HOST_PATTERNS = (
    r'https?://[^\s]*\.qima-inc\.com',
    r'https?://[^\s]*\.youzan\.com',
    r'https?://qima\.feishu\.cn',
)


def detect_company_resource_route(user_message: str) -> Optional[dict]:
    if not user_message:
        return None

    text = user_message.lower()

    if re.search(r'https?://[^\s]*jira\.qima-inc\.com/', text) or re.search(r'\b[A-Z][A-Z0-9]+-\d+\b', user_message):
        return {'skill_id': 'zan-jira', 'request': user_message, 'resource_type': 'jira'}

    if 'qima.feishu.cn/wiki/' in text:
        return {'skill_id': 'feishu-wiki-skill', 'request': user_message, 'resource_type': 'feishu_wiki'}

    trace_like = re.search(r'\b[a-z0-9]+(?:-[a-z0-9]+){3,}\b', text)
    if trace_like and any(keyword in text for keyword in ('天网', '日志', 'traceid', 'trace id', '报错')):
        return {'skill_id': 'zan-log-query', 'request': user_message, 'resource_type': 'tianwang'}

    if trace_like and re.search(r'\b[a-z][a-z0-9]+(?:-[a-z0-9]+)+\b', text):
        return {'skill_id': 'zan-log-query', 'request': user_message, 'resource_type': 'tianwang'}

    if any(re.search(pattern, text) for pattern in COMPANY_WEB_HOST_PATTERNS):
        return {'resource_type': 'company_web', 'request': user_message}

    return None


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
