"""
Keyset pagination helpers.

Cursors encode the sort-key of the last returned row so the next page query
can use a WHERE clause instead of OFFSET.  This keeps pagination O(K) for any
depth — OFFSET degrades to O(M) as pages increase.

Cursor format: base64(JSON([sort_key_value, id_as_str]))
The exact fields depend on each query's ORDER BY clause.
"""

import base64
import json
import uuid
from datetime import date, datetime
from typing import Any


def encode_cursor(*values: Any) -> str:
    payload = []
    for v in values:
        if isinstance(v, datetime | date):
            payload.append(v.isoformat())
        elif isinstance(v, uuid.UUID):
            payload.append(str(v))
        else:
            payload.append(v)
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> list[Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        return json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Cursor inválido: {cursor!r}") from exc
