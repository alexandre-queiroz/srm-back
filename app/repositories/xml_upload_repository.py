import uuid

from sqlalchemy.orm import Session

from app.models.xml_upload import XmlUpload


def create(db: Session, upload: XmlUpload) -> XmlUpload:
    db.add(upload)
    db.flush()
    return upload


def update(db: Session, upload: XmlUpload) -> XmlUpload:
    db.flush()
    return upload


def get_by_id(db: Session, upload_id: uuid.UUID) -> XmlUpload | None:
    return db.query(XmlUpload).filter(XmlUpload.id == upload_id).first()
