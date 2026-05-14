from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.models.product_type import ProductType
from app.models.system_param import SystemParam
from app.schemas.product_type import ProductTypeResponse, SystemParamResponse, SystemParamUpdate

router = APIRouter(prefix="/product-types", tags=["product-types"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[ProductTypeResponse], summary="Listar tipos de recebíveis")
def list_product_types(
    current_user: CurrentUser,
    db: DbDep,
) -> list[ProductTypeResponse]:
    """
    Lista os tipos de recebíveis ativos e seus spreads.
    Essencial para o motor de precificação e simulador no frontend.
    """
    types = db.query(ProductType).filter(ProductType.is_active == True).order_by(ProductType.name).all()  # noqa: E712
    return [ProductTypeResponse.model_validate(t) for t in types]


@router.get("/params", response_model=list[SystemParamResponse], summary="Listar parâmetros do sistema")
def list_params(
    current_user: CurrentUser,
    db: DbDep,
) -> list[SystemParamResponse]:
    params = db.query(SystemParam).order_by(SystemParam.key).all()
    return [SystemParamResponse.model_validate(p) for p in params]


@router.patch("/params/{key}", response_model=SystemParamResponse, summary="Atualizar parâmetro")
def update_param(
    current_user: CurrentUser,
    db: DbDep,
    key: str,
    payload: SystemParamUpdate,
) -> SystemParamResponse:
    update_result = db.execute(sa_update(SystemParam).where(SystemParam.key == key).values(value=payload.value))
    if update_result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parâmetro '{key}' não encontrado.")
    db.commit()
    param = db.query(SystemParam).filter(SystemParam.key == key).first()
    return SystemParamResponse.model_validate(param)
