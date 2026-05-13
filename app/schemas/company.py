import uuid
from datetime import datetime

from pydantic import field_validator

from app.schemas.base import AppSchema


class CompanyCreate(AppSchema):
    cnpj: str
    social_reason: str
    fantasy_name: str | None = None

    @field_validator("cnpj")
    @classmethod
    def cnpj_must_be_numeric_14_digits(cls, v: str) -> str:
        digits = v.replace(".", "").replace("/", "").replace("-", "")
        if not digits.isdigit() or len(digits) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos numéricos")
        return digits


class CompanyResponse(AppSchema):
    id: uuid.UUID
    cnpj: str
    social_reason: str
    fantasy_name: str | None
    created_at: datetime
    available_receivables_count: int = 0
