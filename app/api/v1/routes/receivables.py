import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories import receivable_repository
from app.repositories.company_repository import get_by_id as get_company
from app.repositories.receivable_repository import list_available
from app.schemas.company import CompanyResponse
from app.schemas.receivable import ReceivableResponse, ReceivableUploadResponse
from app.services import receivable_service

router = APIRouter(prefix="/receivables", tags=["receivables"])

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/upload",
    response_model=ReceivableUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de NF-e XML",
    description="Processa um XML de NF-e, persiste os recebíveis e registra o lote de upload.",
)
async def upload_nfe(
    file: UploadFile,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    product_type_id: uuid.UUID | None = None,
    currency_code: str = "BRL",
) -> ReceivableUploadResponse:
    if file.content_type not in ("application/xml", "text/xml"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo deve ser um XML (application/xml ou text/xml)",
        )

    xml_bytes = await file.read()

    if len(xml_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo excede o limite de 5 MB",
        )

    result = receivable_service.ingest_xml(
        db=db,
        user_id=current_user.id,
        filename=file.filename or "upload.xml",
        xml_bytes=xml_bytes,
        product_type_id=product_type_id,
        currency_code=currency_code,
    )

    return ReceivableUploadResponse(
        upload_id=result.upload_id,
        total=result.total,
        imported=result.imported,
        skipped=result.skipped,
        items=[
            {
                "invoice_key": item.invoice_key,
                "installment_number": item.installment_number,
                "success": item.success,
                "error": item.error,
                "receivable_id": item.receivable_id,
            }
            for item in result.items
        ],
    )


@router.get(
    "",
    response_model=list[ReceivableResponse],
    summary="Listar recebíveis disponíveis",
)
def list_receivables(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    assignor_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[ReceivableResponse]:
    from app.models.company import Company
    from app.models.product_type import ProductType

    receivables, _ = list_available(db=db, assignor_id=assignor_id, page=page, page_size=page_size)

    result = []
    for r in receivables:
        assignor = db.query(Company).filter(Company.id == r.assignor_id).first()
        drawee = db.query(Company).filter(Company.id == r.drawee_id).first()
        product_type = db.query(ProductType).filter(ProductType.id == r.product_type_id).first()
        result.append(ReceivableResponse(
            id=r.id,
            assignor=CompanyResponse.model_validate(assignor),
            drawee=CompanyResponse.model_validate(drawee),
            product_type=product_type,
            invoice_key=r.invoice_key,
            invoice_number=r.invoice_number,
            series=r.series,
            issued_at=r.issued_at,
            installment_number=r.installment_number,
            products_value=r.products_value,
            discount_value=r.discount_value,
            freight_value=r.freight_value,
            other_value=r.other_value,
            face_value=r.face_value,
            currency_code=r.currency_code,
            due_date=r.due_date,
            status=r.status,
            created_at=r.created_at,
        ))
    return result
