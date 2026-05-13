import uuid

from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories._filters import multi_col_str_filter


def get_by_cnpj(db: Session, cnpj: str) -> Company | None:
    return db.query(Company).filter(Company.cnpj == cnpj).first()


def get_by_id(db: Session, company_id: uuid.UUID) -> Company | None:
    return db.query(Company).filter(Company.id == company_id).first()


def list_companies(
    db: Session,
    query: str | None = None,
    query_op: str | None = None,
    limit: int = 100,
) -> list[Company]:
    q = db.query(Company)
    if query:
        q = q.filter(multi_col_str_filter([Company.name, Company.cnpj], query, query_op))
    return q.order_by(Company.name).limit(limit).all()


def upsert(db: Session, cnpj: str, name: str) -> Company:
    company = get_by_cnpj(db, cnpj)
    if company:
        if company.name != name:
            company.name = name
        return company
    company = Company(cnpj=cnpj, name=name)
    db.add(company)
    db.flush()
    return company
