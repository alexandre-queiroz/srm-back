from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.services import auth_service

bearer = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        user_id = auth_service.decode_token_from_credentials(credentials.credentials)
        return auth_service.get_user_from_token(db, user_id)
    except (JWTError, auth_service.InvalidCredentialsError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


CurrentUser = Annotated[User, Depends(get_current_user)]
