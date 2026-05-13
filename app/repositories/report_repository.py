from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.report import SettlementReportItem, SettlementSummary


def get_settlement_report(
    db: Session,
    start_date=None,
    end_date=None,
    assignor_id=None,
    currency_code=None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[SettlementReportItem], SettlementSummary]:
    """
    Optimized native SQL query for the Settlement Statement.
    Joins transactions, batches, receivables and companies.
    """

    # 1. Build dynamic filters
    filters = ["1=1"]
    params = {"limit": page_size, "offset": (page - 1) * page_size}

    if start_date:
        filters.append("t.liquidated_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        filters.append("t.liquidated_at <= :end_date")
        params["end_date"] = end_date
    if assignor_id:
        filters.append("b.assignor_id = :assignor_id")
        params["assignor_id"] = assignor_id
    if currency_code:
        filters.append("t.instrument_currency = :currency_code")
        params["currency_code"] = currency_code

    where_clause = " AND ".join(filters)

    # 2. Main query for data
    query_sql = f"""
        SELECT 
            t.id as transaction_id,
            t.batch_id,
            t.liquidated_at,
            COALESCE(ass.fantasy_name, ass.social_reason) as assignor_name,
            ass.cnpj as assignor_cnpj,
            dra.social_reason as drawee_name,
            dra.cnpj as drawee_cnpj,
            r.invoice_key,
            r.installment_number,
            t.instrument_currency,
            t.face_value,
            t.present_value,
            t.settlement_currency,
            t.exchange_rate_used,
            t.term_days,
            t.spread_used,
            t.base_rate_used
        FROM transactions t
        JOIN batches b ON t.batch_id = b.id
        JOIN receivables r ON t.receivable_id = r.id
        JOIN companies ass ON b.assignor_id = ass.id
        JOIN companies dra ON r.drawee_id = dra.id
        WHERE {where_clause}
        ORDER BY t.liquidated_at DESC
        LIMIT :limit OFFSET :offset
    """

    # 3. Summary query for totals (analytical part)
    summary_sql = f"""
        SELECT 
            COUNT(*) as total_count,
            COALESCE(SUM(face_value), 0) as total_face,
            COALESCE(SUM(present_value), 0) as total_present,
            COALESCE(AVG(spread_used), 0) as avg_spread
        FROM transactions t
        JOIN batches b ON t.batch_id = b.id
        WHERE {where_clause}
    """

    data_result = db.execute(text(query_sql), params).mappings().all()
    summary_result = db.execute(text(summary_sql), params).mappings().first()

    items = [SettlementReportItem.model_validate(dict(row)) for row in data_result]

    summary = SettlementSummary(
        total_count=summary_result["total_count"],
        total_face_value_brl=summary_result["total_face"],
        total_present_value_brl=summary_result["total_present"],
        average_spread=summary_result["avg_spread"],
    )

    return items, summary
