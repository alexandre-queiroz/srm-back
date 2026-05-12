import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import AppSchema


class ProductTypeResponse(AppSchema):
    id: uuid.UUID
    name: str
    spread: Decimal
    is_active: bool
    updated_at: datetime


class ProductTypeUpdate(AppSchema):
    spread: Decimal


class SystemParamResponse(AppSchema):
    key: str
    value: Decimal
    description: str | None


class SystemParamUpdate(AppSchema):
    value: Decimal
