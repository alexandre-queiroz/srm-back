import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories import batch_repository
from app.schemas.base import CursorPage
from app.schemas.batch import (
    BatchConfirm,
    BatchCreate,
    BatchDetailResponse,
    BatchPreviewItem,
    BatchPreviewResponse,
    BatchResponse,
)
from app.schemas.company import CompanyResponse
from app.services import batch_service
from app.services.batch_service import BatchError, ConcurrencyError, queue_batch

router = APIRouter(prefix="/batches", tags=["batches"])

DbDep = Annotated[Session, Depends(get_db)]


def _batch_response(batch) -> BatchResponse:
    return BatchResponse(
        id=batch.id,
        assignor=CompanyResponse.model_validate(batch.assignor),
        status=batch.status,
        version=batch.version,
        rejection_reasons=batch.rejection_reasons,
        total_receivables=len(batch.receivables),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


@router.post(
    "",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar lote de antecipação",
)
def create_batch(
    payload: BatchCreate,
    current_user: CurrentUser,
    db: DbDep,
) -> BatchResponse:
    try:
        batch = batch_service.create_batch(
            db=db,
            user_id=current_user.id,
            assignor_id=payload.assignor_id,
            receivable_ids=payload.receivable_ids,
        )
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Reload with eager data after commit so relationships are available
    batch = batch_repository.get_by_id(db, batch.id)
    return _batch_response(batch)


@router.get(
    "/{batch_id}/preview",
    response_model=BatchPreviewResponse,
    summary="Simulação de precificação do lote",
)
def preview_batch(
    batch_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> BatchPreviewResponse:
    try:
        preview = batch_service.preview_batch(db=db, batch_id=batch_id)
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    batch = batch_repository.get_by_id(db, batch_id)

    # Bulk-load all drawee companies in one query to avoid N+1
    from app.models.company import Company

    drawee_ids = list({item.drawee_id for item in preview.items})
    drawees = {c.id: c for c in db.query(Company).filter(Company.id.in_(drawee_ids)).all()}

    items = [
        BatchPreviewItem(
            receivable_id=item.receivable_id,
            invoice_key=item.invoice_key,
            installment_number=item.installment_number,
            drawee=CompanyResponse.model_validate(drawees[item.drawee_id]),
            face_value=item.face_value,
            currency_code=item.currency_code,
            term_days=item.term_days,
            present_value=item.present_value,
        )
        for item in preview.items
    ]

    return BatchPreviewResponse(
        batch_id=preview.batch_id,
        assignor=CompanyResponse.model_validate(batch.assignor),
        total_receivables=preview.total_receivables,
        total_face_value=preview.total_face_value,
        total_present_value=preview.total_present_value,
        items=items,
    )


@router.post(
    "/{batch_id}/confirm",
    response_model=BatchResponse,
    summary="Confirmar lote e gerar transações",
)
def confirm_batch(
    batch_id: uuid.UUID,
    payload: BatchConfirm,
    current_user: CurrentUser,
    db: DbDep,
) -> BatchResponse:
    try:
        batch = batch_service.confirm_batch(
            db=db,
            batch_id=batch_id,
            user_id=current_user.id,
            expected_version=payload.expected_version,
        )
    except ConcurrencyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    batch = batch_repository.get_by_id(db, batch.id)
    return _batch_response(batch)


@router.post(
    "/{batch_id}/queue",
    response_model=BatchResponse,
    summary="Enfileirar lote para processamento assíncrono pelo worker",
)
def queue_batch_endpoint(
    batch_id: uuid.UUID,
    payload: BatchConfirm,
    current_user: CurrentUser,
    db: DbDep,
) -> BatchResponse:
    try:
        batch = queue_batch(db=db, batch_id=batch_id, expected_version=payload.expected_version)
    except ConcurrencyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    batch = batch_repository.get_by_id(db, batch.id)
    return _batch_response(batch)


@router.get(
    "",
    response_model=list[BatchResponse],
    summary="Listar lotes",
)
def list_batches(
    current_user: CurrentUser,
    db: DbDep,
    assignor_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[BatchResponse]:
    # joinedload(Batch.assignor) already applied in the repository — zero N+1
    batches, _ = batch_repository.list_by_assignor(
        db=db,
        assignor_id=assignor_id,
        page=page,
        page_size=page_size,
    )
    return [_batch_response(b) for b in batches]


@router.get(
    "/cursor",
    response_model=CursorPage[BatchResponse],
    summary="Listar lotes com keyset pagination",
    description="Use `after` (next_cursor da página anterior). Keyset pagination: O(K) em qualquer profundidade.",
)
def list_batches_cursor(
    current_user: CurrentUser,
    db: DbDep,
    assignor_id: uuid.UUID | None = None,
    after: str | None = None,
    page_size: int = 20,
) -> CursorPage[BatchResponse]:
    batches, next_cursor = batch_repository.list_by_assignor_cursor(
        db=db,
        assignor_id=assignor_id,
        after=after,
        page_size=page_size,
    )
    return CursorPage(items=[_batch_response(b) for b in batches], next_cursor=next_cursor)


@router.get(
    "/{batch_id}",
    response_model=BatchDetailResponse,
    summary="Detalhe do lote com precificação",
)
def get_batch(
    batch_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> BatchDetailResponse:
    from app.models.company import Company
    from app.models.transaction import Transaction

    batch = batch_repository.get_by_id(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Lote {batch_id} não encontrado.")

    if batch.status == "approved":
        transactions = db.query(Transaction).filter(Transaction.batch_id == batch_id).all()
        txn_by_receivable = {t.receivable_id: t for t in transactions}

        # Bulk-load drawees in one query
        drawee_ids = list({r.drawee_id for r in batch.receivables})
        drawees = {c.id: c for c in db.query(Company).filter(Company.id.in_(drawee_ids)).all()}

        items = [
            BatchPreviewItem(
                receivable_id=r.id,
                invoice_key=r.invoice_key,
                installment_number=r.installment_number,
                drawee=CompanyResponse.model_validate(drawees[r.drawee_id]),
                face_value=r.face_value,
                currency_code=r.currency_code,
                term_days=txn_by_receivable[r.id].term_days if r.id in txn_by_receivable else 0,
                present_value=txn_by_receivable[r.id].present_value if r.id in txn_by_receivable else r.face_value,
            )
            for r in batch.receivables
        ]
    else:
        try:
            preview = batch_service.preview_batch(db=db, batch_id=batch_id)
        except BatchError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

        drawee_ids = list({item.drawee_id for item in preview.items})
        drawees = {c.id: c for c in db.query(Company).filter(Company.id.in_(drawee_ids)).all()}

        items = [
            BatchPreviewItem(
                receivable_id=item.receivable_id,
                invoice_key=item.invoice_key,
                installment_number=item.installment_number,
                drawee=CompanyResponse.model_validate(drawees[item.drawee_id]),
                face_value=item.face_value,
                currency_code=item.currency_code,
                term_days=item.term_days,
                present_value=item.present_value,
            )
            for item in preview.items
        ]

    return BatchDetailResponse(
        id=batch.id,
        assignor=CompanyResponse.model_validate(batch.assignor),
        status=batch.status,
        rejection_reasons=batch.rejection_reasons,
        total_receivables=len(items),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        items=items,
    )
