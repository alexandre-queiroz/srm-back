from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_token, verify_password
from app.models.user import User
from app.repositories import user_repository


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


def authenticate(db: Session, email: str, password: str) -> str:
    user = user_repository.get_by_email(db, email)

    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    if not user.is_active:
        raise InactiveUserError

    return create_access_token(subject=str(user.id))


def decode_token_from_credentials(token: str) -> str:
    return decode_token(token)


def get_user_from_token(db: Session, user_id: str) -> User:
    import uuid
    user = user_repository.get_by_id(db, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise InvalidCredentialsError
    return user
