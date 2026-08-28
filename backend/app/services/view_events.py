"""Stop detail retrieval and its associated view event write."""

from sqlalchemy.orm import Session

from app.models.account import LineViewEvent, StopViewEvent, User
from app.models.transit import BusLine, BusStop
from app.schemas.events import StopViewActorRole, StopViewEntryPoint
from app.services.transit import TransitService


class StopViewEventService:
    """Keep a successful detail read and its single event write together."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def open_stop_detail(
        self,
        stop_id: int,
        *,
        entry_point: StopViewEntryPoint,
        user: User | None,
    ) -> BusStop | None:
        stop = TransitService(self.session).get_stop(stop_id)
        if stop is None:
            return None

        event = StopViewEvent(
            stop_id=stop.id,
            entry_point=entry_point.value,
            user_id=user.id if user is not None else None,
            actor_role=(
                StopViewActorRole(user.role).value
                if user is not None
                else StopViewActorRole.ANONYMOUS.value
            ),
        )
        self.session.add(event)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return stop


class LineViewEventService:
    """Keep a successful line detail read and its event write together."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def open_line_detail(
        self,
        line_id: int,
        *,
        entry_point: str = "direct",
        user: User | None,
    ) -> BusLine | None:
        line = TransitService(self.session).get_line(line_id)
        if line is None:
            return None
        event = LineViewEvent(
            line_id=line.id,
            entry_point=entry_point,
            user_id=user.id if user is not None else None,
            actor_role=user.role if user is not None else "anonymous",
        )
        self.session.add(event)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return line
