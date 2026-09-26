from datetime import datetime
from zoneinfo import ZoneInfo


TORONTO_TIME_ZONE = ZoneInfo("America/Toronto")
DATE_REQUIRED_MESSAGE = "Please choose a date after today."
LOCATION_REQUIRED_MESSAGE = "Den currently supports events within the Greater Toronto Area."

_MUNICIPALITIES = (
    ("toronto", "Toronto"),
    ("ajax", "Ajax"),
    ("brock", "Brock"),
    ("clarington", "Clarington"),
    ("oshawa", "Oshawa"),
    ("pickering", "Pickering"),
    ("scugog", "Scugog"),
    ("uxbridge", "Uxbridge"),
    ("whitby", "Whitby"),
    ("burlington", "Burlington"),
    ("halton-hills", "Halton Hills"),
    ("milton", "Milton"),
    ("oakville", "Oakville"),
    ("brampton", "Brampton"),
    ("caledon", "Caledon"),
    ("mississauga", "Mississauga"),
    ("aurora", "Aurora"),
    ("east-gwillimbury", "East Gwillimbury"),
    ("georgina", "Georgina"),
    ("king", "King"),
    ("markham", "Markham"),
    ("newmarket", "Newmarket"),
    ("richmond-hill", "Richmond Hill"),
    ("vaughan", "Vaughan"),
    ("whitchurch-stouffville", "Whitchurch-Stouffville"),
)
_TORONTO_DISTRICTS = (
    ("north-york", "North York"),
    ("scarborough", "Scarborough"),
    ("etobicoke", "Etobicoke"),
    ("east-york", "East York"),
    ("york-toronto", "York (Toronto)"),
)

EVENT_LOCATIONS = tuple(
    {"id": location_id, "label": label, "canonical_id": location_id, "canonical_label": label, "aliases": []}
    for location_id, label in _MUNICIPALITIES
) + tuple(
    {"id": location_id, "label": label, "canonical_id": "toronto", "canonical_label": "Toronto", "aliases": [label]}
    for location_id, label in _TORONTO_DISTRICTS
)

_LOCATION_BY_ID = {location["id"]: location for location in EVENT_LOCATIONS}


def _normalized(value):
    return " ".join(value.casefold().split())


_LOCATION_BY_NAME = {
    _normalized(name): location
    for location in EVENT_LOCATIONS
    for name in (location["label"], *location["aliases"])
}


def toronto_today():
    return datetime.now(TORONTO_TIME_ZONE).date()


def tomorrow_iso_date():
    from datetime import timedelta

    return (toronto_today() + timedelta(days=1)).isoformat()


def resolve_event_location(value):
    """Return the selected location, accepting its ID or known friendly name."""
    if not isinstance(value, str):
        return None
    return _LOCATION_BY_ID.get(value) or _LOCATION_BY_NAME.get(_normalized(value))


def normalize_event_location(value):
    location = resolve_event_location(value)
    return location["label"] if location else value


def canonical_event_location(value):
    location = resolve_event_location(value)
    return location["canonical_label"] if location else value


def event_location_display(value):
    return normalize_event_location(value)