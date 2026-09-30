from pydantic import BaseModel, EmailStr, Field

from app.models.user import Role


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.FARMER
    state: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    role: Role
    state: str | None
    preferred_language: str

    model_config = {"from_attributes": True}
