"""Admin writes and analyst/admin ingestion audit reads."""

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import AdminUser, AnalystOrAdmin, SessionDep
from app.models.transit import BusLine, BusStop
from app.schemas.admin import (
    ActiveStatusResponse,
    ActiveStatusUpdate,
    AdminUserCreate,
    AdminUserUpdate,
    IngestionRunDetail,
    IngestionRunPage,
    UserPage,
)
from app.schemas.auth import UserResponse
from app.services.admin import AdminError, AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


def _raise(exc: AdminError) -> None:
    raise HTTPException(
        exc.status_code, detail={"code": exc.code, "message": str(exc)}
    ) from exc


@router.get("/users", response_model=UserPage, summary="管理员分页查看用户")
def list_users(
    session: SessionDep,
    _admin: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> UserPage:
    items, total = AdminService(session).list_users(page, page_size)
    return UserPage(page=page, page_size=page_size, total=total, items=items)


@router.post(
    "/users", response_model=UserResponse, status_code=201, summary="管理员创建用户"
)
def create_user(body: AdminUserCreate, session: SessionDep, _admin: AdminUser):
    try:
        return AdminService(session).create_user(body)
    except AdminError as exc:
        _raise(exc)


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="管理员修改用户角色或启用状态",
)
def update_user(
    user_id: int, body: AdminUserUpdate, session: SessionDep, admin: AdminUser
):
    try:
        return AdminService(session).update_user(user_id, body, admin)
    except AdminError as exc:
        _raise(exc)


def _set_status(model, object_id: int, body: ActiveStatusUpdate, session: SessionDep):
    try:
        item = AdminService(session).set_active(model, object_id, body.is_active)
        return ActiveStatusResponse(id=item.id, is_active=item.is_active)
    except AdminError as exc:
        _raise(exc)


@router.patch(
    "/stops/{stop_id}/status",
    response_model=ActiveStatusResponse,
    summary="管理员逻辑启停站点",
)
def set_stop_status(
    stop_id: int, body: ActiveStatusUpdate, session: SessionDep, _admin: AdminUser
) -> ActiveStatusResponse:
    return _set_status(BusStop, stop_id, body, session)


@router.patch(
    "/lines/{line_id}/status",
    response_model=ActiveStatusResponse,
    summary="管理员逻辑启停线路",
)
def set_line_status(
    line_id: int, body: ActiveStatusUpdate, session: SessionDep, _admin: AdminUser
) -> ActiveStatusResponse:
    return _set_status(BusLine, line_id, body, session)


@router.get(
    "/ingestion-runs",
    response_model=IngestionRunPage,
    summary="分析师或管理员分页查看导入运行",
)
def list_ingestion_runs(
    session: SessionDep,
    _user: AnalystOrAdmin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> IngestionRunPage:
    items, total = AdminService(session).list_runs(page, page_size)
    return IngestionRunPage(page=page, page_size=page_size, total=total, items=items)


@router.get(
    "/ingestion-runs/{run_id}",
    response_model=IngestionRunDetail,
    summary="分析师或管理员查看导入错误详情",
)
def get_ingestion_run(run_id: int, session: SessionDep, _user: AnalystOrAdmin):
    try:
        return AdminService(session).get_run(run_id)
    except AdminError as exc:
        _raise(exc)
