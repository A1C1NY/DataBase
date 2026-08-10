"""Authentication and role dependencies shared by protected routes."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.account import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)
SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Return the active database user identified by the bearer token."""

    credentials_error = HTTPException(
        status_code=401,
        detail={"code": "INVALID_CREDENTIALS", "message": "无效或已过期的访问令牌"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise TypeError("Token 缺少用户 ID")
        user_id = int(subject)
    except (ValueError, TypeError):
        raise credentials_error

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_current_user(
    session: SessionDep,
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
) -> User | None:
    """Resolve an optional bearer token without requiring authentication."""

    if token is None:
        return None
    return get_current_user(session, token)


OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    """Build a dependency that authorizes against the current database role."""

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": "权限不足"},
            )
        return user

    return dependency


AnalystOrAdmin = Annotated[User, Depends(require_roles("analyst", "admin"))]
AdminUser = Annotated[User, Depends(require_roles("admin"))]
