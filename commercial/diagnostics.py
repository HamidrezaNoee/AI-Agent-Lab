"""Bounded, payload-free diagnostics; safe to export when business storage fails.

Never pass request bodies, exception messages, credentials or user content here.
Only predefined structural metadata survives serialization.
"""
from __future__ import annotations
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from logging.handlers import RotatingFileHandler
import json
import logging
import os
import re
import threading
import traceback

request_id = ContextVar('avan_request_id', default='')
_lock = threading.Lock()
_handler = None
_directory = None
_SAFE = re.compile(r'^[a-zA-Z0-9_./:{} -]{1,160}$')
_STRINGS = {'request_id', 'method', 'route', 'phase', 'error_type', 'outcome'}
_NUMBERS = {'status', 'upstream_status', 'duration_ms', 'bytes', 'count'}


def sanitize(value):
    result = {}
    for key in _STRINGS:
        item = value.get(key)
        if isinstance(item, str) and _SAFE.fullmatch(item):
            result[key] = item
    for key in _NUMBERS:
        item = value.get(key)
        if isinstance(item, (int, float)) and not isinstance(item, bool) and 0 <= item <= 10**12:
            result[key] = round(item, 3)
    return result


def directory():
    return Path(os.environ.get('AVAN_STATE_DIR', '/var/lib/avan')) / 'diagnostics'


def emit(phase, *, error=None, **metadata):
    """Best effort: observability must never break a business transaction."""
    global _handler, _directory
    try:
        row = sanitize(dict(metadata, phase=phase, request_id=request_id.get(),
                            **({'error_type': type(error).__name__} if error else {})))
        row['at'] = datetime.now(timezone.utc).isoformat()
        if error:
            row['stack'] = [f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}'
                            for frame in traceback.extract_tb(error.__traceback__)[-12:]
                            if _SAFE.fullmatch(f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}')]
        with _lock:
            target = directory()
            if _handler is None or target != _directory:
                if _handler:
                    _handler.close()
                target.mkdir(parents=True, exist_ok=True)
                _handler = RotatingFileHandler(target / 'runtime.jsonl', maxBytes=2_000_000,
                                               backupCount=4, encoding='utf-8')
                _directory = target
            _handler.emit(logging.LogRecord('avan.diagnostics', logging.INFO, '', 0,
                                           json.dumps(row, ensure_ascii=True), (), None))
    except Exception:
        pass


def export_runtime(limit=2000, selected_request_id=''):
    """Re-sanitize stored rows; never include arbitrary text from disk."""
    rows = []
    for suffix in ('.4', '.3', '.2', '.1', ''):
        try:
            with (directory() / ('runtime.jsonl' + suffix)).open(encoding='utf-8') as stream:
                for line in stream:
                    if len(line) > 16000:
                        continue
                    try:
                        original = json.loads(line)
                        row = sanitize(original)
                        stamp = original.get('at', '')
                        datetime.fromisoformat(stamp)
                        row['at'] = stamp
                        row['stack'] = [s for s in original.get('stack', [])[:12]
                                        if isinstance(s, str) and _SAFE.fullmatch(s)]
                        if not selected_request_id or row.get('request_id') == selected_request_id:
                            rows.append(row)
                            rows = rows[-max(1, min(limit, 2000)):]
                    except (ValueError, TypeError, AttributeError):
                        continue
        except OSError:
            continue
    return {'schema': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'includes_payloads': False, 'runtime': rows}


if __name__ == '__main__':
    print(json.dumps(export_runtime(), ensure_ascii=True, indent=2))
