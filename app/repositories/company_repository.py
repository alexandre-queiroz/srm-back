import uuid

from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories._filters import str_filter


def get_by_cnpj(db: Session, cnpj: str) -> Company | None:
    return db.query(Company).filter(Company.cnpj == cnpj).first()


def get_by_id(db: Session, company_id: uuid.UUID) -> Company | None:
    return db.query(Company).filter(Company.id == company_id).first()


def list_companies(
    db: Session,
    social_reason: str | None = None,
    social_reason_op: str | None = None,
    cnpj: str | None = None,
    cnpj_op: str | None = None,
    limit: int = 100,
) -> list[Company]:
    q = db.query(Company)
    if social_reason:
        q = q.filter(str_filter(Company.social_reason, social_reason, social_reason_op))
    if cnpj:
        q = q.filter(str_filter(Company.cnpj, cnpj, cnpj_op))
    return q.order_by(Company.social_reason).limit(limit).all()


def upsert(db: Session, cnpj: str, social_reason: str, fantasy_name: str | None = None) -> Company:
    company = get_by_cnpj(db, cnpj)
    if company:
        if company.social_reason != social_reason:
            company.social_reason = social_reason
        if fantasy_name and company.fantasy_name != fantasy_name:
            company.fantasy_name = fantasy_name
        return company
    company = Company(cnpj=cnpj, social_reason=social_reason, fantasy_name=fantasy_name)
    db.add(company)
    db.flush()
    return company
