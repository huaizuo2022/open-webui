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
