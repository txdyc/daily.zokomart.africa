"""Trip capacity ledger (PRD §8.4). reserve()/release() lock the trip row
(SELECT ... FOR UPDATE on MySQL; harmless no-op on SQLite) so concurrent CS
confirmations cannot overbook. Callers commit."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logistics.models import Trip


class CapacityError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def remaining_load(trip: Trip) -> float:
    return round(trip.total_load_kg - trip.used_load_kg - trip.manual_load_kg, 2)


def remaining_volume(trip: Trip) -> float:
    return round(trip.total_volume_m3 - trip.used_volume_m3 - trip.manual_volume_m3, 2)


def reserve(db: Session, trip_id: int, weight_kg: float, volume_m3: float) -> Trip:
    trip = db.execute(
        select(Trip).where(Trip.id == trip_id).with_for_update()
    ).scalar_one()
    short = []
    if remaining_load(trip) < weight_kg:
        short.append(f"load short by {round(weight_kg - remaining_load(trip), 2)} kg")
    if remaining_volume(trip) < volume_m3:
        short.append(f"volume short by {round(volume_m3 - remaining_volume(trip), 2)} m³")
    if short:
        raise CapacityError("Insufficient capacity: " + ", ".join(short))
    trip.used_load_kg = round(trip.used_load_kg + weight_kg, 2)
    trip.used_volume_m3 = round(trip.used_volume_m3 + volume_m3, 2)
    return trip


def release(db: Session, trip_id: int, weight_kg: float, volume_m3: float) -> Trip:
    trip = db.execute(
        select(Trip).where(Trip.id == trip_id).with_for_update()
    ).scalar_one()
    trip.used_load_kg = max(0.0, round(trip.used_load_kg - weight_kg, 2))
    trip.used_volume_m3 = max(0.0, round(trip.used_volume_m3 - volume_m3, 2))
    return trip
