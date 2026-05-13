import uuid
from datetime import datetime
from typing import Any

from app.schemas.base import AppSchema, FinancialDecimal
from app.schemas.company import CompanyResponse


class BatchCreate(AppSchema):
    assignor_id: uuid.UUID
    receivable_ids: list[uuid.UUID]


class BatchConfirm(AppSchema):
    expected_version: int


class BatchPreviewItem(AppSchema):
    receivable_id: uuid.UUID
    invoice_key: str
    installment_number: str
    drawee: CompanyResponse
    face_value: FinancialDecimal
    currency_code: str
    term_days: int
    present_value: FinancialDecimal


class BatchPreviewResponse(AppSchema):
    batch_id: uuid.UUID
    assignor: CompanyResponse
    total_receivables: int
    total_face_value: FinancialDecimal
    total_present_value: FinancialDecimal
    items: list[BatchPreviewItem]


class BatchResponse(AppSchema):
    id: uuid.UUID
    assignor: CompanyResponse
    status: str
    version: int
    rejection_reasons: dict[str, Any] | None
    total_receivables: int
    created_at: datetime
    updated_at: datetime


class BatchDetailResponse(BatchResponse):
    items: list[BatchPreviewItem]
