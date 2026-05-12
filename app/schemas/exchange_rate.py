import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import AppSchema


class ExchangeRateResponse(AppSchema):
    id: uuid.UUID
    from_currency: str
    to_currency: str
    rate: Decimal
    source: str
    is_stale: bool
    collected_at: datetime
