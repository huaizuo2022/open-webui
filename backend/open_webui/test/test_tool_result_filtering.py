from __future__ import annotations

from pathlib import Path
import sys
import json
import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class ToolResultFilteringTests(unittest.TestCase):
    def test_knowledge_base_error_payload_is_detected_as_failure(self):
        tool_result = json.dumps({'error': 'Embedding function not configured'}, ensure_ascii=False)

        parsed = json.loads(tool_result)

        self.assertIsInstance(parsed, dict)
        self.assertIn('error', parsed)

    def test_nested_base64_images_are_extracted_into_tool_result_files(self):
        from open_webui.utils.middleware import process_tool_result

        tool_result = {
            'search_result': {
                'data': [
                    {
                        'title': '企业微信修改手机号',
                        'images': [
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': 'image/png',
                                    'data': 'ZmFrZS1pbWFnZS0x',
                                },
                            },
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': 'image/png',
                                    'data': 'ZmFrZS1pbWFnZS0y',
                                },
                            },
                        ],
                    }
                ]
            }
        }

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        metadata = {'chat_id': 'chat-1', 'message_id': 'message-1', 'session_id': 'session-1'}
        user = SimpleNamespace(id='user-1')

        async def run():
            with patch(
                'open_webui.utils.middleware.get_file_url_from_base64',
                new=AsyncMock(side_effect=['/api/v1/files/img-1', '/api/v1/files/img-2']),
            ):
                return await process_tool_result(
                    request=request,
                    tool_function_name='execute_internal_skill_request',
                    tool_result=tool_result,
                    tool_type='builtin',
                    metadata=metadata,
                    user=user,
                )

        processed_result, tool_result_files, tool_result_embeds = asyncio.run(run())

        self.assertEqual(tool_result_embeds, [])
        self.assertEqual(
            tool_result_files,
            [
                {'type': 'image', 'url': '/api/v1/files/img-1'},
                {'type': 'image', 'url': '/api/v1/files/img-2'},
            ],
        )

        parsed = json.loads(processed_result)
        images = parsed['search_result']['data'][0]['images']
        self.assertEqual(images[0]['source']['type'], 'file')
        self.assertEqual(images[0]['source']['url'], '/api/v1/files/img-1')
        self.assertEqual(images[1]['source']['type'], 'file')
        self.assertEqual(images[1]['source']['url'], '/api/v1/files/img-2')


if __name__ == '__main__':
    unittest.main()
