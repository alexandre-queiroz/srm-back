import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories import company_repository
from app.schemas.company import CompanyResponse

router = APIRouter(prefix="/companies", tags=["companies"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[CompanyResponse], summary="Listar empresas (cedentes/sacados)")
def list_companies(
    current_user: CurrentUser,
    db: DbDep,
    q: str | None = Query(None, description="Busca por nome ou CNPJ"),
    limit: int = Query(100, le=100),
) -> list[CompanyResponse]:
    """
    Lista empresas cadastradas no sistema. Útil para popular filtros e selects no frontend.
    """
    companies = company_repository.list_companies(db, query=q, limit=limit)
    return [CompanyResponse.model_validate(c) for c in companies]


@router.get("/{company_id}", response_model=CompanyResponse, summary="Detalhes da empresa")
def get_company(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> CompanyResponse:
    company = company_repository.get_by_id(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return CompanyResponse.model_validate(company)
