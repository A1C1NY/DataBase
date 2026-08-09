"""Registration, login, and current-user endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, SessionDep
from app.core.security import create_access_token, hash_password, verify_password
from app.models.account import User
from app.schemas.auth import RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest, session: SessionDep) -> User:
    existing = session.scalar(select(User).where(User.username == body.username))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "USERNAME_EXISTS", "message": "用户名已存在"},
        )

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role="passenger",
        is_active=True,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "USERNAME_EXISTS", "message": "用户名已存在"},
        ) from exc
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    session: SessionDep,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    user = session.scalar(select(User).where(User.username == form.username.strip()))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "用户名或密码错误"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"code": "USER_INACTIVE", "message": "用户已停用"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user_id=user.id, role=user.role)
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: CurrentUser) -> User:
    return user
