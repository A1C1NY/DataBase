"""Current-user stop and line favorite endpoints."""

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, SessionDep
from app.models.account import FavoriteLine, FavoriteStop
from app.models.transit import BusLine, BusStop
from app.schemas.auth import (
    FavoriteLineItem,
    FavoriteLineListResponse,
    FavoriteStopItem,
    FavoriteStopListResponse,
)
from app.schemas.transit import LineItem, StopItem

router = APIRouter(prefix="/me", tags=["favorites"])


def _not_found(object_name: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "NOT_FOUND", "message": f"{object_name}不存在"},
    )


@router.put("/favorite-stops/{stop_id}", status_code=204)
def add_favorite_stop(
    stop_id: int, session: SessionDep, user: CurrentUser
) -> Response:
    stop = session.get(BusStop, stop_id)
    if stop is None or not stop.is_active:
        raise _not_found("站点")
    if session.get(FavoriteStop, (user.id, stop_id)) is None:
        session.add(FavoriteStop(user_id=user.id, stop_id=stop_id))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if session.get(FavoriteStop, (user.id, stop_id)) is None:
                raise
    return Response(status_code=204)


@router.delete("/favorite-stops/{stop_id}", status_code=204)
def remove_favorite_stop(
    stop_id: int, session: SessionDep, user: CurrentUser
) -> Response:
    session.execute(
        delete(FavoriteStop).where(
            FavoriteStop.user_id == user.id,
            FavoriteStop.stop_id == stop_id,
        )
    )
    session.commit()
    return Response(status_code=204)


@router.get("/favorite-stops", response_model=FavoriteStopListResponse)
def list_favorite_stops(
    session: SessionDep,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> FavoriteStopListResponse:
    filters = (
        FavoriteStop.user_id == user.id,
        BusStop.is_active.is_(True),
    )
    total = session.scalar(
        select(func.count())
        .select_from(FavoriteStop)
        .join(BusStop, BusStop.id == FavoriteStop.stop_id)
        .where(*filters)
    ) or 0
    rows = session.execute(
        select(FavoriteStop, BusStop)
        .join(BusStop, BusStop.id == FavoriteStop.stop_id)
        .where(*filters)
        .order_by(FavoriteStop.created_at.desc(), FavoriteStop.stop_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return FavoriteStopListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[
            FavoriteStopItem(
                created_at=favorite.created_at,
                stop=StopItem.model_validate(stop),
            )
            for favorite, stop in rows
        ],
    )


@router.put("/favorite-lines/{line_id}", status_code=204)
def add_favorite_line(
    line_id: int, session: SessionDep, user: CurrentUser
) -> Response:
    line = session.get(BusLine, line_id)
    if line is None or not line.is_active:
        raise _not_found("线路")
    if session.get(FavoriteLine, (user.id, line_id)) is None:
        session.add(FavoriteLine(user_id=user.id, line_id=line_id))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if session.get(FavoriteLine, (user.id, line_id)) is None:
                raise
    return Response(status_code=204)


@router.delete("/favorite-lines/{line_id}", status_code=204)
def remove_favorite_line(
    line_id: int, session: SessionDep, user: CurrentUser
) -> Response:
    session.execute(
        delete(FavoriteLine).where(
            FavoriteLine.user_id == user.id,
            FavoriteLine.line_id == line_id,
        )
    )
    session.commit()
    return Response(status_code=204)


@router.get("/favorite-lines", response_model=FavoriteLineListResponse)
def list_favorite_lines(
    session: SessionDep,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> FavoriteLineListResponse:
    filters = (
        FavoriteLine.user_id == user.id,
        BusLine.is_active.is_(True),
    )
    total = session.scalar(
        select(func.count())
        .select_from(FavoriteLine)
        .join(BusLine, BusLine.id == FavoriteLine.line_id)
        .where(*filters)
    ) or 0
    rows = session.execute(
        select(FavoriteLine, BusLine)
        .join(BusLine, BusLine.id == FavoriteLine.line_id)
        .where(*filters)
        .order_by(FavoriteLine.created_at.desc(), FavoriteLine.line_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return FavoriteLineListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[
            FavoriteLineItem(
                created_at=favorite.created_at,
                line=LineItem.model_validate(line),
            )
            for favorite, line in rows
        ],
    )
