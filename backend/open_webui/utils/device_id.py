from uuid import UUID

from fastapi import HTTPException, Request

DEVICE_ID_HEADER = 'X-OWUI-Device-Id'


def get_request_device_id(request: Request) -> str | None:
    raw = request.headers.get(DEVICE_ID_HEADER)
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='INVALID_DEVICE_ID') from exc


def is_guest_user(user) -> bool:
    return getattr(user, 'email', None) == 'guest@localhost'


def resolve_billing_subject(request: Request, user) -> tuple[str, str, str | None]:
    if not is_guest_user(user):
        return ('user', user.id, user.id)

    device_id = get_request_device_id(request)
    if not device_id:
        # Local anonymous sessions and some internal server-side follow-up calls
        # may not carry the browser device header. Fall back to the guest user id
        # so billing does not block chat behavior in anonymous mode.
        return ('user', user.id, user.id)
    return ('device', device_id, None)
