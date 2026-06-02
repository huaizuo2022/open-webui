import json
import re
from typing import Awaitable, Callable, Optional

from open_webui.utils.company_resources import (
    COMPANY_MARKERS,
    HELP_CENTER_BUSINESS_TERMS,
    HELP_CENTER_PRODUCT_TERMS,
    InternalRouteResult,
    RouteType,
    format_company_route_result,
)

INTERNAL_EVIDENCE_MARKER = '以下是已检索到的内部资料证据'
INTERNAL_EVIDENCE_SOURCE_LABELS = {
    'company-help-center': 'company-help-center',
    'feishu-doc-search': 'lark-cli docs +search',
}
INTERNAL_WARNING_MARKER = '飞书资料补充状态'

QUESTION_HINT_PATTERN = re.compile(
    r'(是什么|什么类型|属于什么|哪种|怎么样|是怎样的|是什么样的|怎么做|如何|规则|区别|优先级|是否支持|可以.*吗|能.*吗)',
    re.IGNORECASE,
)
FEISHU_SEARCH_HINT_TERMS = {
    '飞书',
    'feishu',
    '文档',
    '知识库',
    'wiki',
    'docx',
    '多维表格',
}
GENERIC_INTERNAL_CONSULTING_TERMS = {
    '公司',
    '内部',
}
GENERIC_PLAN_TERMS = {
    '计划',
    '方案',
    '报销',
    '预算',
    '订阅',
    'token',
    '燃烧',
}


def _contains_help_center_terms(user_message: str) -> bool:
    text = (user_message or '').lower()
    return any(term in text for term in HELP_CENTER_PRODUCT_TERMS) or any(
        term in text for term in HELP_CENTER_BUSINESS_TERMS
    )


def _contains_generic_internal_consulting_terms(user_message: str) -> bool:
    text = (user_message or '').lower()
    has_internal_marker = any(term in text for term in COMPANY_MARKERS) or any(
        term in text for term in GENERIC_INTERNAL_CONSULTING_TERMS
    )
    return has_internal_marker and bool(QUESTION_HINT_PATTERN.search(text))


def should_collect_company_help_center(route: Optional[InternalRouteResult], user_message: str) -> bool:
    if route and route.skill_id == 'company-help-center':
        return True

    text = user_message or ''
    lowered = text.lower()
    if _contains_generic_internal_consulting_terms(text) and not any(term in lowered for term in GENERIC_PLAN_TERMS):
        return True

    return _contains_help_center_terms(text)


def should_collect_feishu_docs(route: Optional[InternalRouteResult], user_message: str) -> bool:
    if route and route.skill_id == 'company-help-center':
        return True

    text = (user_message or '').lower()
    if _contains_generic_internal_consulting_terms(text):
        return True

    if any(term in text for term in FEISHU_SEARCH_HINT_TERMS):
        return True

    if route and route.route_type == RouteType.INTERNAL_PRIORITY and _contains_help_center_terms(text):
        return True

    return False


def choose_internal_evidence_sources(
    route: Optional[InternalRouteResult], user_message: str
) -> list[str]:
    sources: list[str] = []

    if should_collect_company_help_center(route, user_message):
        sources.append('company-help-center')

    # Feishu docs search remains a default supplement for every request.
    sources.append('feishu-doc-search')

    deduped: list[str] = []
    for source in sources:
        if source not in deduped:
            deduped.append(source)
    return deduped


def has_internal_evidence_injected(messages: list) -> bool:
    for msg in messages:
        if isinstance(msg, dict) and msg.get('role') == 'system':
            if INTERNAL_EVIDENCE_MARKER in (msg.get('content') or ''):
                return True
    return False


def build_internal_evidence_prompt(evidence_items: list[dict]) -> str:
    lines = [
        INTERNAL_EVIDENCE_MARKER,
        '请优先基于这些内部来源做综合回答；不要逐字照抄原始结果，结论里要标明来源一致性与不确定点。',
        '',
    ]

    for index, item in enumerate(evidence_items, start=1):
        source_label = item.get('source_label') or item.get('source') or f'source-{index}'
        lines.append(f'[{index}] 来源：{source_label}')
        lines.append(item.get('content', '').strip())
        lines.append('')

    return '\n'.join(lines).strip()


def build_internal_evidence_warning_text(warnings: list[str]) -> str:
    warnings = [warning.strip() for warning in warnings if warning and warning.strip()]
    if not warnings:
        return ''

    lines = [f'> **【{INTERNAL_WARNING_MARKER}】**']
    for warning in warnings:
        lines.append(f'> - {warning}')
    return '\n'.join(lines)


def apply_internal_evidence_to_form_data(form_data: dict, evidence_items: list[dict], metadata: dict = None) -> tuple[dict, dict]:
    if not evidence_items:
        return form_data, metadata or {}

    messages = form_data.get('messages', [])
    metadata = metadata or {}

    if has_internal_evidence_injected(messages):
        return form_data, metadata

    evidence_prompt = build_internal_evidence_prompt(evidence_items)
    form_data['messages'] = [
        {'role': 'system', 'content': evidence_prompt},
        *messages,
    ]
    metadata['internal_evidence'] = evidence_items
    metadata['internal_evidence_prompt'] = evidence_prompt
    return form_data, metadata


def _parse_tool_result(value: str):
    try:
        return json.loads(value)
    except Exception:
        return None


def _is_useful_evidence_content(content: str) -> bool:
    content = (content or '').strip()
    if not content:
        return False
    if '未找到相关内容' in content:
        return False
    if '未解析到可展示内容' in content:
        return False
    return True


def _build_warning_for_failed_source(source: str, parsed_result: dict) -> Optional[str]:
    error = str(parsed_result.get('error') or '').strip()
    if not error:
        return None

    if source == 'feishu-doc-search' and 'need_user_authorization' in error:
        return (
            '已尝试补充飞书检索，但当前 `lark-cli` 尚未完成用户授权；'
            '请先在服务宿主机执行 `lark-cli auth login`，完成授权后重新提问。'
        )

    return None


async def collect_internal_evidence(
    user_message: str,
    route: Optional[InternalRouteResult],
    executor: Callable[[str, str], Awaitable[str]],
) -> tuple[list[dict], list[str]]:
    evidence_items: list[dict] = []
    warnings: list[str] = []

    for source in choose_internal_evidence_sources(route, user_message):
        tool_result = await executor(source, user_message)
        parsed_result = _parse_tool_result(tool_result)
        if not isinstance(parsed_result, dict):
            continue
        if parsed_result.get('error'):
            if warning := _build_warning_for_failed_source(source, parsed_result):
                warnings.append(warning)
            continue
        if parsed_result.get('exit_code', 0) not in (0, None):
            continue

        formatted = format_company_route_result(source, parsed_result)
        if not _is_useful_evidence_content(formatted):
            continue

        evidence_items.append(
            {
                'source': source,
                'source_label': INTERNAL_EVIDENCE_SOURCE_LABELS.get(source, source),
                'content': formatted,
            }
        )

    deduped_warnings: list[str] = []
    for warning in warnings:
        if warning not in deduped_warnings:
            deduped_warnings.append(warning)

    return evidence_items, deduped_warnings
