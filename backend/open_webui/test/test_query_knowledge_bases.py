from __future__ import annotations

from pathlib import Path
import sys
import asyncio
import json
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class QueryKnowledgeBasesTests(unittest.TestCase):
    def test_query_knowledge_bases_returns_error_when_embedding_function_missing(self):
        from open_webui.tools.builtin import query_knowledge_bases

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(EMBEDDING_FUNCTION=None)))
        user = {'id': 'user-1'}

        async def run():
            return await query_knowledge_bases(
                query='高德券 实物商品 支持',
                count=5,
                __request__=request,
                __user__=user,
            )

        result = asyncio.run(run())
        payload = json.loads(result)

        self.assertEqual(
            payload,
            {
                'error': 'Embedding function not configured'
            },
        )


if __name__ == '__main__':
    unittest.main()
