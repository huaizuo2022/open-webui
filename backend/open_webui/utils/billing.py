from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import AsyncIterator, Literal

from fastapi import HTTPException, Request

from open_webui.models.credits import CreditSession, CreditSummary, CreditTransactionCreateForm, Credits
from open_webui.utils.device_id import resolve_billing_subject


class InsufficientCreditError(HTTPException):
    def __init__(self):
        super().__init__(status_code=402, detail='INSUFFICIENT_CREDIT')


class MissingModelCreditCostError(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail='MODEL_CREDIT_COST_MISSING')


@dataclass
class BillingReservation:
    reservation_id: str
    kind: Literal['free_quota', 'credit']
    subject_type: str
    subject_id: str
    user_id: str | None
    amount: int
    model_id: str


async def reserve_chat_allowance(
    subject_type: str,
    subject_id: str,
    user_id: str | None,
    model_id: str,
    credit_cost: int,
) -> BillingReservation:
    free_quota = await Credits.consume_free_quota(subject_type, subject_id)
    if free_quota is not None:
        return BillingReservation(
            reservation_id=f'{subject_type}:{subject_id}:{model_id}:free',
            kind='free_quota',
            subject_type=subject_type,
            subject_id=subject_id,
            user_id=user_id,
            amount=0,
            model_id=model_id,
        )

    if not user_id:
        raise InsufficientCreditError()

    account = await Credits.get_or_create_account(user_id)
    if account.balance < credit_cost:
        raise InsufficientCreditError()

    updated = await Credits.change_balance(
        user_id,
        amount_delta=-credit_cost,
        consumed_delta=credit_cost,
    )
    await Credits.create_transaction(
        CreditTransactionCreateForm(
            user_id=user_id,
            type='consume',
            amount=-credit_cost,
            balance_after=updated.balance,
            model_id=model_id,
            remark='reserved for chat completion',
        )
    )
    return BillingReservation(
        reservation_id=f'{subject_type}:{subject_id}:{model_id}:credit',
        kind='credit',
        subject_type=subject_type,
        subject_id=subject_id,
        user_id=user_id,
        amount=credit_cost,
        model_id=model_id,
    )


async def confirm_chat_allowance(
    reservation: BillingReservation,
    chat_id: str | None = None,
    message_id: str | None = None,
):
    if reservation.kind == 'credit' and reservation.user_id:
        account = await Credits.get_or_create_account(reservation.user_id)
        await Credits.create_transaction(
            CreditTransactionCreateForm(
                user_id=reservation.user_id,
                type='confirm',
                amount=0,
                balance_after=account.balance,
                model_id=reservation.model_id,
                chat_id=chat_id,
                remark=f'confirmed chat usage {message_id or ""}'.strip(),
            )
        )


async def rollback_chat_allowance(reservation: BillingReservation, reason: str):
    if reservation.kind == 'free_quota':
        await Credits.restore_free_quota(reservation.subject_type, reservation.subject_id)
        return

    if reservation.kind == 'credit' and reservation.user_id:
        updated = await Credits.change_balance(
            reservation.user_id,
            amount_delta=reservation.amount,
            consumed_delta=-reservation.amount,
        )
        await Credits.create_transaction(
            CreditTransactionCreateForm(
                user_id=reservation.user_id,
                type='rollback',
                amount=reservation.amount,
                balance_after=updated.balance,
                model_id=reservation.model_id,
                remark=reason,
            )
        )


async def wrap_streaming_response_for_billing(
    iterator: AsyncIterator,
    reservation: BillingReservation,
    chat_id: str | None = None,
) -> AsyncIterator:
    try:
        async for chunk in iterator:
            yield chunk
        await confirm_chat_allowance(reservation, chat_id=chat_id)
    except Exception:
        await rollback_chat_allowance(reservation, reason='stream_failed')
        raise


async def reserve_chat_allowance_from_request(
    request: Request,
    user,
    form_data: dict,
    model_info: Any,
) -> BillingReservation | None:
    try:
        model_id = form_data.get('model')
        model_meta = model_info.meta.model_dump() if model_info and model_info.meta else {}
        credit_cost = model_meta.get('credit_cost')

        subject_type, subject_id, user_id = resolve_billing_subject(request, user)

        quota = await Credits.get_or_create_quota(subject_type, subject_id)
        if quota.free_chat_used < quota.free_chat_limit:
            credit_cost = 0
        elif credit_cost is None:
            raise MissingModelCreditCostError()

        return await reserve_chat_allowance(subject_type, subject_id, user_id, model_id, int(credit_cost))
    except HTTPException:
        raise
    except Exception:
        # Billing tables/config are optional in this local anonymous project.
        # Do not block chat when billing is unavailable.
        return None


async def get_credit_session_for_request(request: Request, user) -> CreditSession:
    subject_type, subject_id, user_id = resolve_billing_subject(request, user)
    summary: CreditSummary = await Credits.get_summary_for_subject(subject_type, subject_id, user_id=user_id)
    return CreditSession(
        balance=summary.balance,
        free_chat_used=summary.free_chat_used,
        free_chat_limit=summary.free_chat_limit,
    )
