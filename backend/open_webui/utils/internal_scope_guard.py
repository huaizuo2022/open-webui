"""Guardrails for the local internal-priority assistant."""

from __future__ import annotations

from dataclasses import dataclass

from open_webui.utils.company_resources import InternalRouteResult, RouteType, detect_company_resource_route


INTERNAL_PRIORITY_HINT_MESSAGE = (
    "当前助手采用内网优先策略：命中内网系统、内部数据、内部文档、日志、工单、配置、发布或链路排查时，优先使用内网知识和内网工具；"
    "如果问题不属于内网场景，则回退到普通回答。"
)


@dataclass(frozen=True)
class InternalScopeDecision:
    allowed: bool
    route: InternalRouteResult
    refusal_message: str = INTERNAL_PRIORITY_HINT_MESSAGE


def decide_internal_scope(user_message: str) -> InternalScopeDecision:
    """Prefer internal routing when possible, but do not block public questions."""
    route = detect_company_resource_route(user_message)
    return InternalScopeDecision(
        allowed=True,
        route=route,
    )


def enforce_internal_only_form_data(form_data: dict, metadata: dict | None = None) -> tuple[dict, dict]:
    """Disable external tools so the assistant stays on the local/internal path first."""
    metadata = metadata or {}

    features = form_data.get('features')
    if isinstance(features, dict):
        features['web_search'] = False

    form_data.pop('tools', None)
    form_data['tool_ids'] = []
    form_data.pop('terminal_id', None)

    metadata['tool_ids'] = []
    metadata['tool_servers'] = []
    metadata.setdefault('features', {})
    if isinstance(metadata['features'], dict):
        metadata['features']['web_search'] = False

    return form_data, metadata
