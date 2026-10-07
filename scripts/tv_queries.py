"""Build validated GDELT TV clip-gallery URLs."""
from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlencode

TV_CLIPGALLERY_ENDPOINT = "https://api.gdeltproject.org/api/v2/tv/tv"
_STATION = re.compile(r"\bstation\s*:\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
_MALFORMED_STATION = re.compile(r"\bstation\s*:\s*(?=$|[\s()])", re.IGNORECASE)
_ARCHIVE_ID = re.compile(r"\b[A-Z0-9]+_\d{8}_\d{6}_[A-Z0-9_]+\b", re.IGNORECASE)
_QUERY_TOKEN = re.compile(r'"[^"]*"|\'[^\']*\'|\S+')


def build_tv_query(
    query: str,
    station: str | None,
    station_ids: Iterable[str],
) -> str:
    """Require an official station ID and a positive term, preserving user syntax."""
    query = query.strip()
    if not query:
        raise ValueError("Enter a positive search term.")
    if _ARCHIVE_ID.search(query):
        raise ValueError("Archive item IDs are not GDELT TV search terms.")
    if _MALFORMED_STATION.search(query):
        raise ValueError("The station filter is incomplete.")

    known_stations = {item.strip().upper() for item in station_ids if item.strip()}
    query_stations = [match.upper() for match in _STATION.findall(query)]
    selected_station = (station or "").strip().upper()

    if selected_station and selected_station not in known_stations:
        raise ValueError("Choose a station ID listed by GDELT station details.")
    if any(item not in known_stations for item in query_stations):
        raise ValueError("The query contains a station ID not listed by GDELT station details.")
    if selected_station and query_stations and selected_station not in query_stations:
        raise ValueError("The selected station conflicts with the station filter in the query.")
    if not query_stations:
        if not selected_station:
            raise ValueError("Enter a station ID listed by GDELT station details.")
        query = f"{query} station:{selected_station}"

    search_terms = _STATION.sub(" ", query)
    positive_terms = [
        token for token in _QUERY_TOKEN.findall(search_terms)
        if token.upper() not in {"OR", "AND"}
        and not token.startswith("-")
        and token.strip("\"'()")
    ]
    if not positive_terms:
        raise ValueError("Add at least one positive keyword or phrase.")
    return query


def build_tv_clipgallery_url(
    query: str,
    station: str | None,
    station_ids: Iterable[str],
) -> str:
    validated_query = build_tv_query(query, station, station_ids)
    return (
        f"{TV_CLIPGALLERY_ENDPOINT}?"
        + urlencode({"format": "html", "mode": "clipgallery", "query": validated_query})
    )
