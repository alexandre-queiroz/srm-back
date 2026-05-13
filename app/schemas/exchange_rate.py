import uuid
from datetime import datetime

from app.schemas.base import AppSchema, FinancialDecimal


class ExchangeRateResponse(AppSchema):
    id: uuid.UUID
    from_currency: str
    to_currency: str
    rate: FinancialDecimal
    source: str
    is_stale: bool
    collected_at: datetime
