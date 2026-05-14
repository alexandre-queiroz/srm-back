from pydantic import EmailStr

from app.schemas.base import AppSchema


class LoginRequest(AppSchema):
    email: EmailStr
    password: str


class TokenResponse(AppSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserMeResponse(AppSchema):
    id: str
    name: str
    email: str
