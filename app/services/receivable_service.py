import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product_type import ProductType
from app.models.receivable import Receivable
from app.models.xml_upload import XmlUpload
from app.repositories import company_repository, receivable_repository, xml_upload_repository
from app.services import storage_service, xml_parser_service
from app.services.xml_parser_service import XMLParseError


@dataclass
class UploadItem:
    invoice_key: str
    installment_number: str
    success: bool
    error: str | None = None
    receivable_id: uuid.UUID | None = None


@dataclass
class UploadResult:
    upload_id: uuid.UUID
    total: int
    imported: int
    skipped: int
    items: list[UploadItem]


def _default_product_type(db: Session) -> ProductType:
    pt = db.query(ProductType).filter(ProductType.is_active == True).first()  # noqa: E712
    if pt is None:
        raise ValueError("Nenhum product_type ativo encontrado. Execute o seed.")
    return pt


def ingest_xml(
    db: Session,
    user_id: uuid.UUID,
    filename: str,
    xml_bytes: bytes,
    product_type_id: uuid.UUID | None = None,
    currency_code: str = "BRL",
) -> UploadResult:
    upload = XmlUpload(
        user_id=user_id,
        filename=filename,
        status="processed",
    )
    xml_upload_repository.create(db, upload)

    # Try to upload XML to R2 regardless of parse outcome
    try:
        storage_key = f"nfe/{upload.id}/{filename}"
        storage_url = storage_service.upload_xml(storage_key, xml_bytes)
        upload.xml_storage_url = storage_url
    except Exception:
        upload.xml_storage_url = None

    # Attempt parse
    try:
        installments = xml_parser_service.parse(xml_bytes)
    except XMLParseError as e:
        upload.status = "failed"
        upload.receivables_created = 0
        xml_upload_repository.update(db, upload)
        db.commit()
        return UploadResult(
            upload_id=upload.id,
            total=0,
            imported=0,
            skipped=0,
            items=[UploadItem(invoice_key="", installment_number="", success=False, error=str(e))],
        )

    if product_type_id is None:
        pt = _default_product_type(db)
        product_type_id = pt.id

    items: list[UploadItem] = []
    imported = 0

    for inst in installments:
        try:
            assignor = company_repository.upsert(db, cnpj=inst.assignor_cnpj, name=inst.assignor_name)
            drawee = company_repository.upsert(db, cnpj=inst.drawee_cnpj, name=inst.drawee_name)

            existing = receivable_repository.get_by_invoice_installment(
                db, inst.invoice_key, inst.installment_number
            )
            if existing:
                items.append(
                    UploadItem(
                        invoice_key=inst.invoice_key,
                        installment_number=inst.installment_number,
                        success=False,
                        error="Duplicata já existe no sistema",
                        receivable_id=existing.id,
                    )
                )
                continue

            receivable = Receivable(
                xml_upload_id=upload.id,
                assignor_id=assignor.id,
                drawee_id=drawee.id,
                product_type_id=product_type_id,
                invoice_key=inst.invoice_key,
                invoice_number=inst.invoice_number,
                series=inst.series,
                issued_at=inst.issued_at,
                installment_number=inst.installment_number,
                due_date=inst.due_date,
                face_value=inst.face_value,
                products_value=inst.products_value,
                discount_value=inst.discount_value,
                freight_value=inst.freight_value,
                other_value=inst.other_value,
                currency_code=currency_code,
                xml_storage_url=upload.xml_storage_url,
                status="available",
            )
            receivable_repository.create(db, receivable)
            imported += 1
            items.append(
                UploadItem(
                    invoice_key=inst.invoice_key,
                    installment_number=inst.installment_number,
                    success=True,
                    receivable_id=receivable.id,
                )
            )

        except IntegrityError as e:
            db.rollback()
            # Re-open the upload record after rollback
            upload = xml_upload_repository.get_by_id(db, upload.id)
            items.append(
                UploadItem(
                    invoice_key=inst.invoice_key,
                    installment_number=inst.installment_number,
                    success=False,
                    error=f"Violação de integridade: {e.orig}",
                )
            )
        except Exception as e:
            items.append(
                UploadItem(
                    invoice_key=inst.invoice_key,
                    installment_number=inst.installment_number,
                    success=False,
                    error=str(e),
                )
            )

    upload.receivables_created = imported
    if imported == 0 and len(installments) > 0:
        upload.status = "failed"
    xml_upload_repository.update(db, upload)
    db.commit()

    skipped = len(installments) - imported
    return UploadResult(
        upload_id=upload.id,
        total=len(installments),
        imported=imported,
        skipped=skipped,
        items=items,
    )
