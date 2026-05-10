import pytest
from open_webui.utils.company_resources import detect_company_resource_route, RouteType


class TestDetectCompanyResourceRoute:

    def test_jira_forced_skill(self):
        result = detect_company_resource_route('查一下 ONLINE-12345 这个工单')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-jira'
        assert result.confidence == 'high'

    def test_jira_link_forced_skill(self):
        result = detect_company_resource_route('看看 https://jira.qima-inc.com/browse/ONLINE-98765')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-jira'

    def test_feishu_wiki_forced_skill(self):
        result = detect_company_resource_route('查下这个飞书文档 qima.feishu.cn/wiki/ABC123')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'feishu-wiki-skill'

    def test_tianwang_forced_skill(self):
        result = detect_company_resource_route('traceId abc-def-ghi-jkl 报错怎么查')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-log-query'

    def test_apollo_with_action_internal_priority(self):
        result = detect_company_resource_route('Apollo 配置怎么排查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_redis_with_action_internal_priority(self):
        result = detect_company_resource_route('Redis 连接超时怎么排查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_redis_with_company_marker_internal_priority(self):
        result = detect_company_resource_route('我们内网的 Redis 怎么连')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_xiaolv_keyword_internal_priority(self):
        result = detect_company_resource_route('Xiaolv 需求怎么查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_redis_principle_no_route(self):
        result = detect_company_resource_route('Redis 原理是什么')
        assert result.route_type == RouteType.NONE

    def test_mysql_basic_no_route(self):
        result = detect_company_resource_route('MySQL 索引怎么建')
        assert result.route_type == RouteType.NONE

    def test_dubbo_with_action_internal_priority(self):
        result = detect_company_resource_route('Dubbo 联调怎么做')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_traceid_pure_no_route(self):
        result = detect_company_resource_route('traceId 怎么查')
        assert result.route_type == RouteType.NONE

    def test_traceid_with_app_name_forced_skill(self):
        result = detect_company_resource_route('查下 pay-opcenter 这个应用的 abc-def-ghi-jkl 日志')
        assert result.route_type == RouteType.FORCED_SKILL
        assert result.skill_id == 'zan-log-query'

    def test_feishu_keyword_internal_priority(self):
        result = detect_company_resource_route('飞书文档怎么查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_feishu_english_internal_priority(self):
        result = detect_company_resource_route('feishu 文档怎么查')
        assert result.route_type == RouteType.INTERNAL_PRIORITY

    def test_as_dict_compatibility(self):
        result = detect_company_resource_route('查一下 ONLINE-12345')
        d = result.as_dict()
        assert d['skill_id'] == 'zan-jira'
        assert d['route_type'] == 'forced_skill'

    def test_bool_behavior(self):
        result_forced = detect_company_resource_route('查一下 ONLINE-12345')
        result_none = detect_company_resource_route('今天天气怎么样')

        assert bool(result_forced) == True
        assert bool(result_none) == False