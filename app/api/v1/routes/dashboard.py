from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories import dashboard_repository
from app.schemas.dashboard import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=DashboardResponse)
def get_dashboard(current_user: CurrentUser, db: DbDep) -> DashboardResponse:
    data = dashboard_repository.get_dashboard(db)
    return DashboardResponse(**data)
