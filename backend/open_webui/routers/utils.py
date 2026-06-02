import logging
import markdown
import json
import subprocess
import asyncio

from open_webui.models.chats import ChatTitleMessagesForm
from open_webui.config import DATA_DIR, ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from starlette.responses import FileResponse


from open_webui.utils.misc import get_gravatar_url
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.code_interpreter import execute_code_jupyter

log = logging.getLogger(__name__)

router = APIRouter()

_FEISHU_AUTH_TASKS: dict[str, dict] = {}


def _run_lark_cli_auth_command(args: list[str]) -> dict:
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=30,
    )

    stdout = (completed.stdout or '').strip()
    stderr = (completed.stderr or '').strip()
    data = None
    if stdout:
        try:
            data = json.loads(stdout)
        except Exception:
            data = None

    return {
        'ok': completed.returncode == 0,
        'exit_code': completed.returncode,
        'stdout': stdout,
        'stderr': stderr,
        'data': data,
    }


@router.get('/gravatar')
async def get_gravatar(email: str, user=Depends(get_verified_user)):
    return get_gravatar_url(email)


@router.get('/integrations/feishu/auth/status')
async def get_feishu_auth_status(user=Depends(get_verified_user)):
    try:
        result = _run_lark_cli_auth_command(['lark-cli', 'auth', 'status'])
        data = result.get('data') or {}
        identity = data.get('identity', '')
        note = data.get('note', '')

        authorized = identity == 'user' and 'Token does not exist' not in note

        return {
            'authorized': authorized,
            'identity': identity,
            'note': note,
            'user_name': data.get('userName', ''),
            'user_open_id': data.get('userOpenId', ''),
            'brand': data.get('brand', 'feishu'),
            'default_as': data.get('defaultAs', 'auto'),
        }
    except Exception as e:
        log.exception(f'Failed to get Feishu auth status: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/integrations/feishu/auth/start')
async def start_feishu_auth(user=Depends(get_verified_user)):
    try:
        result = _run_lark_cli_auth_command(
            ['lark-cli', 'auth', 'login', '--no-wait', '--json', '--domain', 'docs']
        )
        data = result.get('data') or {}
        if not data:
            raise HTTPException(status_code=500, detail=result.get('stderr') or 'Failed to start Feishu auth')

        verification_url = data.get('verification_url', '')
        device_code = data.get('device_code', '')
        expires_in = data.get('expires_in', 0)

        return {
            'verification_url': verification_url,
            'device_code': device_code,
            'expires_in': expires_in,
            'hint': data.get('hint', ''),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f'Failed to start Feishu auth: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/integrations/feishu/auth/complete')
async def complete_feishu_auth(user=Depends(get_verified_user)):
    try:
        task_id = user.id
        existing = _FEISHU_AUTH_TASKS.get(task_id)
        if existing and existing.get('task') and not existing['task'].done():
            return {'status': 'pending'}

        status_result = _run_lark_cli_auth_command(['lark-cli', 'auth', 'status'])
        status_data = status_result.get('data') or {}
        if status_data.get('identity') == 'user' and 'Token does not exist' not in status_data.get('note', ''):
            return {'status': 'authorized'}

        start_result = _run_lark_cli_auth_command(
            ['lark-cli', 'auth', 'login', '--no-wait', '--json', '--domain', 'docs']
        )
        data = start_result.get('data') or {}
        device_code = data.get('device_code', '')
        verification_url = data.get('verification_url', '')
        expires_in = int(data.get('expires_in', 600) or 600)

        if not device_code or not verification_url:
            raise HTTPException(status_code=500, detail='Failed to create Feishu auth session')

        async def wait_for_completion():
            try:
                proc = await asyncio.create_subprocess_exec(
                    'lark-cli',
                    'auth',
                    'login',
                    '--device-code',
                    device_code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=min(expires_in + 10, 660))
                _FEISHU_AUTH_TASKS[task_id]['result'] = {
                    'returncode': proc.returncode,
                    'stdout': stdout.decode('utf-8', 'replace'),
                    'stderr': stderr.decode('utf-8', 'replace'),
                }
            except Exception as e:
                _FEISHU_AUTH_TASKS[task_id]['result'] = {
                    'returncode': 1,
                    'stdout': '',
                    'stderr': str(e),
                }

        task = asyncio.create_task(wait_for_completion())
        _FEISHU_AUTH_TASKS[task_id] = {
            'device_code': device_code,
            'verification_url': verification_url,
            'expires_in': expires_in,
            'task': task,
            'result': None,
        }

        return {
            'status': 'pending',
            'verification_url': verification_url,
            'expires_in': expires_in,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f'Failed to complete Feishu auth: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/integrations/feishu/auth/poll')
async def poll_feishu_auth(user=Depends(get_verified_user)):
    try:
        task_data = _FEISHU_AUTH_TASKS.get(user.id)
        if not task_data:
            status_result = _run_lark_cli_auth_command(['lark-cli', 'auth', 'status'])
            status_data = status_result.get('data') or {}
            authorized = status_data.get('identity') == 'user' and 'Token does not exist' not in status_data.get(
                'note', ''
            )
            return {'status': 'authorized' if authorized else 'idle'}

        task = task_data.get('task')
        if task and not task.done():
            return {
                'status': 'pending',
                'verification_url': task_data.get('verification_url', ''),
                'expires_in': task_data.get('expires_in', 0),
            }

        result = task_data.get('result') or {}
        status_result = _run_lark_cli_auth_command(['lark-cli', 'auth', 'status'])
        status_data = status_result.get('data') or {}
        authorized = status_data.get('identity') == 'user' and 'Token does not exist' not in status_data.get(
            'note', ''
        )

        if authorized:
            _FEISHU_AUTH_TASKS.pop(user.id, None)
            return {'status': 'authorized'}

        return {
            'status': 'failed',
            'error': (result.get('stderr') or result.get('stdout') or status_data.get('note') or '').strip(),
        }
    except Exception as e:
        log.exception(f'Failed to poll Feishu auth: {e}')
        raise HTTPException(status_code=500, detail=str(e))


class CodeForm(BaseModel):
    code: str


@router.post('/code/format')
async def format_code(form_data: CodeForm, user=Depends(get_admin_user)):
    try:
        import black

        formatted_code = black.format_str(form_data.code, mode=black.Mode())
        return {'code': formatted_code}
    except black.NothingChanged:
        return {'code': form_data.code}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/code/execute')
async def execute_code(request: Request, form_data: CodeForm, user=Depends(get_verified_user)):
    if not request.app.state.config.ENABLE_CODE_EXECUTION:
        raise HTTPException(
            status_code=403,
            detail=ERROR_MESSAGES.FEATURE_DISABLED('Code execution'),
        )

    if request.app.state.config.CODE_EXECUTION_ENGINE == 'jupyter':
        output = await execute_code_jupyter(
            request.app.state.config.CODE_EXECUTION_JUPYTER_URL,
            form_data.code,
            (
                request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_TOKEN
                if request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH == 'token'
                else None
            ),
            (
                request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_PASSWORD
                if request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH == 'password'
                else None
            ),
            request.app.state.config.CODE_EXECUTION_JUPYTER_TIMEOUT,
        )

        return output
    else:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.DEFAULT('Code execution engine not supported'),
        )


class MarkdownForm(BaseModel):
    md: str


@router.post('/markdown')
async def get_html_from_markdown(form_data: MarkdownForm, user=Depends(get_verified_user)):
    return {'html': markdown.markdown(form_data.md)}


class ChatForm(BaseModel):
    title: str
    messages: list[dict]


@router.post('/pdf')
async def download_chat_as_pdf(form_data: ChatTitleMessagesForm, user=Depends(get_verified_user)):
    try:
        from open_webui.utils.pdf_generator import PDFGenerator

        pdf_bytes = PDFGenerator(form_data).generate_chat_pdf()

        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={'Content-Disposition': 'attachment;filename=chat.pdf'},
        )
    except Exception as e:
        log.exception(f'Error generating PDF: {e}')
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/db/download')
async def download_db(user=Depends(get_admin_user)):
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    from open_webui.internal.db import engine

    if engine.name != 'sqlite':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DB_NOT_SQLITE,
        )
    return FileResponse(
        engine.url.database,
        media_type='application/octet-stream',
        filename='webui.db',
    )
