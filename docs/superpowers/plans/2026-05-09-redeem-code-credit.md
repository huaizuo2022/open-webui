# Redeem Code Credit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build redeem-code-backed credits, five free chats for non-paying users, model-based point deduction, and a minimal admin UI for batch code generation and pricing.

**Architecture:** Add a small billing domain inside the backend with dedicated models, migrations, and service helpers, then wire both chat completion entrypoints through a shared guard that reserves free quota or credits and rolls back on failure. Extend the session user payload plus dedicated admin/user APIs, then add focused admin pages and lightweight user-facing balance/redeem UI.

**Tech Stack:** FastAPI, SQLAlchemy async models, Alembic migrations, SvelteKit, existing `src/lib/apis/*` wrappers, `svelte-check`, Ruff, pytest

---

## File Structure

### Backend files to create

- `backend/open_webui/models/credits.py`
  - 积分账户、积分流水、兑换码批次、兑换码、免费次数模型与数据访问
- `backend/open_webui/utils/billing.py`
  - 统一计费主体解析、免费次数/积分预占、确认、回滚
- `backend/open_webui/utils/device_id.py`
  - 解析 `X-OWUI-Device-Id`、校验 UUID、把匿名请求映射到 `device` quota subject
- `backend/open_webui/routers/credits.py`
  - 用户侧余额查询与兑换码核销接口
- `backend/open_webui/routers/admin_credits.py`
  - 管理员批次生成、列表、导出、兑换码明细接口
- `backend/open_webui/migrations/versions/5b6c7d8e9f10_add_credit_and_redeem_code_tables.py`
  - Alembic 迁移
- `backend/open_webui/test/test_credits_models.py`
- `backend/open_webui/test/test_billing.py`
- `backend/open_webui/test/test_credit_routers.py`

### Backend files to modify

- `backend/open_webui/main.py`
  - 注册新 router
- `backend/open_webui/routers/auths.py`
  - 扩展 `GET /api/v1/auths/` 返回积分/免费次数摘要，并更新 `SessionUserResponse` / `SessionUserInfoResponse`
- `backend/open_webui/routers/openai.py`
  - 接入聊天计费 guard
- `backend/open_webui/routers/ollama.py`
  - 接入聊天计费 guard
- `backend/open_webui/models/models.py`
  - 为模型元信息约定 `meta.credit_cost`

### Frontend files to create

- `src/lib/apis/credits/index.ts`
  - 用户侧与管理侧 credit API 封装
- `src/lib/apis/device.ts`
  - 统一生成和读取浏览器稳定 `device_id`
- `src/lib/components/admin/Credits/RedeemCodeBatches.svelte`
- `src/lib/components/admin/Credits/RedeemCodeDetails.svelte`
- `src/lib/components/admin/Credits/ModelCreditPricing.svelte`
- `src/routes/(app)/admin/credits/+page.svelte`
- `src/routes/(app)/admin/credits/[tab]/+page.svelte`
- `src/lib/components/chat/RedeemCodeModal.svelte`

### Frontend files to modify

- `src/lib/stores/index.ts`
  - 扩展 `SessionUser` 类型
- `src/lib/apis/auths/index.ts`
  - 复用扩展后的会话用户字段，并在匿名/会话请求上透传 `X-OWUI-Device-Id`
- `src/lib/apis/openai/index.ts`
  - 在聊天请求上透传 `X-OWUI-Device-Id`
- `src/routes/(app)/admin/+layout.svelte`
  - 增加 Credits 导航
- `src/lib/components/admin/Settings/Models.svelte`
  - 接入模型积分价格编辑入口
- `src/lib/components/chat/MessageInput.svelte`
  - 展示余额/剩余免费次数/兑换提示
- `src/routes/+layout.svelte`
  - 会话用户刷新后同步新字段

### Verification commands

- `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credits_models.py backend/open_webui/test/test_billing.py backend/open_webui/test/test_credit_routers.py -q`
- `cd /Users/shang/Dev/open-webui-anon && npm run check`
- `cd /Users/shang/Dev/open-webui-anon && python -m ruff check backend/open_webui`
- `cd /Users/shang/Dev/open-webui-anon/backend/open_webui && alembic -c alembic.ini upgrade head`

---

### Task 1: Create the failing backend schema tests

**Files:**
- Create: `backend/open_webui/test/test_credits_models.py`
- Reference: `backend/open_webui/models/users.py`
- Reference: `backend/open_webui/internal/db.py`

- [ ] **Step 1: Write the failing schema/model tests**

```python
import pytest

from open_webui.models.credits import (
    CreditAccountForm,
    RedeemCodeBatchForm,
    UsageQuotaSubject,
)


def test_credit_account_defaults():
    form = CreditAccountForm(user_id='u1')
    assert form.balance == 0
    assert form.total_recharged == 0
    assert form.total_consumed == 0


def test_redeem_batch_requires_positive_quantity():
    with pytest.raises(ValueError):
        RedeemCodeBatchForm(batch_name='tb-001', credit_amount=100, quantity=0)


def test_usage_quota_subject_enum_values():
    assert UsageQuotaSubject.USER.value == 'user'
    assert UsageQuotaSubject.DEVICE.value == 'device'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credits_models.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing symbols for `open_webui.models.credits`

- [ ] **Step 3: Write minimal model/form scaffolding**

```python
class UsageQuotaSubject(str, Enum):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credits_models.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui/test/test_credits_models.py backend/open_webui/models/credits.py
git commit -m "Define billing domain schema for redeemable credits"
```

---

### Task 2: Add database tables and migration

**Files:**
- Modify: `backend/open_webui/models/credits.py`
- Create: `backend/open_webui/migrations/versions/5b6c7d8e9f10_add_credit_and_redeem_code_tables.py`
- Test: `backend/open_webui/test/test_credits_models.py`

- [ ] **Step 1: Extend the failing tests with table-level expectations**

```python
from open_webui.models.credits import CreditAccount, RedeemCode, UsageQuota


def test_credit_tables_have_expected_tablenames():
    assert CreditAccount.__tablename__ == 'credit_account'
    assert RedeemCode.__tablename__ == 'redeem_code'
    assert UsageQuota.__tablename__ == 'usage_quota'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credits_models.py -q`
Expected: FAIL because SQLAlchemy models are not defined yet

- [ ] **Step 3: Implement SQLAlchemy models and Alembic migration**

```python
class CreditAccount(Base):
    __tablename__ = 'credit_account'
    id = Column(Text, primary_key=True)
    user_id = Column(Text, unique=True, nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    total_recharged = Column(BigInteger, nullable=False, default=0)
    total_consumed = Column(BigInteger, nullable=False, default=0)
```

```python
def upgrade():
    op.create_table(
        'credit_account',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False, unique=True),
        sa.Column('balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_recharged', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_consumed', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )
    op.create_index('ix_usage_quota_subject', 'usage_quota', ['subject_type', 'subject_id'], unique=True)
```

- [ ] **Step 4: Run targeted tests and migration smoke check**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credits_models.py -q`
Expected: PASS

Run: `cd /Users/shang/Dev/open-webui-anon/backend/open_webui && alembic -c alembic.ini upgrade head`
Expected: migration applies cleanly on local dev DB

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui/models/credits.py backend/open_webui/migrations/versions/*.py backend/open_webui/test/test_credits_models.py
git commit -m "Persist credit accounts, redeem codes, and free quota"
```

---

### Task 3: Build the billing service with free-quota and credit reservation

**Files:**
- Create: `backend/open_webui/test/test_billing.py`
- Create: `backend/open_webui/utils/billing.py`
- Create: `backend/open_webui/utils/device_id.py`
- Modify: `backend/open_webui/models/credits.py`
- Reference: `backend/open_webui/models/models.py`

- [ ] **Step 1: Write failing billing service tests**

```python
async def test_user_consumes_free_quota_before_credits():
    result = await reserve_chat_allowance(
        subject_type='user',
        subject_id='u1',
        user_id='u1',
        model_id='gpt-4o-mini',
        credit_cost=2,
    )
    assert result.kind == 'free_quota'


async def test_insufficient_credits_blocks_after_free_quota_exhausted():
    with pytest.raises(InsufficientCreditError):
        await reserve_chat_allowance(
            subject_type='user',
            subject_id='u2',
            user_id='u2',
            model_id='gpt-4o',
            credit_cost=10,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_billing.py -q`
Expected: FAIL because `reserve_chat_allowance` does not exist

- [ ] **Step 3: Implement minimal reservation/confirm/rollback service**

```python
@dataclass
class BillingReservation:
    kind: Literal['free_quota', 'credit']
    subject_type: str
    subject_id: str
    user_id: str | None
    amount: int
    model_id: str
    reservation_id: str


async def reserve_chat_allowance(subject_type, subject_id, user_id, model_id, credit_cost): ...
async def confirm_chat_allowance(reservation, chat_id=None, message_id=None): ...
async def rollback_chat_allowance(reservation, reason): ...
```

- [ ] **Step 3A: Add anonymous device-id subject resolution**

```python
DEVICE_ID_HEADER = 'X-OWUI-Device-Id'


def get_request_device_id(request: Request) -> str | None:
    raw = request.headers.get(DEVICE_ID_HEADER)
    if not raw:
        return None
    return str(UUID(raw))


def resolve_billing_subject(request: Request, user) -> tuple[str, str, str | None]:
    is_guest = getattr(user, 'email', None) == 'guest@localhost'
    if not is_guest:
        return ('user', user.id, user.id)

    device_id = get_request_device_id(request)
    if not device_id:
        raise HTTPException(status_code=400, detail='DEVICE_ID_REQUIRED')
    return ('device', device_id, None)
```

- [ ] **Step 3B: Add failing anonymous-device tests, then make them pass**

```python
async def test_guest_without_device_id_is_rejected():
    with pytest.raises(HTTPException):
        resolve_billing_subject(FakeRequest(headers={}), guest_user)


async def test_guest_with_device_id_uses_device_subject():
    request = FakeRequest(headers={'X-OWUI-Device-Id': str(uuid4())})
    subject_type, subject_id, user_id = resolve_billing_subject(request, guest_user)
    assert subject_type == 'device'
    assert user_id is None
```

- [ ] **Step 4: Run billing tests**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_billing.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui/test/test_billing.py backend/open_webui/utils/billing.py backend/open_webui/models/credits.py
git commit -m "Add billing guard for free quota and model-based credits"
```

---

### Task 4: Expose user credit summary and redeem-code APIs

**Files:**
- Create: `backend/open_webui/test/test_credit_routers.py`
- Create: `backend/open_webui/routers/credits.py`
- Modify: `backend/open_webui/main.py`
- Modify: `backend/open_webui/routers/auths.py`
- Modify: `backend/open_webui/models/credits.py`

- [ ] **Step 1: Write failing router tests**

```python
import pytest
from fastapi.testclient import TestClient


def build_test_app():
    app = FastAPI()
    app.include_router(router, prefix='/api/v1/credits')
    return app


@pytest.fixture
def client():
    return TestClient(build_test_app())


@pytest.fixture
def auth_headers():
    token = create_token(data={'id': 'u-credit'})
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def admin_headers():
    token = create_token(data={'id': 'u-admin'})
    return {'Authorization': f'Bearer {token}'}


async def test_get_my_credit_summary_returns_balance_and_free_quota(client, auth_headers):
    response = await client.get('/api/v1/credits/me', headers=auth_headers)
    assert response.status_code == 200
    assert {'balance', 'free_chat_used', 'free_chat_limit'} <= response.json().keys()


async def test_redeem_code_recharges_current_user(client, auth_headers):
    response = await client.post('/api/v1/credits/redeem', headers=auth_headers, json={'code': 'TB-100'})
    assert response.status_code == 200
    assert response.json()['balance'] == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credit_routers.py -q`
Expected: FAIL with 404 or import errors

- [ ] **Step 3: Implement user-facing router and extend session payload**

```python
class CreditSession(BaseModel):
    balance: int
    free_chat_used: int
    free_chat_limit: int


class SessionUserResponse(Token, UserProfileImageResponse):
    expires_at: Optional[int] = None
    permissions: Optional[dict] = None
    credit: Optional[CreditSession] = None


class SessionUserInfoResponse(SessionUserResponse, UserStatus):
    bio: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None


@router.get('/me')
async def get_my_credit_summary(user=Depends(get_verified_user)):
    return await Credits.get_summary_for_user(user.id)


@router.post('/redeem')
async def redeem_code(form_data: RedeemCodeForm, user=Depends(get_verified_user)):
    return await Credits.redeem_code_for_user(form_data.code, user.id)
```

```python
return {
    'token': token,
    'token_type': 'Bearer',
    'expires_at': expires_at,
    'id': user.id,
    'email': user.email,
    'name': user.name,
    'role': user.role,
    'profile_image_url': user.profile_image_url,
    'credit': {
        'balance': summary.balance,
        'free_chat_used': summary.free_chat_used,
        'free_chat_limit': summary.free_chat_limit,
    },
}
```

- [ ] **Step 4: Run router tests**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credit_routers.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui/test/test_credit_routers.py backend/open_webui/routers/credits.py backend/open_webui/main.py backend/open_webui/routers/auths.py
git commit -m "Expose redeem code redemption and credit summary APIs"
```

---

### Task 5: Wire OpenAI chat completions through the billing guard

**Files:**
- Modify: `backend/open_webui/routers/openai.py`
- Modify: `backend/open_webui/test/test_billing.py`
- Modify: `backend/open_webui/utils/billing.py`

- [ ] **Step 1: Add a failing integration-style billing test**

```python
async def failing_stream():
    yield b'data: {"delta":"ok"}\n\n'
    raise RuntimeError('stream failed')


async def test_openai_stream_rolls_back_credit_on_generator_failure():
    reservation = await reserve_chat_allowance(
        subject_type='user',
        subject_id='u-credit',
        user_id='u-credit',
        model_id='gpt-4o',
        credit_cost=10,
    )
    wrapped = wrap_streaming_response_for_billing(failing_stream(), reservation)
    with pytest.raises(RuntimeError):
        async for _ in wrapped:
            pass
    summary = await Credits.get_summary_for_user('u-credit')
    assert summary.balance == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_billing.py -q`
Expected: FAIL because rollback bookkeeping is incomplete

- [ ] **Step 3: Wrap `generate_chat_completion` with reserve/confirm/rollback**

```python
reservation = await reserve_chat_allowance_from_request(request, user, form_data, model_info)
response = await _generate_openai_chat_completion_impl(...)
if isinstance(response, StreamingResponse):
    response.body_iterator = wrap_streaming_response_for_billing(
        response.body_iterator,
        reservation,
        chat_id=metadata.get('chat_id') if metadata else None,
    )
    return response
try:
    await confirm_chat_allowance(reservation, chat_id=metadata.get('chat_id') if metadata else None)
    return response
except Exception:
    await rollback_chat_allowance(reservation, reason='chat_failed')
    raise
```

- [ ] **Step 4: Run billing tests**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_billing.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui/routers/openai.py backend/open_webui/test/test_billing.py backend/open_webui/utils/billing.py
git commit -m "Guard OpenAI chat completions with quota and credit billing"
```

---

### Task 6: Wire Ollama chat completions through the same guard

**Files:**
- Modify: `backend/open_webui/routers/ollama.py`
- Modify: `backend/open_webui/test/test_billing.py`

- [ ] **Step 1: Add a failing parity test or assertion for Ollama path**

```python
async def test_ollama_chat_uses_same_billing_guard():
    reservation = await reserve_chat_allowance(
        subject_type='device',
        subject_id='device-1',
        user_id=None,
        model_id='llama3.1',
        credit_cost=3,
    )
    assert reservation.model_id == 'llama3.1'
```

- [ ] **Step 2: Run test to verify it fails or is missing coverage**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_billing.py -q`
Expected: FAIL or uncovered code path identified

- [ ] **Step 3: Apply the same reserve/confirm/rollback flow in Ollama router**

```python
reservation = await reserve_chat_allowance_from_request(request, user, form_data, model_info)
response = await _generate_ollama_chat_completion_impl(...)
if isinstance(response, StreamingResponse):
    response.body_iterator = wrap_streaming_response_for_billing(
        response.body_iterator,
        reservation,
        chat_id=metadata.get('chat_id') if metadata else None,
    )
    return response
try:
    await confirm_chat_allowance(reservation, chat_id=metadata.get('chat_id') if metadata else None)
    return response
except Exception:
    await rollback_chat_allowance(reservation, reason='chat_failed')
    raise
```

- [ ] **Step 4: Run billing tests**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_billing.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui/routers/ollama.py backend/open_webui/test/test_billing.py
git commit -m "Apply consistent billing to Ollama chat completions"
```

---

### Task 7: Add admin APIs for redeem-code batches and exports

**Files:**
- Create: `backend/open_webui/routers/admin_credits.py`
- Modify: `backend/open_webui/main.py`
- Modify: `backend/open_webui/models/credits.py`
- Modify: `backend/open_webui/test/test_credit_routers.py`

- [ ] **Step 1: Write failing admin API tests**

```python
async def test_admin_can_create_batch_and_generate_codes(client, admin_headers):
    response = await client.post(
        '/api/v1/admin/redeem-codes/batches',
        headers=admin_headers,
        json={'batch_name': 'tb-may', 'credit_amount': 100, 'quantity': 3},
    )
    assert response.status_code == 200
    assert len(response.json()['codes']) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credit_routers.py -q`
Expected: FAIL with 404/import errors

- [ ] **Step 3: Implement admin router, batch generation, and export payload**

```python
@router.post('/redeem-codes/batches')
async def create_redeem_code_batch(form_data: RedeemCodeBatchForm, user=Depends(get_admin_user)): ...


@router.get('/redeem-codes')
async def list_redeem_codes(batch_id: str | None = None, status: str | None = None, user=Depends(get_admin_user)): ...


@router.get('/redeem-codes/batches/{batch_id}/export')
async def export_redeem_codes(batch_id: str, user=Depends(get_admin_user)): ...
```

- [ ] **Step 4: Run router tests**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credit_routers.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui/routers/admin_credits.py backend/open_webui/main.py backend/open_webui/models/credits.py backend/open_webui/test/test_credit_routers.py
git commit -m "Add admin batch generation and redeem-code export APIs"
```

---

### Task 8: Extend frontend session types and add credit API wrappers

**Files:**
- Create: `src/lib/apis/credits/index.ts`
- Create: `src/lib/apis/device.ts`
- Modify: `src/lib/stores/index.ts`
- Modify: `src/lib/apis/auths/index.ts`
- Modify: `src/lib/apis/openai/index.ts`

- [ ] **Step 1: Write the failing type/API shape updates**

```ts
export type SessionUser = {
  permissions: any;
  id: string;
  email: string;
  name: string;
  role: string;
  profile_image_url: string;
  credit?: {
    balance: number;
    free_chat_used: number;
    free_chat_limit: number;
  };
};
```

```ts
export const getMyCredits = async (token: string) => { /* fetch /credits/me */ }
export const redeemCode = async (token: string, code: string) => { /* post /credits/redeem */ }
```

```ts
import { v4 as uuidv4 } from 'uuid';

const DEVICE_ID_KEY = 'owui_device_id';

export const getDeviceId = () => {
	let value = localStorage.getItem(DEVICE_ID_KEY);
	if (!value) {
		value = uuidv4();
		localStorage.setItem(DEVICE_ID_KEY, value);
	}
	return value;
};
```

- [ ] **Step 2: Run typecheck to verify it fails before implementation**

Run: `cd /Users/shang/Dev/open-webui-anon && npm run check`
Expected: FAIL once consuming components reference missing `credit` fields or API module

- [ ] **Step 3: Implement API wrappers and type extension**

```ts
const res = await fetch(`${WEBUI_API_BASE_URL}/credits/me`, {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    'X-OWUI-Device-Id': getDeviceId()
  }
});
```

```ts
const res = await fetch(`${OPENAI_API_BASE_URL}/chat/completions`, {
	method: 'POST',
	headers: {
		'Content-Type': 'application/json',
		authorization: `Bearer ${token}`,
		'X-OWUI-Device-Id': getDeviceId()
	},
	credentials: 'include',
	body: JSON.stringify(body)
});
```

```ts
const res = await fetch(`${WEBUI_BASE_URL}/api/chat/completions`, {
	method: 'POST',
	headers: {
		Authorization: `Bearer ${token}`,
		'Content-Type': 'application/json',
		'X-OWUI-Device-Id': getDeviceId()
	},
	credentials: 'include',
	body: JSON.stringify(body)
});
```

- [ ] **Step 4: Run typecheck**

Run: `cd /Users/shang/Dev/open-webui-anon && npm run check`
Expected: PASS for these additions

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add src/lib/apis/credits/index.ts src/lib/apis/device.ts src/lib/stores/index.ts src/lib/apis/auths/index.ts src/lib/apis/openai/index.ts
git commit -m "Add frontend credit client and anonymous device id plumbing"
```

---

### Task 9: Add admin credits pages and model pricing controls

**Files:**
- Create: `src/routes/(app)/admin/credits/+page.svelte`
- Create: `src/routes/(app)/admin/credits/[tab]/+page.svelte`
- Create: `src/lib/components/admin/Credits/RedeemCodeBatches.svelte`
- Create: `src/lib/components/admin/Credits/RedeemCodeDetails.svelte`
- Create: `src/lib/components/admin/Credits/ModelCreditPricing.svelte`
- Modify: `src/routes/(app)/admin/+layout.svelte`
- Modify: `src/lib/components/admin/Settings/Models.svelte`

- [ ] **Step 1: Add the failing route/component skeletons**

```svelte
<script>
  import RedeemCodeBatches from '$lib/components/admin/Credits/RedeemCodeBatches.svelte';
</script>

<RedeemCodeBatches />
```

- [ ] **Step 2: Run typecheck to verify missing imports or props**

Run: `cd /Users/shang/Dev/open-webui-anon && npm run check`
Expected: FAIL until all components and imports exist

- [ ] **Step 3: Implement minimal admin pages**

```svelte
<a
  class="min-w-fit p-1.5 {$page.url.pathname.includes('/admin/credits')
    ? ''
    : 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
  href="/admin/credits"
>
  {$i18n.t('Credits')}
</a>
```

```svelte
<button on:click={createBatch}>Generate Codes</button>
<button on:click={exportBatch}>Export</button>
```

```svelte
<input bind:value={creditCost} />
<button on:click={() => saveModelPrice(model.id, creditCost)}>Save</button>
```

- [ ] **Step 4: Run typecheck**

Run: `cd /Users/shang/Dev/open-webui-anon && npm run check`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add 'src/routes/(app)/admin/credits/+page.svelte' 'src/routes/(app)/admin/credits/[tab]/+page.svelte' src/lib/components/admin/Credits/*.svelte 'src/routes/(app)/admin/+layout.svelte' src/lib/components/admin/Settings/Models.svelte
git commit -m "Add admin UI for redeem-code batches and model credit pricing"
```

---

### Task 10: Add user-facing redeem modal and low-balance/free-quota messaging

**Files:**
- Create: `src/lib/components/chat/RedeemCodeModal.svelte`
- Modify: `src/lib/components/chat/MessageInput.svelte`
- Modify: `src/routes/+layout.svelte`

- [ ] **Step 1: Add the failing user-flow hooks**

```svelte
{#if $user?.credit}
  <div>{$user.credit.balance} credits</div>
{/if}
```

```svelte
<RedeemCodeModal bind:open={showRedeemModal} />
```

- [ ] **Step 2: Run typecheck to verify it fails without the new component/wiring**

Run: `cd /Users/shang/Dev/open-webui-anon && npm run check`
Expected: FAIL until modal and props are defined

- [ ] **Step 3: Implement redeem modal and send-precheck UX**

```svelte
if ($user?.credit && $user.credit.free_chat_used >= $user.credit.free_chat_limit && $user.credit.balance <= 0) {
  toast.error($i18n.t('Free chats used up. Redeem a code to continue.'));
  showRedeemModal = true;
  return;
}
```

- [ ] **Step 4: Run typecheck**

Run: `cd /Users/shang/Dev/open-webui-anon && npm run check`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add src/lib/components/chat/RedeemCodeModal.svelte src/lib/components/chat/MessageInput.svelte src/routes/+layout.svelte
git commit -m "Surface credit balance and redeem flow in chat UI"
```

---

### Task 11: Full verification and cleanup

**Files:**
- Verify only: all files touched above

- [ ] **Step 1: Run backend tests**

Run: `cd /Users/shang/Dev/open-webui-anon && PYTHONPATH=backend pytest backend/open_webui/test/test_credits_models.py backend/open_webui/test/test_billing.py backend/open_webui/test/test_credit_routers.py -q`
Expected: PASS

- [ ] **Step 2: Run backend lint**

Run: `cd /Users/shang/Dev/open-webui-anon && python -m ruff check backend/open_webui`
Expected: PASS

- [ ] **Step 3: Run frontend typecheck**

Run: `cd /Users/shang/Dev/open-webui-anon && npm run check`
Expected: PASS

- [ ] **Step 4: Run focused manual verification**

Run:

```bash
cd /Users/shang/Dev/open-webui-anon
npm run dev
# In another shell, start backend as this repo normally does
```

Manual expectations:
- 匿名设备前 5 次聊天成功，第 6 次被拦截
- 登录用户前 5 次后无积分被拦截
- 核销兑换码后余额增加
- 不同模型按不同 `credit_cost` 扣分
- 免费次数已用尽且模型未配置 `credit_cost` 时，发送被结构化错误拦截
- `/api/chat/completions` 流式响应正常结束后才确认扣费；中途异常时发生回滚
- 聊天失败后余额或免费次数回滚

- [ ] **Step 5: Final commit**

```bash
cd /Users/shang/Dev/open-webui-anon
git add backend/open_webui src docs/superpowers
git commit -m "Gate chat usage with redeemable credits and free-quota limits"
```

## Notes For Implementers

- 不要把匿名免费次数绑到 `guest@localhost` 账号本身；必须以 `device_id` 为主体，否则所有匿名用户共用 5 次额度。
- OpenAI 与 Ollama 两个聊天入口都必须接入相同 guard。
- 第一版模型价格统一使用整数积分，不要引入 token 级计费。
- 如需新增错误码，保持前端可直接基于 `detail` 或结构化 `code` 做提示，不要只返回模糊文案。
