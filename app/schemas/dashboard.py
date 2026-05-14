import uuid
from datetime import datetime

from app.schemas.base import AppSchema, FinancialDecimal


class DashboardKpis(AppSchema):
    total_anticipated_brl: FinancialDecimal
    total_available_receivables: int
    average_rate_pct: FinancialDecimal
    total_approved_batches: int


class DailyVolume(AppSchema):
    date: str  # format "DD/MM"
    volume_brl: FinancialDecimal


class TopAssignor(AppSchema):
    assignor_name: str
    total_anticipated_brl: FinancialDecimal
    total_batches: int


class RecentBatch(AppSchema):
    id: uuid.UUID
    assignor_name: str
    status: str
    total_face_value_brl: FinancialDecimal
    total_present_value_brl: FinancialDecimal
    created_at: datetime


class DashboardResponse(AppSchema):
    kpis: DashboardKpis
    daily_volume: list[DailyVolume]
    top_assignors: list[TopAssignor]
    recent_batches: list[RecentBatch]
