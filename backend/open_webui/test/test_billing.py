from __future__ import annotations

from pathlib import Path
import sys
import asyncio
import unittest
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


class FakeUser:
    def __init__(self, email: str, user_id: str):
        self.email = email
        self.id = user_id


class BillingTests(unittest.TestCase):
    def test_guest_without_device_id_is_rejected(self):
        from open_webui.utils.device_id import resolve_billing_subject

        guest_user = FakeUser('guest@localhost', 'guest-id')

        with self.assertRaises(HTTPException):
            resolve_billing_subject(FakeRequest(headers={}), guest_user)

    def test_guest_with_device_id_uses_device_subject(self):
        from open_webui.utils.device_id import resolve_billing_subject

        guest_user = FakeUser('guest@localhost', 'guest-id')
        request = FakeRequest(headers={'X-OWUI-Device-Id': str(uuid4())})

        subject_type, subject_id, user_id = resolve_billing_subject(request, guest_user)

        self.assertEqual(subject_type, 'device')
        self.assertIsNone(user_id)
        self.assertTrue(subject_id)

    def test_logged_in_user_uses_user_subject(self):
        from open_webui.utils.device_id import resolve_billing_subject

        user = FakeUser('test@example.com', 'u-1')
        subject_type, subject_id, user_id = resolve_billing_subject(FakeRequest(headers={}), user)

        self.assertEqual(subject_type, 'user')
        self.assertEqual(subject_id, 'u-1')
        self.assertEqual(user_id, 'u-1')

    def test_missing_model_credit_cost_error_uses_contract_detail(self):
        from open_webui.utils.billing import MissingModelCreditCostError

        error = MissingModelCreditCostError()

        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.detail, 'MODEL_CREDIT_COST_MISSING')

    def test_insufficient_credit_error_uses_contract_detail(self):
        from open_webui.utils.billing import InsufficientCreditError

        error = InsufficientCreditError()

        self.assertEqual(error.status_code, 402)
        self.assertEqual(error.detail, 'INSUFFICIENT_CREDIT')

    def test_stream_wrapper_confirms_on_success(self):
        from open_webui.utils.billing import BillingReservation, wrap_streaming_response_for_billing

        async def stream():
            yield b'a'
            yield b'b'

        async def run():
            reservation = BillingReservation(
                reservation_id='r1',
                kind='credit',
                subject_type='user',
                subject_id='u1',
                user_id='u1',
                amount=3,
                model_id='gpt-4o-mini',
            )
            with (
                patch('open_webui.utils.billing.confirm_chat_allowance', new=AsyncMock()) as confirm_mock,
                patch('open_webui.utils.billing.rollback_chat_allowance', new=AsyncMock()) as rollback_mock,
            ):
                chunks = []
                async for chunk in wrap_streaming_response_for_billing(stream(), reservation, chat_id='chat-1'):
                    chunks.append(chunk)

                return chunks, confirm_mock.await_count, rollback_mock.await_count

        chunks, confirm_count, rollback_count = asyncio.run(run())

        self.assertEqual(chunks, [b'a', b'b'])
        self.assertEqual(confirm_count, 1)
        self.assertEqual(rollback_count, 0)

    def test_stream_wrapper_rolls_back_on_failure(self):
        from open_webui.utils.billing import BillingReservation, wrap_streaming_response_for_billing

        async def stream():
            yield b'a'
            raise RuntimeError('boom')

        async def run():
            reservation = BillingReservation(
                reservation_id='r2',
                kind='credit',
                subject_type='user',
                subject_id='u1',
                user_id='u1',
                amount=3,
                model_id='gpt-4o-mini',
            )
            with (
                patch('open_webui.utils.billing.confirm_chat_allowance', new=AsyncMock()) as confirm_mock,
                patch('open_webui.utils.billing.rollback_chat_allowance', new=AsyncMock()) as rollback_mock,
            ):
                with self.assertRaises(RuntimeError):
                    async for _ in wrap_streaming_response_for_billing(stream(), reservation, chat_id='chat-1'):
                        pass

                return confirm_mock.await_count, rollback_mock.await_count

        confirm_count, rollback_count = asyncio.run(run())

        self.assertEqual(confirm_count, 0)
        self.assertEqual(rollback_count, 1)

    def test_reserve_from_request_uses_free_quota_before_price_check(self):
        from open_webui.utils.billing import BillingReservation, reserve_chat_allowance_from_request

        class Meta:
            def model_dump(self):
                return {}

        class ModelInfo:
            meta = Meta()

        async def run():
            request = FakeRequest(headers={'X-OWUI-Device-Id': str(uuid4())})
            user = FakeUser('guest@localhost', 'guest-id')
            with (
                patch('open_webui.utils.billing.Credits.get_or_create_quota', new=AsyncMock(return_value=type('Quota', (), {'free_chat_used': 0, 'free_chat_limit': 5})())),
                patch(
                    'open_webui.utils.billing.reserve_chat_allowance',
                    new=AsyncMock(
                        return_value=BillingReservation(
                            reservation_id='r3',
                            kind='free_quota',
                            subject_type='device',
                            subject_id='device-1',
                            user_id=None,
                            amount=0,
                            model_id='gpt-4o-mini',
                        )
                    ),
                ) as reserve_mock,
            ):
                reservation = await reserve_chat_allowance_from_request(
                    request,
                    user,
                    {'model': 'gpt-4o-mini'},
                    ModelInfo(),
                )
                return reservation, reserve_mock.await_args.args

        reservation, reserve_args = asyncio.run(run())
        self.assertEqual(reservation.kind, 'free_quota')
        self.assertEqual(reserve_args[4], 0)

    def test_reserve_from_request_requires_price_after_free_quota_exhausted(self):
        from open_webui.utils.billing import MissingModelCreditCostError, reserve_chat_allowance_from_request

        class Meta:
            def model_dump(self):
                return {}

        class ModelInfo:
            meta = Meta()

        async def run():
            request = FakeRequest(headers={'X-OWUI-Device-Id': str(uuid4())})
            user = FakeUser('guest@localhost', 'guest-id')
            with patch(
                'open_webui.utils.billing.Credits.get_or_create_quota',
                new=AsyncMock(return_value=type('Quota', (), {'free_chat_used': 5, 'free_chat_limit': 5})()),
            ):
                with self.assertRaises(MissingModelCreditCostError):
                    await reserve_chat_allowance_from_request(
                        request,
                        user,
                        {'model': 'gpt-4o-mini'},
                        ModelInfo(),
                    )

        asyncio.run(run())

    def test_reserve_chat_allowance_blocks_when_balance_is_insufficient(self):
        from open_webui.utils.billing import InsufficientCreditError, reserve_chat_allowance

        async def run():
            with (
                patch('open_webui.utils.billing.Credits.consume_free_quota', new=AsyncMock(return_value=None)),
                patch(
                    'open_webui.utils.billing.Credits.get_or_create_account',
                    new=AsyncMock(return_value=type('Account', (), {'balance': 1})()),
                ),
            ):
                with self.assertRaises(InsufficientCreditError):
                    await reserve_chat_allowance(
                        subject_type='user',
                        subject_id='u-1',
                        user_id='u-1',
                        model_id='gpt-4o',
                        credit_cost=5,
                    )

        asyncio.run(run())

    def test_reserve_from_request_uses_model_credit_cost_for_logged_in_user_after_free_quota(self):
        from open_webui.utils.billing import BillingReservation, reserve_chat_allowance_from_request

        class Meta:
            def model_dump(self):
                return {'credit_cost': 6}

        class ModelInfo:
            meta = Meta()

        async def run():
            request = FakeRequest(headers={})
            user = FakeUser('test@example.com', 'u-1')
            with (
                patch(
                    'open_webui.utils.billing.Credits.get_or_create_quota',
                    new=AsyncMock(return_value=type('Quota', (), {'free_chat_used': 5, 'free_chat_limit': 5})()),
                ),
                patch(
                    'open_webui.utils.billing.reserve_chat_allowance',
                    new=AsyncMock(
                        return_value=BillingReservation(
                            reservation_id='r4',
                            kind='credit',
                            subject_type='user',
                            subject_id='u-1',
                            user_id='u-1',
                            amount=6,
                            model_id='gpt-4o',
                        )
                    ),
                ) as reserve_mock,
            ):
                reservation = await reserve_chat_allowance_from_request(
                    request,
                    user,
                    {'model': 'gpt-4o'},
                    ModelInfo(),
                )
                return reservation, reserve_mock.await_args.args

        reservation, reserve_args = asyncio.run(run())
        self.assertEqual(reservation.kind, 'credit')
        self.assertEqual(reserve_args[4], 6)

    def test_confirm_chat_allowance_accepts_missing_reservation(self):
        from open_webui.utils.billing import confirm_chat_allowance

        asyncio.run(confirm_chat_allowance(None, chat_id='chat-1'))

    def test_rollback_chat_allowance_accepts_missing_reservation(self):
        from open_webui.utils.billing import rollback_chat_allowance

        asyncio.run(rollback_chat_allowance(None, reason='chat_failed'))

    def test_stream_wrapper_accepts_missing_reservation(self):
        from open_webui.utils.billing import wrap_streaming_response_for_billing

        async def stream():
            yield b'a'
            yield b'b'

        async def run():
            chunks = []
            async for chunk in wrap_streaming_response_for_billing(stream(), None, chat_id='chat-1'):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(run())
        self.assertEqual(chunks, [b'a', b'b'])


if __name__ == '__main__':
    unittest.main()
