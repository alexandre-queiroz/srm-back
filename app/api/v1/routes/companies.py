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
    social_reason: str | None = Query(None),
    social_reason_op: str | None = Query(
        None, description="Operador: startswith, endswith, equal, different, contains (padrão)"
    ),
    fantasy_name: str | None = Query(None),
    fantasy_name_op: str | None = Query(
        None, description="Operador: startswith, endswith, equal, different, contains (padrão)"
    ),
    cnpj: str | None = Query(None),
    cnpj_op: str | None = Query(
        None, description="Operador: startswith, endswith, equal, different, contains (padrão)"
    ),
    limit: int = Query(100, le=500),
) -> list[CompanyResponse]:
    rows = company_repository.list_companies(
        db,
        social_reason=social_reason,
        social_reason_op=social_reason_op,
        fantasy_name=fantasy_name,
        fantasy_name_op=fantasy_name_op,
        cnpj=cnpj,
        cnpj_op=cnpj_op,
        limit=limit,
    )
    return [
        CompanyResponse.model_validate(c).model_copy(update={"available_receivables_count": count}) for c, count in rows
    ]


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
