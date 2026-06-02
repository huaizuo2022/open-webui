from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from open_webui.tools.builtin import (
    _extract_feishu_fallback_queries,
    _run_feishu_search_with_fallbacks,
)
from open_webui.utils.internal_evidence import should_collect_company_help_center
from open_webui.utils.company_resources import detect_company_resource_route


class TestFeishuSearchFallback(unittest.TestCase):
    def test_extracts_compact_query_from_natural_question(self):
        queries = _extract_feishu_fallback_queries('公司 token 的燃烧计划是什么')

        self.assertIn('token 燃烧计划', queries)

    def test_retries_with_fallback_when_primary_has_no_results(self):
        responses = [
            {
                'command': 'primary',
                'cwd': '/tmp',
                'exit_code': 0,
                'stdout': '',
                'stderr': '',
                'data': {'ok': True, 'data': {'results': []}},
            },
            {
                'command': 'fallback',
                'cwd': '/tmp',
                'exit_code': 0,
                'stdout': '',
                'stderr': '',
                'data': {'ok': True, 'data': {'results': [{'title': 'Token 燃烧计划'}]}},
            },
        ]

        with patch('open_webui.tools.builtin._run_lark_cli_json', side_effect=responses):
            result, attempted_queries, error = _run_feishu_search_with_fallbacks(
                '公司 token 的燃烧计划是什么',
                Path.cwd(),
                30,
            )

        self.assertIsNone(error)
        self.assertEqual(attempted_queries[:2], ['公司 token 的燃烧计划是什么', 'token 燃烧计划'])
        self.assertEqual(result['command'], 'fallback')


class TestInternalEvidenceSourceSelection(unittest.TestCase):
    def test_generic_company_plan_question_skips_help_center(self):
        route = detect_company_resource_route('公司 token 的燃烧计划是什么')

        self.assertFalse(should_collect_company_help_center(route, '公司 token 的燃烧计划是什么'))


if __name__ == '__main__':
    unittest.main()
