from __future__ import annotations

from pathlib import Path
import sys
import json
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class DirectChatStreamTests(unittest.TestCase):
    def test_done_event_with_content_is_emitted_before_stream_stops(self):
        from open_webui.utils.chat import _format_direct_stream_event

        chunk, should_stop = _format_direct_stream_event(
            {
                'done': True,
                'content': '高德券通常不支持实物商品',
            }
        )

        self.assertTrue(should_stop)
        self.assertTrue(chunk.startswith('data: '))

        payload = json.loads(chunk.removeprefix('data: ').strip())
        self.assertEqual(
            payload,
            {
                'done': True,
                'content': '高德券通常不支持实物商品',
            },
        )

    def test_model_throttle_waits_between_same_model_requests(self):
        from open_webui.utils.chat import (
            _CHAT_MODEL_REQUEST_LOCKS,
            _CHAT_MODEL_NEXT_AVAILABLE_AT,
            _throttle_chat_model_request,
        )

        _CHAT_MODEL_REQUEST_LOCKS.clear()
        _CHAT_MODEL_NEXT_AVAILABLE_AT.clear()

        current_time = 100.0
        sleeps = []

        def now():
            return current_time

        async def sleep(seconds):
            nonlocal current_time
            sleeps.append(seconds)
            current_time += seconds

        async def run():
            await _throttle_chat_model_request('deepseek-v4-flash', now_fn=now, sleep_fn=sleep)
            await _throttle_chat_model_request('deepseek-v4-flash', now_fn=now, sleep_fn=sleep)

        with patch.dict('os.environ', {'CHAT_MODEL_MIN_INTERVAL_SECONDS': '{"deepseek-v4-flash": 20}'}, clear=False):
            asyncio.run(run())

        self.assertEqual(sleeps, [20.0])

    def test_model_throttle_ignores_unconfigured_models(self):
        from open_webui.utils.chat import (
            _CHAT_MODEL_REQUEST_LOCKS,
            _CHAT_MODEL_NEXT_AVAILABLE_AT,
            _throttle_chat_model_request,
        )

        _CHAT_MODEL_REQUEST_LOCKS.clear()
        _CHAT_MODEL_NEXT_AVAILABLE_AT.clear()

        sleeps = []

        async def sleep(seconds):
            sleeps.append(seconds)

        async def run():
            await _throttle_chat_model_request('DeepSeek-v4-pro', now_fn=lambda: 0.0, sleep_fn=sleep)
            await _throttle_chat_model_request('DeepSeek-v4-pro', now_fn=lambda: 0.0, sleep_fn=sleep)

        with patch.dict('os.environ', {'CHAT_MODEL_MIN_INTERVAL_SECONDS': '{}'}, clear=False):
            asyncio.run(run())

        self.assertEqual(sleeps, [])

    def test_openai_completion_retries_model_rate_limit_after_throttle(self):
        from open_webui.utils.chat import (
            _CHAT_MODEL_REQUEST_LOCKS,
            _CHAT_MODEL_NEXT_AVAILABLE_AT,
            _generate_openai_chat_completion_with_throttle,
        )

        _CHAT_MODEL_REQUEST_LOCKS.clear()
        _CHAT_MODEL_NEXT_AVAILABLE_AT.clear()

        current_time = 0.0
        sleeps = []

        def now():
            return current_time

        async def sleep(seconds):
            nonlocal current_time
            sleeps.append(seconds)
            current_time += seconds

        upstream = AsyncMock(
            side_effect=[
                Exception('litellm.RateLimitError: Too many requests'),
                {'choices': []},
            ]
        )

        async def run():
            with patch('open_webui.utils.chat.generate_openai_chat_completion', new=upstream):
                return await _generate_openai_chat_completion_with_throttle(
                    request=object(),
                    form_data={'model': 'deepseek-v4-flash'},
                    user=object(),
                    bypass_system_prompt=False,
                    now_fn=now,
                    sleep_fn=sleep,
                )

        with patch.dict(
            'os.environ',
            {
                'CHAT_MODEL_MIN_INTERVAL_SECONDS': '{"deepseek-v4-flash": 20}',
                'CHAT_MODEL_RATE_LIMIT_RETRY_ATTEMPTS': '1',
            },
            clear=False,
        ):
            result = asyncio.run(run())

        self.assertEqual(result, {'choices': []})
        self.assertEqual(upstream.await_count, 2)
        self.assertEqual(sleeps, [20.0])


if __name__ == '__main__':
    unittest.main()
