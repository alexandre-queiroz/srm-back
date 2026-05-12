import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories import batch_repository
from app.repositories.company_repository import get_by_id as get_company
from app.schemas.batch import (
    BatchCreate,
    BatchDetailResponse,
    BatchPreviewItem,
    BatchPreviewResponse,
    BatchResponse,
)
from app.schemas.company import CompanyResponse
from app.services import batch_service
from app.services.batch_service import BatchError

router = APIRouter(prefix="/batches", tags=["batches"])

DbDep = Annotated[Session, Depends(get_db)]


def _company_response(db: Session, company_id: uuid.UUID) -> CompanyResponse:
    c = get_company(db, company_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Empresa {company_id} não encontrada.")
    return CompanyResponse.model_validate(c)


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

    assignor = _company_response(db, batch.assignor_id)
    return BatchResponse(
        id=batch.id,
        assignor=assignor,
        status=batch.status,
        rejection_reasons=batch.rejection_reasons,
        total_receivables=len(batch.receivables),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


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

    assignor = _company_response(db, preview.assignor_id)

    items = []
    for item in preview.items:
        drawee = _company_response(db, item.drawee_id)
        items.append(BatchPreviewItem(
            receivable_id=item.receivable_id,
            invoice_key=item.invoice_key,
            installment_number=item.installment_number,
            drawee=drawee,
            face_value=item.face_value,
            currency_code=item.currency_code,
            term_days=item.term_days,
            present_value=item.present_value,
        ))

    return BatchPreviewResponse(
        batch_id=preview.batch_id,
        assignor=assignor,
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
    current_user: CurrentUser,
    db: DbDep,
) -> BatchResponse:
    try:
        batch = batch_service.confirm_batch(
            db=db,
            batch_id=batch_id,
            user_id=current_user.id,
        )
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    assignor = _company_response(db, batch.assignor_id)
    return BatchResponse(
        id=batch.id,
        assignor=assignor,
        status=batch.status,
        rejection_reasons=batch.rejection_reasons,
        total_receivables=len(batch.receivables),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


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
    batches, _ = batch_repository.list_by_assignor(
        db=db,
        assignor_id=assignor_id,
        page=page,
        page_size=page_size,
    )
    result = []
    for batch in batches:
        assignor = _company_response(db, batch.assignor_id)
        result.append(BatchResponse(
            id=batch.id,
            assignor=assignor,
            status=batch.status,
            rejection_reasons=batch.rejection_reasons,
            total_receivables=len(batch.receivables),
            created_at=batch.created_at,
            updated_at=batch.updated_at,
        ))
    return result


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
    from app.models.transaction import Transaction

    batch = batch_repository.get_by_id(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Lote {batch_id} não encontrado.")

    assignor = _company_response(db, batch.assignor_id)

    if batch.status == "approved":
        transactions = db.query(Transaction).filter(Transaction.batch_id == batch_id).all()
        txn_by_receivable = {t.receivable_id: t for t in transactions}
        items = []
        for r in batch.receivables:
            txn = txn_by_receivable.get(r.id)
            drawee = _company_response(db, r.drawee_id)
            items.append(BatchPreviewItem(
                receivable_id=r.id,
                invoice_key=r.invoice_key,
                installment_number=r.installment_number,
                drawee=drawee,
                face_value=r.face_value,
                currency_code=r.currency_code,
                term_days=txn.term_days if txn else 0,
                present_value=txn.present_value if txn else r.face_value,
            ))
    else:
        try:
            preview = batch_service.preview_batch(db=db, batch_id=batch_id)
        except BatchError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        items = []
        for item in preview.items:
            drawee = _company_response(db, item.drawee_id)
            items.append(BatchPreviewItem(
                receivable_id=item.receivable_id,
                invoice_key=item.invoice_key,
                installment_number=item.installment_number,
                drawee=drawee,
                face_value=item.face_value,
                currency_code=item.currency_code,
                term_days=item.term_days,
                present_value=item.present_value,
            ))

    return BatchDetailResponse(
        id=batch.id,
        assignor=assignor,
        status=batch.status,
        rejection_reasons=batch.rejection_reasons,
        total_receivables=len(items),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        items=items,
    )
