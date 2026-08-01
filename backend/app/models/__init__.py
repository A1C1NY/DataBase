"""Import every mapped class so Base.metadata contains the complete schema."""

from app.models.account import FavoriteStop, QueryLog, User
from app.models.ingestion import ArrivalInfo, DispatchCar, DispatchSchedule, IngestionRun
from app.models.transit import Line, LineRoute, Stop

__all__ = [
    "ArrivalInfo",
    "DispatchCar",
    "DispatchSchedule",
    "FavoriteStop",
    "IngestionRun",
    "Line",
    "LineRoute",
    "QueryLog",
    "Stop",
    "User",
]
