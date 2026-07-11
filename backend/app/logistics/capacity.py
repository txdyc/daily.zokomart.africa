from app.logistics.models import Trip


def remaining_load(trip: Trip) -> float:
    return round(trip.total_load_kg - trip.used_load_kg - trip.manual_load_kg, 2)


def remaining_volume(trip: Trip) -> float:
    return round(trip.total_volume_m3 - trip.used_volume_m3 - trip.manual_volume_m3, 2)
