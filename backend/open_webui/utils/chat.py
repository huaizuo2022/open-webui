import time
import logging
import sys
import os

from aiocache import cached
from typing import Any, Callable, Awaitable, Optional
import random
import json

import uuid
import asyncio

from fastapi import HTTPException, Request, status
from starlette.responses import Response, StreamingResponse, JSONResponse


from open_webui.models.users import UserModel

from open_webui.socket.main import (
    sio,
    get_event_call,
    get_event_emitter,
)
from open_webui.functions import generate_function_chat_completion

from open_webui.routers.openai import (
    generate_chat_completion as generate_openai_chat_completion,
)

from open_webui.routers.ollama import (
    generate_chat_completion as generate_ollama_chat_completion,
)

from open_webui.routers.pipelines import (
    process_pipeline_inlet_filter,
    process_pipeline_outlet_filter,
)

from open_webui.models.functions import Functions
from open_webui.models.models import Models

from open_webui.utils.models import get_all_models, check_model_access
from open_webui.utils.payload import convert_payload_openai_to_ollama
from open_webui.utils.response import (
    convert_response_ollama_to_openai,
    convert_streaming_response_ollama_to_openai,
)
from open_webui.utils.filter import (
    get_sorted_filter_ids,
    process_filter_functions,
)

from open_webui.env import GLOBAL_LOG_LEVEL, BYPASS_MODEL_ACCESS_CONTROL

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


DEFAULT_CHAT_MODEL_MIN_INTERVAL_SECONDS = {
    'deepseek-v4-flash': 21.0,
}

_CHAT_MODEL_REQUEST_LOCKS: dict[str, asyncio.Lock] = {}
_CHAT_MODEL_NEXT_AVAILABLE_AT: dict[str, float] = {}


def _get_chat_model_min_interval_seconds(model_id: Optional[str]) -> float:
    if not model_id:
        return 0.0

    limits = DEFAULT_CHAT_MODEL_MIN_INTERVAL_SECONDS.copy()
    raw_limits = os.environ.get('CHAT_MODEL_MIN_INTERVAL_SECONDS')
    if raw_limits:
        try:
            parsed_limits = json.loads(raw_limits)
            if isinstance(parsed_limits, dict):
                limits.update(parsed_limits)
        except Exception as e:
            log.warning('Invalid CHAT_MODEL_MIN_INTERVAL_SECONDS ignored: %s', e)

    try:
        return max(0.0, float(limits.get(model_id, 0) or 0))
    except (TypeError, ValueError):
        return 0.0


async def _throttle_chat_model_request(
    model_id: Optional[str],
    *,
    now_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], Awaitable[Any]] = asyncio.sleep,
) -> None:
    min_interval = _get_chat_model_min_interval_seconds(model_id)
    if min_interval <= 0:
        return

    lock = _CHAT_MODEL_REQUEST_LOCKS.setdefault(model_id, asyncio.Lock())
    async with lock:
        now = now_fn()
        next_available_at = _CHAT_MODEL_NEXT_AVAILABLE_AT.get(model_id, now)
        wait_seconds = max(0.0, next_available_at - now)

        if wait_seconds > 0:
            log.info('Throttling chat model request: model=%s wait=%.2fs', model_id, wait_seconds)
            await sleep_fn(wait_seconds)
            now = now_fn()

        _CHAT_MODEL_NEXT_AVAILABLE_AT[model_id] = max(now, next_available_at) + min_interval


def _get_chat_model_rate_limit_retry_attempts() -> int:
    raw_attempts = os.environ.get('CHAT_MODEL_RATE_LIMIT_RETRY_ATTEMPTS', '1')
    try:
        return max(0, int(raw_attempts))
    except (TypeError, ValueError):
        return 1


def _is_chat_model_rate_limit_error(error: Exception) -> bool:
    message = str(error)
    return (
        'RateLimitError' in message
        or 'Too many requests' in message
        or 'ModelArts.81101' in message
        or 'TooManyRequests' in message
    )


async def _generate_openai_chat_completion_with_throttle(
    *,
    request: Request,
    form_data: dict,
    user: Any,
    bypass_system_prompt: bool,
    now_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], Awaitable[Any]] = asyncio.sleep,
):
    retry_attempts = _get_chat_model_rate_limit_retry_attempts()
    attempts = retry_attempts + 1
    last_error: Optional[Exception] = None

    for attempt_index in range(attempts):
        await _throttle_chat_model_request(form_data.get('model'), now_fn=now_fn, sleep_fn=sleep_fn)
        try:
            return await generate_openai_chat_completion(
                request=request,
                form_data=form_data,
                user=user,
                bypass_system_prompt=bypass_system_prompt,
            )
        except Exception as e:
            last_error = e
            if attempt_index >= retry_attempts or not _is_chat_model_rate_limit_error(e):
                raise
            log.warning(
                'Retrying chat model request after rate limit: model=%s attempt=%s/%s error=%s',
                form_data.get('model'),
                attempt_index + 1,
                retry_attempts,
                e,
            )

    if last_error:
        raise last_error
    raise RuntimeError('OpenAI chat completion failed without an exception')


def _format_direct_stream_event(data):
    if isinstance(data, dict):
        chunk = f'data: {json.dumps(data)}\n\n'
        return chunk, bool(data.get('done'))

    if isinstance(data, str):
        chunk = f'{data}\n\n' if 'data:' in data else f'data: {data}\n\n'
        should_stop = '[DONE]' in data
        return chunk, should_stop

    return None, False


def _build_stream_metadata_events(
    chat_id: Optional[str] = None,
    selected_model_id: Optional[str] = None,
) -> list[str]:
    events: list[str] = []

    if chat_id:
        events.append(f'data: {json.dumps({"chat_id": chat_id})}\n\n')

    if selected_model_id:
        events.append(f'data: {json.dumps({"selected_model_id": selected_model_id})}\n\n')

    return events


def _wrap_streaming_response_with_metadata(
    response: Any,
    *,
    chat_id: Optional[str] = None,
    selected_model_id: Optional[str] = None,
):
    if not isinstance(response, StreamingResponse):
        return response

    if not (chat_id or selected_model_id):
        return response

    content_type = response.headers.get('content-type', '')
    if 'text/event-stream' not in content_type and 'application/x-ndjson' not in content_type:
        return response

    async def stream_wrapper():
        for chunk in _build_stream_metadata_events(chat_id, selected_model_id):
            yield chunk

        async for chunk in response.body_iterator:
            yield chunk

    headers = dict(response.headers)
    headers.pop('content-length', None)

    return StreamingResponse(
        stream_wrapper(),
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
        background=response.background,
    )


# When the question has been asked, let silence not be the
# answer. But if the answer must wait, let it come honest.
async def generate_direct_chat_completion(
    request: Request,
    form_data: dict,
    user: Any,
    models: dict,
):
    log.info('generate_direct_chat_completion')

    metadata = form_data.pop('metadata', {})

    user_id = metadata.get('user_id')
    session_id = metadata.get('session_id')
    request_id = str(uuid.uuid4())  # Generate a unique request ID

    event_caller = await get_event_call(metadata)

    channel = f'{user_id}:{session_id}:{request_id}'
    logging.info(f'WebSocket channel: {channel}')
    chat_id = metadata.get('chat_id')
    selected_model_id = metadata.get('selected_model_id')

    if form_data.get('stream'):
        q = asyncio.Queue()

        async def message_listener(sid, data):
            """
            Handle received socket messages and push them into the queue.
            """
            await q.put(data)

        # Register the listener
        sio.on(channel, message_listener)

        # Start processing chat completion in background
        res = await event_caller(
            {
                'type': 'request:chat:completion',
                'data': {
                    'form_data': form_data,
                    'model': models[form_data['model']],
                    'channel': channel,
                    'session_id': session_id,
                },
            }
        )

        log.info(f'res: {res}')

        if res.get('status', False):
            # Define a generator to stream responses
            async def event_generator():
                nonlocal q
                try:
                    for chunk in _build_stream_metadata_events(chat_id, selected_model_id):
                        yield chunk

                    while True:
                        data = await q.get()  # Wait for new messages
                        chunk, should_stop = _format_direct_stream_event(data)
                        if chunk:
                            yield chunk
                        if should_stop:
                            break
                except Exception as e:
                    log.debug(f'Error in event generator: {e}')
                    pass

            # Define a background task to run the event generator
            async def background():
                try:
                    del sio.handlers['/'][channel]
                except Exception as e:
                    pass

            # Return the streaming response
            return StreamingResponse(event_generator(), media_type='text/event-stream', background=background)
        else:
            raise Exception(str(res))
    else:
        res = await event_caller(
            {
                'type': 'request:chat:completion',
                'data': {
                    'form_data': form_data,
                    'model': models[form_data['model']],
                    'channel': channel,
                    'session_id': session_id,
                },
            }
        )

        if 'error' in res and res['error']:
            raise Exception(res['error'])

        if chat_id and 'chat_id' not in res:
            res['chat_id'] = chat_id
        if selected_model_id and 'selected_model_id' not in res:
            res['selected_model_id'] = selected_model_id

        return res


async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user: Any,
    bypass_filter: bool = False,
    bypass_system_prompt: bool = False,
):
    log.debug(f'generate_chat_completion: {form_data}')
    if BYPASS_MODEL_ACCESS_CONTROL:
        bypass_filter = True

    # Propagate bypass_filter via request.state so that downstream route
    # handlers (openai/ollama) can read it without exposing it as a query param.
    request.state.bypass_filter = bypass_filter

    if hasattr(request.state, 'metadata'):
        if 'metadata' not in form_data:
            form_data['metadata'] = request.state.metadata
        else:
            form_data['metadata'] = {
                **form_data['metadata'],
                **request.state.metadata,
            }

    if getattr(request.state, 'direct', False) and hasattr(request.state, 'model'):
        models = {
            request.state.model['id']: request.state.model,
        }
        log.debug(f'direct connection to model: {models}')
    else:
        models = request.app.state.MODELS

    model_id = form_data['model']
    if model_id not in models:
        raise Exception('Model not found')

    model = models[model_id]

    if getattr(request.state, 'direct', False):
        return await generate_direct_chat_completion(request, form_data, user=user, models=models)
    else:
        # Check if user has access to the model
        if not bypass_filter and user.role == 'user':
            try:
                await check_model_access(user, model)
            except Exception as e:
                raise e

        # Arena model — sub-model was already resolved by process_chat_payload.
        # Inject selected_model_id into the response for the frontend.
        metadata = form_data.get('metadata', {})
        selected_model_id = metadata.pop('selected_model_id', None)
        # Also clear from request.state.metadata to prevent the merge at
        # lines 177-179 from re-adding it on the recursive call.
        if hasattr(request.state, 'metadata'):
            request.state.metadata.pop('selected_model_id', None)

        # Fallback: if generate_chat_completion is called with an arena model
        # from a path that did NOT go through process_chat_payload (e.g.,
        # background tasks for title/follow-up/tags generation), resolve now.
        if not selected_model_id and model.get('owned_by') == 'arena':
            model_ids = model.get('info', {}).get('meta', {}).get('model_ids')
            filter_mode = model.get('info', {}).get('meta', {}).get('filter_mode')
            if model_ids and filter_mode == 'exclude':
                model_ids = [
                    available_model['id']
                    for available_model in list(request.app.state.MODELS.values())
                    if available_model.get('owned_by') != 'arena' and available_model['id'] not in model_ids
                ]

            if isinstance(model_ids, list) and model_ids:
                selected_model_id = random.choice(model_ids)
            else:
                model_ids = [
                    available_model['id']
                    for available_model in list(request.app.state.MODELS.values())
                    if available_model.get('owned_by') != 'arena'
                ]
                selected_model_id = random.choice(model_ids)

            form_data['model'] = selected_model_id

        if selected_model_id and form_data.get('stream') != True:
            response = await generate_chat_completion(
                request,
                form_data,
                user,
                bypass_filter=True,
                bypass_system_prompt=bypass_system_prompt,
            )
            return {
                **response,
                'selected_model_id': selected_model_id,
                **({'chat_id': metadata['chat_id']} if metadata.get('chat_id') else {}),
            }

        if model.get('pipe'):
            # Below does not require bypass_filter because this is the only route the uses this function and it is already bypassing the filter
            response = await generate_function_chat_completion(request, form_data, user=user, models=models)
            return _wrap_streaming_response_with_metadata(
                response,
                chat_id=metadata.get('chat_id'),
                selected_model_id=selected_model_id,
            )
        if model.get('owned_by') == 'ollama':
            # Using /ollama/api/chat endpoint
            form_data = convert_payload_openai_to_ollama(form_data)
            response = await generate_ollama_chat_completion(
                request=request,
                form_data=form_data,
                user=user,
                bypass_system_prompt=bypass_system_prompt,
            )
            if form_data.get('stream'):
                response.headers['content-type'] = 'text/event-stream'
                response = StreamingResponse(
                    convert_streaming_response_ollama_to_openai(response),
                    headers=dict(response.headers),
                    background=response.background,
                )
                return _wrap_streaming_response_with_metadata(
                    response,
                    chat_id=metadata.get('chat_id'),
                    selected_model_id=selected_model_id,
                )
            else:
                response = convert_response_ollama_to_openai(response)
                if metadata.get('chat_id'):
                    response['chat_id'] = metadata['chat_id']
                if selected_model_id:
                    response['selected_model_id'] = selected_model_id
                return response
        else:
            response = await _generate_openai_chat_completion_with_throttle(
                request=request,
                form_data=form_data,
                user=user,
                bypass_system_prompt=bypass_system_prompt,
            )
            return _wrap_streaming_response_with_metadata(
                response,
                chat_id=metadata.get('chat_id'),
                selected_model_id=selected_model_id,
            )


chat_completion = generate_chat_completion


async def chat_completed(request: Request, form_data: dict, user: Any):
    if not request.app.state.MODELS:
        await get_all_models(request, user=user)

    if getattr(request.state, 'direct', False) and hasattr(request.state, 'model'):
        models = {
            request.state.model['id']: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    data = form_data

    if not data.get('id'):
        raise Exception('Missing message id')

    model_id = data['model']
    if model_id not in models:
        raise Exception('Model not found')

    model = models[model_id]

    try:
        data = await process_pipeline_outlet_filter(request, data, user, models)
    except HTTPException:
        raise
    except Exception as e:
        log.debug(f'Legacy chat_completed pipeline outlet filter error: {e}')

    if not data.get('id'):
        raise Exception('Missing message id')

    metadata = {
        'chat_id': data['chat_id'],
        'message_id': data['id'],
        'filter_ids': data.get('filter_ids', []),
        'session_id': data['session_id'],
        'user_id': user.id,
    }

    extra_params = {
        '__event_emitter__': await get_event_emitter(metadata),
        '__event_call__': await get_event_call(metadata),
        '__user__': user.model_dump() if isinstance(user, UserModel) else {},
        '__metadata__': metadata,
        '__request__': request,
        '__model__': model,
    }

    try:
        filter_ids = await get_sorted_filter_ids(request, model, metadata.get('filter_ids', []))
        filter_functions = await Functions.get_functions_by_ids(filter_ids)

        result, _ = await process_filter_functions(
            request=request,
            filter_functions=filter_functions,
            filter_type='outlet',
            form_data=data,
            extra_params=extra_params,
        )
        return result
    except Exception as e:
        log.debug(f'Legacy chat_completed function outlet filter error: {e}')
        return data
