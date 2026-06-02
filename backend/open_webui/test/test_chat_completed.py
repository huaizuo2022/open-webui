from __future__ import annotations

from pathlib import Path
import sys
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class ChatCompletedTests(unittest.TestCase):
    def test_chat_completed_ignores_outlet_failures_for_legacy_callback(self):
        from open_webui.utils.chat import chat_completed

        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(MODELS={'DeepSeek-v4-pro': {'id': 'DeepSeek-v4-pro'}})),
            state=SimpleNamespace(),
        )
        user = SimpleNamespace(id='user-1', email='guest@localhost', name='Guest', role='admin')
        form_data = {
            'id': 'message-1',
            'model': 'DeepSeek-v4-pro',
            'chat_id': 'chat-1',
            'session_id': 'session-1',
            'messages': [{'id': 'message-1', 'role': 'assistant', 'content': '你好'}],
        }

        async def run():
            with (
                patch(
                    'open_webui.utils.chat.process_pipeline_outlet_filter',
                    new=AsyncMock(side_effect=Exception("'NoneType' object has no attribute 'kind'")),
                ),
                patch(
                    'open_webui.utils.chat.get_sorted_filter_ids',
                    new=AsyncMock(return_value=[]),
                ),
                patch(
                    'open_webui.utils.chat.Functions.get_functions_by_ids',
                    new=AsyncMock(return_value=[]),
                ),
                patch(
                    'open_webui.utils.chat.process_filter_functions',
                    new=AsyncMock(return_value=(form_data, {})),
                ),
                patch(
                    'open_webui.utils.chat.get_event_emitter',
                    new=AsyncMock(return_value=None),
                ),
                patch(
                    'open_webui.utils.chat.get_event_call',
                    new=AsyncMock(return_value=None),
                ),
            ):
                return await chat_completed(request, dict(form_data), user)

        result = asyncio.run(run())

        self.assertEqual(result['id'], 'message-1')
        self.assertEqual(result['messages'][0]['content'], '你好')


if __name__ == '__main__':
    unittest.main()
