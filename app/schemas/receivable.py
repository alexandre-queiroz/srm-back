import uuid
from datetime import date, datetime

from app.schemas.base import AppSchema, FinancialDecimal
from app.schemas.company import CompanyResponse
from app.schemas.product_type import ProductTypeResponse


class ReceivableResponse(AppSchema):
    id: uuid.UUID
    assignor: CompanyResponse
    drawee: CompanyResponse
    product_type: ProductTypeResponse

    invoice_key: str
    invoice_number: str
    series: str
    issued_at: date
    installment_number: str

    products_value: FinancialDecimal
    discount_value: FinancialDecimal
    freight_value: FinancialDecimal
    other_value: FinancialDecimal
    face_value: FinancialDecimal
    currency_code: str
    due_date: date

    status: str
    created_at: datetime


class ReceivableUploadItem(AppSchema):
    invoice_key: str
    installment_number: str
    success: bool
    error: str | None = None
    receivable_id: uuid.UUID | None = None


class ReceivableUploadResponse(AppSchema):
    upload_id: uuid.UUID
    total: int
    imported: int
    skipped: int
    items: list[ReceivableUploadItem]
