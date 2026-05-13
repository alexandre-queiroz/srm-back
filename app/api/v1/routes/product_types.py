from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.models.product_type import ProductType
from app.schemas.product_type import ProductTypeResponse

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
