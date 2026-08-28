"""Administrative protection and logical status coverage."""

from unittest.mock import Mock

import pytest

from app.models.account import User
from app.models.transit import BusStop
from app.schemas.admin import AdminUserUpdate
from app.services.admin import AdminError, AdminService


def _admin(user_id: int = 1) -> User:
    return User(
        id=user_id,
        username=f"admin-{user_id}",
        password_hash="hash",
        role="admin",
        is_active=True,
    )


@pytest.mark.parametrize(
    "body,code",
    [
        (AdminUserUpdate(is_active=False), "CANNOT_DISABLE_SELF"),
        (AdminUserUpdate(role="analyst"), "CANNOT_DEMOTE_SELF"),
    ],
)
def test_admin_cannot_disable_or_demote_self(body: AdminUserUpdate, code: str) -> None:
    session = Mock()
    session.get.return_value = _admin()

    with pytest.raises(AdminError) as raised:
        AdminService(session).update_user(1, body, _admin())

    assert raised.value.code == code
    session.commit.assert_not_called()


def test_last_active_admin_cannot_be_disabled() -> None:
    session = Mock()
    session.get.return_value = _admin(2)
    session.scalar.return_value = 1

    with pytest.raises(AdminError) as raised:
        AdminService(session).update_user(
            2, AdminUserUpdate(is_active=False), _admin(1)
        )

    assert raised.value.code == "LAST_ACTIVE_ADMIN"
    session.commit.assert_not_called()


def test_transit_status_change_is_logical_only() -> None:
    stop = Mock(spec=BusStop)
    stop.id = 37
    stop.is_active = True
    session = Mock()
    session.get.return_value = stop

    result = AdminService(session).set_active(BusStop, 37, False)

    assert result.is_active is False
    session.commit.assert_called_once()
    session.delete.assert_not_called()


def test_ingestion_page_uses_offset_and_limit() -> None:
    session = Mock()
    session.scalar.return_value = 42
    scalars = session.scalars.return_value
    scalars.__iter__ = Mock(return_value=iter([]))

    items, total = AdminService(session).list_runs(page=3, page_size=10)

    assert items == []
    assert total == 42
    statement = session.scalars.call_args.args[0]
    assert statement._offset_clause.value == 20
    assert statement._limit_clause.value == 10
