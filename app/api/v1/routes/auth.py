from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserMeResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    try:
        token = auth_service.authenticate(db, email=body.email, password=body.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except auth_service.InactiveUserError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserMeResponse)
def get_me(current_user: CurrentUser) -> UserMeResponse:
    return UserMeResponse(id=str(current_user.id), name=current_user.name, email=current_user.email)
