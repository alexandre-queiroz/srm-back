from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.models.batch import Batch
from app.models.company import Company
from app.models.receivable import Receivable
from app.models.transaction import Transaction


def _face_value_brl_expr():
    """SQLAlchemy case expression that converts face_value to BRL using exchange rate when present."""
    return case(
        (Transaction.exchange_rate_used.is_not(None), Transaction.face_value * Transaction.exchange_rate_used),
        else_=Transaction.face_value,
    )


def get_dashboard(db: Session) -> dict:
    now = datetime.now(tz=UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = now - timedelta(days=30)

    # --- KPIs ---
    # Total anticipated (present_value) this month
    kpi_row = (
        db.query(
            func.coalesce(func.sum(Transaction.present_value), Decimal("0")).label("total_present_brl"),
            func.coalesce(func.sum(_face_value_brl_expr()), Decimal("0")).label("total_face_brl"),
        )
        .filter(
            Transaction.liquidated_at >= month_start,
        )
        .one()
    )

    total_present_brl: Decimal = kpi_row.total_present_brl
    total_face_brl: Decimal = kpi_row.total_face_brl

    if total_face_brl > 0:
        average_rate_pct = (total_face_brl - total_present_brl) / total_face_brl * 100
    else:
        average_rate_pct = Decimal("0")

    total_available_receivables: int = (
        db.query(func.count(Receivable.id)).filter(Receivable.status == "available").scalar() or 0
    )

    total_approved_batches: int = (
        db.query(func.count(Batch.id))
        .filter(
            Batch.status == "approved",
            Batch.created_at >= month_start,
        )
        .scalar()
        or 0
    )

    kpis = {
        "total_anticipated_brl": total_present_brl,
        "total_available_receivables": total_available_receivables,
        "average_rate_pct": average_rate_pct,
        "total_approved_batches": total_approved_batches,
    }

    # --- Daily Volume (last 30 days) ---
    daily_rows = (
        db.query(
            func.date(Transaction.liquidated_at).label("day"),
            func.sum(Transaction.present_value).label("volume"),
        )
        .filter(
            Transaction.liquidated_at >= thirty_days_ago,
        )
        .group_by(
            func.date(Transaction.liquidated_at),
        )
        .order_by(
            func.date(Transaction.liquidated_at),
        )
        .all()
    )

    # Build a dict of existing data
    existing = {row.day: row.volume for row in daily_rows}

    # Fill missing days
    daily_volume = []
    for i in range(30):
        day = (thirty_days_ago + timedelta(days=i + 1)).date()
        volume = existing.get(day, Decimal("0"))
        daily_volume.append(
            {
                "date": day.strftime("%d/%m"),
                "volume_brl": volume,
            }
        )

    # --- Top Assignors (all-time top 5) ---
    top_rows = (
        db.query(
            Company.social_reason.label("assignor_name"),
            func.sum(Transaction.present_value).label("total_anticipated_brl"),
            func.count(func.distinct(Batch.id)).label("total_batches"),
        )
        .join(
            Batch,
            Transaction.batch_id == Batch.id,
        )
        .join(
            Company,
            Batch.assignor_id == Company.id,
        )
        .group_by(
            Company.id,
            Company.social_reason,
        )
        .order_by(
            func.sum(Transaction.present_value).desc(),
        )
        .limit(5)
        .all()
    )

    top_assignors = [
        {
            "assignor_name": row.assignor_name,
            "total_anticipated_brl": row.total_anticipated_brl,
            "total_batches": row.total_batches,
        }
        for row in top_rows
    ]

    # --- Recent Batches (last 8) ---
    batches = db.query(Batch).options(joinedload(Batch.assignor)).order_by(Batch.created_at.desc()).limit(8).all()

    recent_batches = []
    for batch in batches:
        totals = (
            db.query(
                func.coalesce(func.sum(_face_value_brl_expr()), Decimal("0")).label("face_brl"),
                func.coalesce(func.sum(Transaction.present_value), Decimal("0")).label("present_brl"),
            )
            .filter(Transaction.batch_id == batch.id)
            .one()
        )

        recent_batches.append(
            {
                "id": batch.id,
                "assignor_name": batch.assignor.social_reason,
                "status": batch.status,
                "total_face_value_brl": totals.face_brl,
                "total_present_value_brl": totals.present_brl,
                "created_at": batch.created_at,
            }
        )

    return {
        "kpis": kpis,
        "daily_volume": daily_volume,
        "top_assignors": top_assignors,
        "recent_batches": recent_batches,
    }
