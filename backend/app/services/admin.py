"""Small transactional service for administrative operations."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.account import User
from app.models.ingestion import IngestionRun
from app.models.transit import BusLine, BusStop
from app.schemas.admin import AdminUserCreate, AdminUserUpdate


class AdminError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class AdminService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_users(self, page: int, page_size: int) -> tuple[list[User], int]:
        total = self.session.scalar(select(func.count()).select_from(User)) or 0
        items = list(
            self.session.scalars(
                select(User)
                .order_by(User.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def create_user(self, body: AdminUserCreate) -> User:
        if self.session.scalar(select(User).where(User.username == body.username)):
            raise AdminError("USERNAME_EXISTS", "用户名已存在", 409)
        user = User(
            username=body.username,
            password_hash=hash_password(body.password),
            role=body.role,
            is_active=body.is_active,
        )
        self.session.add(user)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AdminError("USERNAME_EXISTS", "用户名已存在", 409) from exc
        self.session.refresh(user)
        return user

    def update_user(self, user_id: int, body: AdminUserUpdate, actor: User) -> User:
        user = self.session.get(User, user_id)
        if user is None:
            raise AdminError("NOT_FOUND", "用户不存在", 404)
        if user.id == actor.id and body.is_active is False:
            raise AdminError("CANNOT_DISABLE_SELF", "管理员不能停用自己", 409)
        if user.id == actor.id and body.role is not None and body.role != "admin":
            raise AdminError("CANNOT_DEMOTE_SELF", "管理员不能降级自己", 409)
        removes_active_admin = (
            user.role == "admin"
            and user.is_active
            and (
                body.is_active is False
                or (body.role is not None and body.role != "admin")
            )
        )
        if removes_active_admin:
            count = (
                self.session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.role == "admin", User.is_active.is_(True))
                )
                or 0
            )
            if count <= 1:
                raise AdminError(
                    "LAST_ACTIVE_ADMIN", "不能停用或降级最后一个有效管理员", 409
                )
        if body.role is not None:
            user.role = body.role
        if body.is_active is not None:
            user.is_active = body.is_active
        self.session.commit()
        self.session.refresh(user)
        return user

    def set_active(
        self, model: type[BusStop] | type[BusLine], object_id: int, is_active: bool
    ) -> BusStop | BusLine:
        item = self.session.get(model, object_id)
        if item is None:
            raise AdminError("NOT_FOUND", "站点或线路不存在", 404)
        item.is_active = is_active
        self.session.commit()
        self.session.refresh(item)
        return item

    def list_runs(self, page: int, page_size: int) -> tuple[list[IngestionRun], int]:
        total = self.session.scalar(select(func.count()).select_from(IngestionRun)) or 0
        items = list(
            self.session.scalars(
                select(IngestionRun)
                .order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def get_run(self, run_id: int) -> IngestionRun:
        run = self.session.get(IngestionRun, run_id)
        if run is None:
            raise AdminError("NOT_FOUND", "导入运行不存在", 404)
        return run
