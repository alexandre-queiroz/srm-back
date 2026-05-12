import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from app.schemas.base import AppSchema


class GroupBy(StrEnum):
    assignor = "assignor"
    drawee = "drawee"
    none = "none"


class LiquidationFilters(AppSchema):
    date_from: date
    date_to: date
    assignor_id: uuid.UUID | None = None
    currency_code: str | None = None
    group_by: GroupBy = GroupBy.none
    page: int = 1
    page_size: int = 50


class LiquidationItem(AppSchema):
    transaction_id: uuid.UUID
    batch_id: uuid.UUID
    assignor_name: str
    drawee_name: str
    invoice_key: str
    installment_number: str
    product_type_name: str
    face_value: Decimal
    present_value: Decimal
    term_days: int
    spread_used: Decimal
    base_rate_used: Decimal
    instrument_currency: str
    settlement_currency: str
    exchange_rate_used: Decimal | None
    liquidated_at: datetime


class LiquidationGroup(AppSchema):
    group_label: str
    total_face_value: Decimal
    total_present_value: Decimal
    total_transactions: int
    items: list[LiquidationItem]


class LiquidationReportResponse(AppSchema):
    date_from: date
    date_to: date
    group_by: GroupBy
    total_face_value: Decimal
    total_present_value: Decimal
    total_transactions: int
    groups: list[LiquidationGroup]
