import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import AppSchema


class SettlementReportItem(AppSchema):
    transaction_id: uuid.UUID
    batch_id: uuid.UUID
    liquidated_at: datetime

    assignor_name: str
    assignor_cnpj: str
    drawee_name: str
    drawee_cnpj: str

    invoice_key: str
    installment_number: str

    instrument_currency: str
    face_value: Decimal
    present_value: Decimal
    settlement_currency: str
    exchange_rate_used: Decimal | None

    term_days: int
    spread_used: Decimal
    base_rate_used: Decimal


class SettlementReportParams(AppSchema):
    start_date: datetime | None = None
    end_date: datetime | None = None
    assignor_id: uuid.UUID | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)


class SettlementSummary(AppSchema):
    total_count: int
    total_face_value_brl: Decimal
    total_present_value_brl: Decimal
    average_spread: Decimal


class SettlementReportResponse(AppSchema):
    items: list[SettlementReportItem]
    summary: SettlementSummary
    page: int
    page_size: int
