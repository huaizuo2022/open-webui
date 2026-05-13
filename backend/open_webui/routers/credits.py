from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.models.credits import CreditTransactionCreateForm, Credits, RedeemCodeRedeemForm
from open_webui.utils.auth import get_verified_user

router = APIRouter()


@router.get('/me')
async def get_my_credit_summary(user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    return await Credits.get_summary_for_user(user.id, db=db)


@router.post('/redeem')
async def redeem_code(
    form_data: RedeemCodeRedeemForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if user.email == 'guest@localhost':
        raise HTTPException(status_code=401, detail='SIGN_IN_REQUIRED_FOR_REDEEM')

    try:
        code = await Credits.mark_code_used(form_data.code, user.id, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated = await Credits.change_balance(
        user.id,
        amount_delta=code.credit_amount,
        recharge_delta=code.credit_amount,
        db=db,
    )
    await Credits.create_transaction(
        CreditTransactionCreateForm(
            user_id=user.id,
            type='redeem',
            amount=code.credit_amount,
            balance_after=updated.balance,
            redeem_code_id=code.id,
            remark=f'redeemed {code.code}',
        ),
        db=db,
    )
    return await Credits.get_summary_for_user(user.id, db=db)
