import enum
import logging
import secrets
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import BigInteger, Column, Index, String, Text, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context

log = logging.getLogger(__name__)


class CreditAccount(Base):
    __tablename__ = 'credit_account'

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, unique=True, nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    total_recharged = Column(BigInteger, nullable=False, default=0)
    total_consumed = Column(BigInteger, nullable=False, default=0)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class CreditTransaction(Base):
    __tablename__ = 'credit_transaction'

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, nullable=False)
    type = Column(String, nullable=False)
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger, nullable=False)
    model_id = Column(String, nullable=True)
    chat_id = Column(String, nullable=True)
    redeem_code_id = Column(String, nullable=True)
    remark = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index('idx_credit_transaction_user_id', 'user_id'),
        Index('idx_credit_transaction_created_at', 'created_at'),
    )


class RedeemCodeBatch(Base):
    __tablename__ = 'redeem_code_batch'

    id = Column(String, primary_key=True, unique=True)
    batch_name = Column(String, nullable=False)
    credit_amount = Column(BigInteger, nullable=False)
    quantity = Column(BigInteger, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(BigInteger, nullable=False)


class RedeemCode(Base):
    __tablename__ = 'redeem_code'

    id = Column(String, primary_key=True, unique=True)
    batch_id = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    credit_amount = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False, default='unused')
    used_by_user_id = Column(String, nullable=True)
    used_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index('idx_redeem_code_batch_id', 'batch_id'),
        Index('idx_redeem_code_status', 'status'),
    )


class UsageQuota(Base):
    __tablename__ = 'usage_quota'

    id = Column(String, primary_key=True, unique=True)
    subject_type = Column(String, nullable=False)
    subject_id = Column(String, nullable=False)
    free_chat_used = Column(BigInteger, nullable=False, default=0)
    free_chat_limit = Column(BigInteger, nullable=False, default=5)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index('ix_usage_quota_subject', 'subject_type', 'subject_id', unique=True),
    )


class UsageQuotaSubject(str, enum.Enum):
    USER = 'user'
    DEVICE = 'device'


class CreditAccountForm(BaseModel):
    user_id: str
    balance: int = 0
    total_recharged: int = 0
    total_consumed: int = 0


class RedeemCodeBatchForm(BaseModel):
    batch_name: str
    credit_amount: int
    quantity: int

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, value: int) -> int:
        if value <= 0:
            raise ValueError('quantity must be positive')
        return value

    @field_validator('credit_amount')
    @classmethod
    def validate_credit_amount(cls, value: int) -> int:
        if value <= 0:
            raise ValueError('credit_amount must be positive')
        return value


class RedeemCodeRedeemForm(BaseModel):
    code: str


class CreditSummary(BaseModel):
    balance: int = 0
    total_recharged: int = 0
    total_consumed: int = 0
    free_chat_used: int = 0
    free_chat_limit: int = 5


class CreditSession(BaseModel):
    balance: int = 0
    free_chat_used: int = 0
    free_chat_limit: int = 5


class CreditAccountModel(BaseModel):
    id: str
    user_id: str
    balance: int
    total_recharged: int
    total_consumed: int
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class RedeemCodeModel(BaseModel):
    id: str
    batch_id: str
    code: str
    credit_amount: int
    status: str
    used_by_user_id: Optional[str] = None
    used_at: Optional[int] = None
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class RedeemCodeBatchModel(BaseModel):
    id: str
    batch_name: str
    credit_amount: int
    quantity: int
    created_by: str
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class RedeemCodeBatchListResponse(BaseModel):
    items: list[RedeemCodeBatchModel]
    total: int


class RedeemCodeBatchCreateResponse(BaseModel):
    batch: RedeemCodeBatchModel
    codes: list[RedeemCodeModel]


class RedeemCodeListResponse(BaseModel):
    items: list[RedeemCodeModel]
    total: int


class CreditTransactionModel(BaseModel):
    id: str
    user_id: str
    type: str
    amount: int
    balance_after: int
    model_id: Optional[str] = None
    chat_id: Optional[str] = None
    redeem_code_id: Optional[str] = None
    remark: Optional[str] = None
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class CreditTransactionCreateForm(BaseModel):
    user_id: str
    type: str
    amount: int
    balance_after: int
    model_id: Optional[str] = None
    chat_id: Optional[str] = None
    redeem_code_id: Optional[str] = None
    remark: Optional[str] = None


class UsageQuotaModel(BaseModel):
    id: str
    subject_type: str
    subject_id: str
    free_chat_used: int
    free_chat_limit: int
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class UsageQuotaConsumeResult(BaseModel):
    quota: UsageQuotaModel
    consumed: bool = True


class CreditTables:
    async def get_or_create_account(self, user_id: str, db: Optional[AsyncSession] = None) -> CreditAccountModel:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(CreditAccount).where(CreditAccount.user_id == user_id))
            account = result.scalar_one_or_none()
            if account is None:
                now = int(time.time())
                account = CreditAccount(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    balance=0,
                    total_recharged=0,
                    total_consumed=0,
                    created_at=now,
                    updated_at=now,
                )
                db.add(account)
                await db.commit()
                await db.refresh(account)
            return CreditAccountModel.model_validate(account)

    async def get_account_by_user_id(self, user_id: str, db: Optional[AsyncSession] = None) -> Optional[CreditAccountModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(CreditAccount).where(CreditAccount.user_id == user_id))
            account = result.scalar_one_or_none()
            return CreditAccountModel.model_validate(account) if account else None

    async def change_balance(
        self,
        user_id: str,
        amount_delta: int,
        recharge_delta: int = 0,
        consumed_delta: int = 0,
        db: Optional[AsyncSession] = None,
    ) -> CreditAccountModel:
        async with get_async_db_context(db) as db:
            account = await self.get_or_create_account(user_id, db=db)
            now = int(time.time())
            new_balance = account.balance + amount_delta
            if new_balance < 0:
                raise ValueError('insufficient balance')
            await db.execute(
                update(CreditAccount)
                .where(CreditAccount.user_id == user_id)
                .values(
                    balance=new_balance,
                    total_recharged=account.total_recharged + recharge_delta,
                    total_consumed=account.total_consumed + consumed_delta,
                    updated_at=now,
                )
            )
            await db.commit()
            return await self.get_or_create_account(user_id, db=db)

    async def create_transaction(
        self,
        form_data: CreditTransactionCreateForm,
        db: Optional[AsyncSession] = None,
    ) -> CreditTransactionModel:
        async with get_async_db_context(db) as db:
            tx = CreditTransaction(
                id=str(uuid.uuid4()),
                user_id=form_data.user_id,
                type=form_data.type,
                amount=form_data.amount,
                balance_after=form_data.balance_after,
                model_id=form_data.model_id,
                chat_id=form_data.chat_id,
                redeem_code_id=form_data.redeem_code_id,
                remark=form_data.remark,
                created_at=int(time.time()),
            )
            db.add(tx)
            await db.commit()
            await db.refresh(tx)
            return CreditTransactionModel.model_validate(tx)

    async def get_or_create_quota(
        self,
        subject_type: str,
        subject_id: str,
        default_limit: int = 5,
        db: Optional[AsyncSession] = None,
    ) -> UsageQuotaModel:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(UsageQuota).where(
                    UsageQuota.subject_type == subject_type,
                    UsageQuota.subject_id == subject_id,
                )
            )
            quota = result.scalar_one_or_none()
            if quota is None:
                now = int(time.time())
                quota = UsageQuota(
                    id=str(uuid.uuid4()),
                    subject_type=subject_type,
                    subject_id=subject_id,
                    free_chat_used=0,
                    free_chat_limit=default_limit,
                    created_at=now,
                    updated_at=now,
                )
                db.add(quota)
                await db.commit()
                await db.refresh(quota)
            return UsageQuotaModel.model_validate(quota)

    async def consume_free_quota(
        self,
        subject_type: str,
        subject_id: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[UsageQuotaConsumeResult]:
        async with get_async_db_context(db) as db:
            quota = await self.get_or_create_quota(subject_type, subject_id, db=db)
            if quota.free_chat_used >= quota.free_chat_limit:
                return None
            now = int(time.time())
            await db.execute(
                update(UsageQuota)
                .where(UsageQuota.id == quota.id)
                .values(free_chat_used=quota.free_chat_used + 1, updated_at=now)
            )
            await db.commit()
            updated = await self.get_or_create_quota(subject_type, subject_id, db=db)
            return UsageQuotaConsumeResult(quota=updated)

    async def restore_free_quota(
        self,
        subject_type: str,
        subject_id: str,
        db: Optional[AsyncSession] = None,
    ) -> UsageQuotaModel:
        async with get_async_db_context(db) as db:
            quota = await self.get_or_create_quota(subject_type, subject_id, db=db)
            now = int(time.time())
            new_used = max(quota.free_chat_used - 1, 0)
            await db.execute(
                update(UsageQuota)
                .where(UsageQuota.id == quota.id)
                .values(free_chat_used=new_used, updated_at=now)
            )
            await db.commit()
            return await self.get_or_create_quota(subject_type, subject_id, db=db)

    async def create_batch(
        self,
        form_data: RedeemCodeBatchForm,
        created_by: str,
        db: Optional[AsyncSession] = None,
    ) -> RedeemCodeBatchCreateResponse:
        async with get_async_db_context(db) as db:
            now = int(time.time())
            batch = RedeemCodeBatch(
                id=str(uuid.uuid4()),
                batch_name=form_data.batch_name,
                credit_amount=form_data.credit_amount,
                quantity=form_data.quantity,
                created_by=created_by,
                created_at=now,
            )
            db.add(batch)
            await db.flush()

            codes: list[RedeemCode] = []
            for _ in range(form_data.quantity):
                code = RedeemCode(
                    id=str(uuid.uuid4()),
                    batch_id=batch.id,
                    code=self.generate_code(),
                    credit_amount=form_data.credit_amount,
                    status='unused',
                    created_at=now,
                )
                db.add(code)
                codes.append(code)

            await db.commit()
            await db.refresh(batch)
            for code in codes:
                await db.refresh(code)

            return RedeemCodeBatchCreateResponse(
                batch=RedeemCodeBatchModel.model_validate(batch),
                codes=[RedeemCodeModel.model_validate(code) for code in codes],
            )

    async def list_codes(
        self,
        batch_id: Optional[str] = None,
        status: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> RedeemCodeListResponse:
        async with get_async_db_context(db) as db:
            stmt = select(RedeemCode)
            if batch_id:
                stmt = stmt.where(RedeemCode.batch_id == batch_id)
            if status:
                stmt = stmt.where(RedeemCode.status == status)
            stmt = stmt.order_by(RedeemCode.created_at.desc())
            result = await db.execute(stmt)
            items = result.scalars().all()
            return RedeemCodeListResponse(items=[RedeemCodeModel.model_validate(item) for item in items], total=len(items))

    async def list_batches(
        self,
        db: Optional[AsyncSession] = None,
    ) -> RedeemCodeBatchListResponse:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(RedeemCodeBatch).order_by(RedeemCodeBatch.created_at.desc()))
            items = result.scalars().all()
            return RedeemCodeBatchListResponse(
                items=[RedeemCodeBatchModel.model_validate(item) for item in items],
                total=len(items),
            )

    async def get_code_by_value(self, code: str, db: Optional[AsyncSession] = None) -> Optional[RedeemCodeModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(RedeemCode).where(RedeemCode.code == code))
            item = result.scalar_one_or_none()
            return RedeemCodeModel.model_validate(item) if item else None

    async def mark_code_used(
        self,
        code: str,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> RedeemCodeModel:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(RedeemCode).where(RedeemCode.code == code))
            item = result.scalar_one_or_none()
            if item is None:
                raise ValueError('redeem code not found')
            if item.status == 'used':
                raise ValueError('redeem code already used')
            now = int(time.time())
            await db.execute(
                update(RedeemCode)
                .where(RedeemCode.id == item.id)
                .values(status='used', used_by_user_id=user_id, used_at=now)
            )
            await db.commit()
            return (await self.get_code_by_value(code, db=db))

    async def get_summary_for_user(
        self,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> CreditSummary:
        account = await self.get_or_create_account(user_id, db=db)
        quota = await self.get_or_create_quota(UsageQuotaSubject.USER.value, user_id, db=db)
        return CreditSummary(
            balance=account.balance,
            total_recharged=account.total_recharged,
            total_consumed=account.total_consumed,
            free_chat_used=quota.free_chat_used,
            free_chat_limit=quota.free_chat_limit,
        )

    async def get_summary_for_subject(
        self,
        subject_type: str,
        subject_id: str,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> CreditSummary:
        quota = await self.get_or_create_quota(subject_type, subject_id, db=db)
        if user_id:
            account = await self.get_or_create_account(user_id, db=db)
            return CreditSummary(
                balance=account.balance,
                total_recharged=account.total_recharged,
                total_consumed=account.total_consumed,
                free_chat_used=quota.free_chat_used,
                free_chat_limit=quota.free_chat_limit,
            )

        return CreditSummary(
            balance=0,
            total_recharged=0,
            total_consumed=0,
            free_chat_used=quota.free_chat_used,
            free_chat_limit=quota.free_chat_limit,
        )

    @staticmethod
    def generate_code() -> str:
        return f'TB-{secrets.token_hex(4).upper()}'


Credits = CreditTables()
