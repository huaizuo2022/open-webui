from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from open_webui.utils.company_resources import detect_company_resource_route, RouteType
from open_webui.utils.internal_evidence import choose_internal_evidence_sources


class TestDetectCompanyResourceRoute(unittest.TestCase):
    def test_jira_forced_skill(self):
        result = detect_company_resource_route('查一下 ONLINE-12345 这个工单')
        self.assertEqual(result.route_type, RouteType.FORCED_SKILL)
        self.assertEqual(result.skill_id, 'zan-jira')
        self.assertEqual(result.confidence, 'high')

    def test_jira_link_forced_skill(self):
        result = detect_company_resource_route('看看 https://jira.qima-inc.com/browse/ONLINE-98765')
        self.assertEqual(result.route_type, RouteType.FORCED_SKILL)
        self.assertEqual(result.skill_id, 'zan-jira')
        self.assertEqual(result.confidence, 'high')

    def test_feishu_wiki_forced_skill(self):
        result = detect_company_resource_route('查下这个飞书文档 qima.feishu.cn/wiki/ABC123')
        self.assertEqual(result.route_type, RouteType.FORCED_SKILL)
        self.assertEqual(result.skill_id, 'feishu-doc-read')

    def test_tianwang_forced_skill(self):
        result = detect_company_resource_route('traceId abc-def-ghi-jkl 报错怎么查')
        self.assertEqual(result.route_type, RouteType.FORCED_SKILL)
        self.assertEqual(result.skill_id, 'zan-log-query')

    def test_apollo_with_action_internal_priority(self):
        result = detect_company_resource_route('Apollo 配置怎么排查')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_redis_with_action_internal_priority(self):
        result = detect_company_resource_route('Redis 连接超时怎么排查')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_redis_with_company_marker_internal_priority(self):
        result = detect_company_resource_route('我们内网的 Redis 怎么连')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_xiaolv_keyword_internal_priority(self):
        result = detect_company_resource_route('Xiaolv 需求怎么查')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_redis_principle_no_route(self):
        result = detect_company_resource_route('Redis 原理是什么')
        self.assertEqual(result.route_type, RouteType.NONE)

    def test_mysql_basic_no_route(self):
        result = detect_company_resource_route('MySQL 索引怎么建')
        self.assertEqual(result.route_type, RouteType.NONE)

    def test_mysql_query_internal_priority(self):
        result = detect_company_resource_route('查下 MySQL 订单表数据')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_httpgateway_internal_priority(self):
        result = detect_company_resource_route('查 HTTPGateway 访问日志')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_dubbo_with_action_internal_priority(self):
        result = detect_company_resource_route('Dubbo 联调怎么做')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_traceid_pure_no_route(self):
        result = detect_company_resource_route('traceId 怎么查')
        self.assertEqual(result.route_type, RouteType.NONE)

    def test_empty_string_returns_none(self):
        result = detect_company_resource_route('')
        self.assertEqual(result.route_type, RouteType.NONE)

    def test_traceid_with_app_name_forced_skill(self):
        result = detect_company_resource_route('查下 pay-opcenter 这个应用的 abc-def-ghi-jkl 日志')
        self.assertEqual(result.route_type, RouteType.FORCED_SKILL)
        self.assertEqual(result.skill_id, 'zan-log-query')
        self.assertEqual(result.confidence, 'high')

    def test_feishu_keyword_internal_priority(self):
        result = detect_company_resource_route('飞书文档怎么查')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_feishu_english_internal_priority(self):
        result = detect_company_resource_route('feishu 文档怎么查')
        self.assertEqual(result.route_type, RouteType.INTERNAL_PRIORITY)

    def test_company_help_center_business_question_forced_skill(self):
        result = detect_company_resource_route('限时折扣和满减送可以叠加吗')
        self.assertEqual(result.route_type, RouteType.FORCED_SKILL)
        self.assertEqual(result.skill_id, 'company-help-center')

    def test_company_help_center_product_question_forced_skill(self):
        result = detect_company_resource_route('高德券支持实物商品吗?')
        self.assertEqual(result.route_type, RouteType.FORCED_SKILL)
        self.assertEqual(result.skill_id, 'company-help-center')

    def test_as_dict_compatibility(self):
        result = detect_company_resource_route('查一下 ONLINE-12345')
        d = result.as_dict()
        self.assertEqual(d['skill_id'], 'zan-jira')
        self.assertEqual(d['route_type'], 'forced_skill')

    def test_bool_behavior(self):
        result_forced = detect_company_resource_route('查一下 ONLINE-12345')
        result_none = detect_company_resource_route('今天天气怎么样')

        self.assertTrue(bool(result_forced))
        self.assertFalse(bool(result_none))


class TestInternalScopeGuard(unittest.TestCase):
    def test_allows_public_knowledge_question_with_no_internal_route(self):
        from open_webui.utils.internal_scope_guard import decide_internal_scope

        result = decide_internal_scope('Redis 原理是什么')

        self.assertTrue(result.allowed)
        self.assertEqual(result.route.route_type, RouteType.NONE)
        self.assertIn('内网优先策略', result.refusal_message)

    def test_allows_internal_jira_question(self):
        from open_webui.utils.internal_scope_guard import decide_internal_scope

        result = decide_internal_scope('查一下 ONLINE-12345 这个工单')

        self.assertTrue(result.allowed)
        self.assertEqual(result.route.skill_id, 'zan-jira')

    def test_enforce_internal_only_form_data_disables_external_features(self):
        from open_webui.utils.internal_scope_guard import enforce_internal_only_form_data

        form_data, metadata = enforce_internal_only_form_data(
            {
                'features': {'web_search': True, 'memory': True},
                'tools': [{'type': 'function'}],
                'tool_ids': ['external-tool'],
                'terminal_id': 'terminal-1',
            },
            {'features': {'web_search': True}, 'tool_servers': [{'url': 'https://example.com'}]},
        )

        self.assertFalse(form_data['features']['web_search'])
        self.assertEqual(form_data['tool_ids'], [])
        self.assertNotIn('tools', form_data)
        self.assertNotIn('terminal_id', form_data)
        self.assertEqual(metadata['tool_ids'], [])
        self.assertEqual(metadata['tool_servers'], [])
        self.assertFalse(metadata['features']['web_search'])


class TestInternalEvidenceSelection(unittest.TestCase):
    def test_generic_question_collects_feishu_only(self):
        route = detect_company_resource_route('今天天气怎么样')
        sources = choose_internal_evidence_sources(route, '今天天气怎么样')
        self.assertEqual(sources, ['feishu-doc-search'])

    def test_company_help_center_question_collects_help_center_and_feishu(self):
        route = detect_company_resource_route('有赞订单类型是什么')
        sources = choose_internal_evidence_sources(route, '有赞订单类型是什么')
        self.assertEqual(sources, ['company-help-center', 'feishu-doc-search'])

    def test_jira_forced_route_collects_feishu_only(self):
        route = detect_company_resource_route('查一下 ONLINE-12345 这个工单')
        sources = choose_internal_evidence_sources(route, '查一下 ONLINE-12345 这个工单')
        self.assertEqual(sources, ['feishu-doc-search'])

    def test_trace_route_collects_feishu_only(self):
        route = detect_company_resource_route('traceId abc-def-ghi-jkl 报错怎么查')
        sources = choose_internal_evidence_sources(route, 'traceId abc-def-ghi-jkl 报错怎么查')
        self.assertEqual(sources, ['feishu-doc-search'])


if __name__ == '__main__':
    unittest.main()
