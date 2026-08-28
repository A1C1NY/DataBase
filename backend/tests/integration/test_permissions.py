"""Current-user refresh and fixed-role permission matrix coverage."""

import pytest
from fastapi import HTTPException

from app.api.dependencies import get_current_user, require_roles
from app.core.security import create_access_token
from app.models.account import User


class _UserSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def get(self, model: object, identity: int) -> User | None:
        return self.user


def _user(role: str, *, active: bool = True) -> User:
    return User(
        id=7,
        username=f"user-{role}",
        password_hash="argon-hash",
        role=role,
        is_active=active,
    )


def test_old_token_is_rejected_after_user_is_disabled() -> None:
    token = create_access_token(user_id=7, role="passenger")

    with pytest.raises(HTTPException) as raised:
        get_current_user(_UserSession(_user("passenger", active=False)), token)  # type: ignore[arg-type]

    assert raised.value.status_code == 401


def test_database_role_replaces_stale_token_role() -> None:
    token = create_access_token(user_id=7, role="passenger")

    user = get_current_user(_UserSession(_user("admin")), token)  # type: ignore[arg-type]

    assert user.role == "admin"


@pytest.mark.parametrize(
    "role,allowed",
    [("passenger", False), ("analyst", True), ("admin", True)],
)
def test_analyst_permission_matrix(role: str, allowed: bool) -> None:
    dependency = require_roles("analyst", "admin")
    if allowed:
        assert dependency(_user(role)).role == role
    else:
        with pytest.raises(HTTPException) as raised:
            dependency(_user(role))
        assert raised.value.status_code == 403


@pytest.mark.parametrize(
    "role,allowed",
    [("passenger", False), ("analyst", False), ("admin", True)],
)
def test_admin_permission_matrix(role: str, allowed: bool) -> None:
    dependency = require_roles("admin")
    if allowed:
        assert dependency(_user(role)).role == role
    else:
        with pytest.raises(HTTPException) as raised:
            dependency(_user(role))
        assert raised.value.status_code == 403
