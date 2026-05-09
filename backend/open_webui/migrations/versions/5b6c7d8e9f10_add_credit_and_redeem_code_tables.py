"""add credit and redeem code tables

Revision ID: 5b6c7d8e9f10
Revises: 3af16a1c9fb6
Create Date: 2026-05-09 15:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from open_webui.migrations.util import get_existing_tables

revision: str = '5b6c7d8e9f10'
down_revision: Union[str, None] = '56359461a091'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if 'credit_account' not in existing_tables:
        op.create_table(
            'credit_account',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), nullable=False, unique=True),
            sa.Column('balance', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('total_recharged', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('total_consumed', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )

    if 'credit_transaction' not in existing_tables:
        op.create_table(
            'credit_transaction',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('type', sa.String(), nullable=False),
            sa.Column('amount', sa.BigInteger(), nullable=False),
            sa.Column('balance_after', sa.BigInteger(), nullable=False),
            sa.Column('model_id', sa.String(), nullable=True),
            sa.Column('chat_id', sa.String(), nullable=True),
            sa.Column('redeem_code_id', sa.String(), nullable=True),
            sa.Column('remark', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('idx_credit_transaction_user_id', 'credit_transaction', ['user_id'])
        op.create_index('idx_credit_transaction_created_at', 'credit_transaction', ['created_at'])

    if 'redeem_code_batch' not in existing_tables:
        op.create_table(
            'redeem_code_batch',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('batch_name', sa.String(), nullable=False),
            sa.Column('credit_amount', sa.BigInteger(), nullable=False),
            sa.Column('quantity', sa.BigInteger(), nullable=False),
            sa.Column('created_by', sa.String(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )

    if 'redeem_code' not in existing_tables:
        op.create_table(
            'redeem_code',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('batch_id', sa.String(), nullable=False),
            sa.Column('code', sa.String(), nullable=False, unique=True),
            sa.Column('credit_amount', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='unused'),
            sa.Column('used_by_user_id', sa.String(), nullable=True),
            sa.Column('used_at', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('idx_redeem_code_batch_id', 'redeem_code', ['batch_id'])
        op.create_index('idx_redeem_code_status', 'redeem_code', ['status'])

    if 'usage_quota' not in existing_tables:
        op.create_table(
            'usage_quota',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('subject_type', sa.String(), nullable=False),
            sa.Column('subject_id', sa.String(), nullable=False),
            sa.Column('free_chat_used', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('free_chat_limit', sa.BigInteger(), nullable=False, server_default='5'),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_usage_quota_subject', 'usage_quota', ['subject_type', 'subject_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_usage_quota_subject', table_name='usage_quota')
    op.drop_table('usage_quota')
    op.drop_index('idx_redeem_code_status', table_name='redeem_code')
    op.drop_index('idx_redeem_code_batch_id', table_name='redeem_code')
    op.drop_table('redeem_code')
    op.drop_table('redeem_code_batch')
    op.drop_index('idx_credit_transaction_created_at', table_name='credit_transaction')
    op.drop_index('idx_credit_transaction_user_id', table_name='credit_transaction')
    op.drop_table('credit_transaction')
    op.drop_table('credit_account')
