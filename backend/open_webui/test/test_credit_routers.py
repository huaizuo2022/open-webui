from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class CreditRouterSurfaceTests(unittest.TestCase):
    def test_session_user_response_accepts_credit(self):
        from open_webui.models.credits import CreditSession
        from open_webui.routers.auths import SessionUserResponse

        response = SessionUserResponse(
            token='t',
            token_type='Bearer',
            id='u1',
            email='u1@example.com',
            name='User',
            role='user',
            profile_image_url='/img.png',
            credit=CreditSession(balance=10, free_chat_used=1, free_chat_limit=5),
        )

        self.assertEqual(response.credit.balance, 10)

    def test_credit_router_module_loads(self):
        from open_webui.routers import credits, admin_credits

        self.assertIsNotNone(credits.router)
        self.assertIsNotNone(admin_credits.router)

    def test_create_session_response_includes_credit_payload(self):
        from open_webui.routers.auths import create_session_response

        class DummyRequest:
            class DummyApp:
                class DummyState:
                    class DummyConfig:
                        JWT_EXPIRES_IN = '5m'
                        USER_PERMISSIONS = {}

                    config = DummyConfig()

                state = DummyState()

            app = DummyApp()

        class DummyUser:
            id = 'u1'
            email = 'u1@example.com'
            name = 'User'
            role = 'user'

        async def run():
            with (
                patch('open_webui.routers.auths.get_permissions', new=AsyncMock(return_value={})),
                patch(
                    'open_webui.routers.auths.get_credit_session_for_request',
                    new=AsyncMock(
                        return_value=type(
                            'Credit',
                            (),
                            {'model_dump': lambda self: {'balance': 9, 'free_chat_used': 2, 'free_chat_limit': 5}},
                        )()
                    ),
                ),
            ):
                return await create_session_response(DummyRequest(), DummyUser(), db=None)

        import asyncio

        payload = asyncio.run(run())

        self.assertEqual(payload['credit']['balance'], 9)
        self.assertEqual(payload['credit']['free_chat_used'], 2)
        self.assertEqual(payload['credit']['free_chat_limit'], 5)

    def test_admin_credit_routes_are_registered(self):
        from open_webui.routers.admin_credits import router

        registered = {(route.path, tuple(sorted(route.methods))) for route in router.routes}

        self.assertIn(('/credits/redeem-codes/batches', ('POST',)), registered)
        self.assertIn(('/credits/redeem-codes/batches', ('GET',)), registered)
        self.assertIn(('/credits/redeem-codes', ('GET',)), registered)
        self.assertIn(('/credits/redeem-codes/batches/{batch_id}/export', ('GET',)), registered)


if __name__ == '__main__':
    unittest.main()
