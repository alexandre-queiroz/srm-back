import uuid
from datetime import datetime

from app.schemas.base import AppSchema


class CurrencyCreate(AppSchema):
    code: str
    name: str
    symbol: str
    is_base: bool = False


class CurrencyUpdate(AppSchema):
    name: str | None = None
    symbol: str | None = None
    is_base: bool | None = None
    is_active: bool | None = None


class CurrencyResponse(AppSchema):
    id: uuid.UUID
    code: str
    name: str
    symbol: str
    is_base: bool
    is_active: bool
    created_at: datetime
