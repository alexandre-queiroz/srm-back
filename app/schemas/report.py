import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import AppSchema


class SettlementTransactionItem(AppSchema):
    transaction_id: uuid.UUID
    invoice_key: str
    installment_number: str
    drawee_name: str
    drawee_cnpj: str
    instrument_currency: str
    face_value: Decimal
    face_value_brl: Decimal
    present_value: Decimal
    exchange_rate_used: Decimal | None
    term_days: int
    spread_used: Decimal
    base_rate_used: Decimal
    liquidated_at: datetime


class SettlementBatchItem(AppSchema):
    batch_id: uuid.UUID
    assignor_name: str
    assignor_cnpj: str
    processed_at: datetime
    total_receivables: int
    total_face_brl: Decimal
    total_present_brl: Decimal
    total_discount_brl: Decimal
    avg_rate_pct: Decimal
    transactions: list[SettlementTransactionItem]


class SettlementBatchSummary(AppSchema):
    total_batches: int
    total_receivables: int
    total_face_brl: Decimal
    total_present_brl: Decimal
    total_discount_brl: Decimal
    avg_rate_pct: Decimal


class SettlementBatchReportResponse(AppSchema):
    items: list[SettlementBatchItem]
    summary: SettlementBatchSummary
    page: int
    page_size: int
    total_pages: int
    total_batches: int


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
