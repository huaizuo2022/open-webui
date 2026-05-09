from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.models.credits import Credits, RedeemCodeBatchForm
from open_webui.utils.auth import get_admin_user

router = APIRouter()


@router.post('/credits/redeem-codes/batches')
async def create_redeem_code_batch(
    form_data: RedeemCodeBatchForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await Credits.create_batch(form_data, user.id, db=db)


@router.get('/credits/redeem-codes/batches')
async def list_redeem_code_batches(
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await Credits.list_batches(db=db)


@router.get('/credits/redeem-codes')
async def list_redeem_codes(
    batch_id: str | None = None,
    status: str | None = None,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await Credits.list_codes(batch_id=batch_id, status=status, db=db)


@router.get('/credits/redeem-codes/batches/{batch_id}/export')
async def export_redeem_codes(
    batch_id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await Credits.list_codes(batch_id=batch_id, db=db)
