"""Request-local, revalidated process context for existing analytical endpoints."""
from contextvars import ContextVar
import re

_selected=ContextVar('avan_process_pack',default=None)
# Mutations/tasks carry their own pack and native assignment; do not infer it.
_PATH=re.compile(r'^/api/sources/[^/]+/(?:ask|questions|meetings(?:/[^/]+)?|agent/(?:status|history)|reports/actions(?:/ask)?|monitor(?:/[^/]+)?|voice/(?:speech|transcribe))$')

def analytical_path(path):return bool(_PATH.fullmatch(path))

def install(app):
    from fastapi.responses import JSONResponse
    @app.middleware('http')
    async def bind_process_context(request,call_next):
        value=request.headers.get('X-AVAN-Process-Pack') if analytical_path(request.url.path) else None
        if value and not re.fullmatch(r'[0-9a-f]{24}',value):
            return JSONResponse({'detail':'شناسه فرایند انتخاب‌شده معتبر نیست.'},status_code=422)
        token=_selected.set(value)
        try:return await call_next(request)
        finally:_selected.reset(token)

def scoped(scope):
    value=_selected.get()
    if not value:return scope
    from .secretary_catalog import get
    from .process_workspace import resolve
    from .processmaker_store import ProductionAccessDenied
    try:
        pack=get(scope['source_id'],value)
        adapter=resolve(pack,scope)
        if adapter.key!='meeting_v2':raise PermissionError('آداپتور تحلیلی این فرایند نصب نشده است.')
    except (PermissionError,ValueError) as exc:
        raise ProductionAccessDenied(str(exc)) from exc
    return {**scope,'process_pack_id':value,'meeting_process_uid':pack['meeting']['process_uid'],
            'action_process_uid':pack['action']['process_uid']}
