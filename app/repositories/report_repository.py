from collections import defaultdict
from decimal import Decimal

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.schemas.report import (
    SettlementBatchItem,
    SettlementBatchReportResponse,
    SettlementBatchSummary,
    SettlementReportItem,
    SettlementSummary,
    SettlementTransactionItem,
)


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


def get_settlement_report_by_batch(
    db: Session,
    start_date=None,
    end_date=None,
    assignor_id=None,
    page: int = 1,
    page_size: int = 20,
) -> SettlementBatchReportResponse:
    """
    Returns approved batches with their liquidated transactions, hierarchically grouped.
    Uses two native SQL queries: one for paginated batch summaries, one for transactions.
    """

    # 1. Build dynamic filters on batches
    filters = ["b.status = 'approved'"]
    params: dict = {}

    if start_date:
        filters.append("b.updated_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        filters.append("b.updated_at <= :end_date")
        params["end_date"] = end_date
    if assignor_id:
        filters.append("b.assignor_id = :assignor_id")
        params["assignor_id"] = assignor_id

    where_clause = " AND ".join(filters)

    # 2. Count total matching batches (for pagination)
    count_sql = f"""
        SELECT COUNT(DISTINCT b.id) as total_batches
        FROM batches b
        WHERE {where_clause}
    """
    total_batches_row = db.execute(text(count_sql), params).mappings().first()
    total_batches: int = total_batches_row["total_batches"] if total_batches_row else 0
    total_pages = max(1, -(-total_batches // page_size))  # ceiling division

    if total_batches == 0:
        empty_summary = SettlementBatchSummary(
            total_batches=0,
            total_receivables=0,
            total_face_brl=Decimal("0"),
            total_present_brl=Decimal("0"),
            total_discount_brl=Decimal("0"),
            avg_rate_pct=Decimal("0"),
        )
        return SettlementBatchReportResponse(
            items=[],
            summary=empty_summary,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_batches=0,
        )

    # 3. Query paginated batch summaries
    batch_params = {**params, "limit": page_size, "offset": (page - 1) * page_size}
    batch_sql = f"""
        SELECT
            b.id as batch_id,
            COALESCE(ass.fantasy_name, ass.social_reason) as assignor_name,
            ass.cnpj as assignor_cnpj,
            b.updated_at as processed_at,
            COUNT(t.id) as total_receivables,
            COALESCE(SUM(
                CASE WHEN t.exchange_rate_used IS NOT NULL
                     THEN t.face_value * t.exchange_rate_used
                     ELSE t.face_value
                END
            ), 0) as total_face_brl,
            COALESCE(SUM(t.present_value), 0) as total_present_brl
        FROM batches b
        JOIN companies ass ON b.assignor_id = ass.id
        JOIN transactions t ON t.batch_id = b.id
        WHERE {where_clause}
        GROUP BY b.id, ass.fantasy_name, ass.social_reason, ass.cnpj, b.updated_at
        ORDER BY b.updated_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    batch_rows = db.execute(text(batch_sql), batch_params).mappings().all()
    batch_ids = [str(row["batch_id"]) for row in batch_rows]

    # 4. Query transactions for those batch IDs
    txn_sql = text("""
        SELECT
            t.id as transaction_id,
            t.batch_id,
            r.invoice_key,
            r.installment_number,
            dra.social_reason as drawee_name,
            dra.cnpj as drawee_cnpj,
            t.instrument_currency,
            t.face_value,
            CASE WHEN t.exchange_rate_used IS NOT NULL
                 THEN t.face_value * t.exchange_rate_used
                 ELSE t.face_value
            END as face_value_brl,
            t.present_value,
            t.exchange_rate_used,
            t.term_days,
            t.spread_used,
            t.base_rate_used,
            t.liquidated_at
        FROM transactions t
        JOIN receivables r ON t.receivable_id = r.id
        JOIN companies dra ON r.drawee_id = dra.id
        WHERE t.batch_id IN :batch_ids
        ORDER BY t.liquidated_at DESC
    """).bindparams(bindparam("batch_ids", expanding=True))

    txn_rows = db.execute(txn_sql, {"batch_ids": batch_ids}).mappings().all()

    # 5. Group transactions by batch_id in Python
    txn_by_batch: dict[str, list[SettlementTransactionItem]] = defaultdict(list)
    for row in txn_rows:
        txn_by_batch[str(row["batch_id"])].append(SettlementTransactionItem.model_validate(dict(row)))

    # 6. Build batch items
    items: list[SettlementBatchItem] = []
    for row in batch_rows:
        bid = str(row["batch_id"])
        total_face = Decimal(str(row["total_face_brl"]))
        total_present = Decimal(str(row["total_present_brl"]))
        total_discount = total_face - total_present
        avg_rate_pct = round((total_discount / total_face) * 100, 4) if total_face > 0 else Decimal("0")
        items.append(
            SettlementBatchItem(
                batch_id=row["batch_id"],
                assignor_name=row["assignor_name"],
                assignor_cnpj=row["assignor_cnpj"],
                processed_at=row["processed_at"],
                total_receivables=row["total_receivables"],
                total_face_brl=total_face,
                total_present_brl=total_present,
                total_discount_brl=total_discount,
                avg_rate_pct=avg_rate_pct,
                transactions=txn_by_batch.get(bid, []),
            )
        )

    # 7. Compute page-level summary
    page_face = sum(i.total_face_brl for i in items)
    page_present = sum(i.total_present_brl for i in items)
    page_discount = page_face - page_present
    page_avg = round((page_discount / page_face) * 100, 4) if page_face > 0 else Decimal("0")
    summary = SettlementBatchSummary(
        total_batches=total_batches,
        total_receivables=sum(i.total_receivables for i in items),
        total_face_brl=page_face,
        total_present_brl=page_present,
        total_discount_brl=page_discount,
        avg_rate_pct=page_avg,
    )

    return SettlementBatchReportResponse(
        items=items,
        summary=summary,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        total_batches=total_batches,
    )
