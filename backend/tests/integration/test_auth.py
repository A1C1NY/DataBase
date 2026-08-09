"""Authentication contract coverage without a live database."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.routes.auth import login, register
from app.core.security import decode_access_token, verify_password
from app.models.account import User
from app.schemas.auth import RegisterRequest, UserResponse


class _AuthSession:
    def __init__(self, scalar_result: User | None = None) -> None:
        self.scalar_result = scalar_result
        self.added: User | None = None
        self.commits = 0

    def scalar(self, statement: object) -> User | None:
        return self.scalar_result

    def add(self, user: User) -> None:
        self.added = user

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None

    def refresh(self, user: User) -> None:
        user.id = 41


def test_register_hashes_password_and_never_exposes_hash() -> None:
    session = _AuthSession()

    user = register(
        RegisterRequest(username="  passenger41  ", password="secret-pass-41"),
        session,  # type: ignore[arg-type]
    )

    assert user.username == "passenger41"
    assert user.role == "passenger"
    assert user.password_hash != "secret-pass-41"
    assert verify_password("secret-pass-41", user.password_hash)
    assert "password" not in UserResponse.model_validate(user).model_dump()
    assert session.commits == 1


def test_duplicate_username_returns_409() -> None:
    session = _AuthSession(User(id=1, username="existing", password_hash="hash"))

    with pytest.raises(HTTPException) as raised:
        register(
            RegisterRequest(username="existing", password="secret-pass-41"),
            session,  # type: ignore[arg-type]
        )

    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "USERNAME_EXISTS"


def test_login_returns_token_with_required_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.security import hash_password

    user = User(
        id=9,
        username="passenger9",
        password_hash=hash_password("secret-pass-9"),
        role="passenger",
        is_active=True,
    )
    form: Any = SimpleNamespace(username="passenger9", password="secret-pass-9")

    response = login(_AuthSession(user), form)  # type: ignore[arg-type]
    payload = decode_access_token(response.access_token)

    assert payload["sub"] == "9"
    assert payload["role"] == "passenger"
    assert "exp" in payload


def test_inactive_user_cannot_login() -> None:
    from app.core.security import hash_password

    user = User(
        id=10,
        username="inactive",
        password_hash=hash_password("secret-pass-10"),
        role="passenger",
        is_active=False,
    )
    form: Any = SimpleNamespace(username="inactive", password="secret-pass-10")

    with pytest.raises(HTTPException) as raised:
        login(_AuthSession(user), form)  # type: ignore[arg-type]

    assert raised.value.status_code == 401
    assert raised.value.detail["code"] == "USER_INACTIVE"
