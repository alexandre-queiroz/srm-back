import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import AppSchema
from app.schemas.company import CompanyResponse


class BatchCreate(AppSchema):
    assignor_id: uuid.UUID
    receivable_ids: list[uuid.UUID]


class BatchPreviewItem(AppSchema):
    receivable_id: uuid.UUID
    invoice_key: str
    installment_number: str
    drawee: CompanyResponse
    face_value: Decimal
    currency_code: str
    term_days: int
    present_value: Decimal


class BatchPreviewResponse(AppSchema):
    batch_id: uuid.UUID
    assignor: CompanyResponse
    total_receivables: int
    total_face_value: Decimal
    total_present_value: Decimal
    items: list[BatchPreviewItem]


class BatchResponse(AppSchema):
    id: uuid.UUID
    assignor: CompanyResponse
    status: str
    rejection_reasons: list[str] | None
    total_receivables: int
    created_at: datetime
    updated_at: datetime


class BatchDetailResponse(BatchResponse):
    items: list[BatchPreviewItem]
