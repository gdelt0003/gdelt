#!/usr/bin/env python3
"""Build a CCTV-1 programme index from the public GDELT Visual Explorer inventory."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "cctv1.json"
INVENTORY_BASE = "https://visualexplorer.gdeltproject.org/ve/site/inv/json/"
UA = "gdelt-cctv1-programme-index/1.0"
ID_PATTERN = re.compile(r"^CCTV1_(\d{8})_(\d{6})(?:_[A-Za-z0-9-]+)?$")
OFFSET_PATTERN = re.compile(r"^([+-]?)(\d{1,2})(\d{2})$")
SAVED_OFFSET_PATTERN = re.compile(r"^UTC([+-])(\d{2}):(\d{2})$")
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def safe_text(value: object, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"Inventory field {field!r} must be a non-empty string")
    if len(value) > 2000:
        raise ValueError(f"Inventory field {field!r} is too long")
    return value.strip()


def utc_offset_label(value: object) -> str:
    raw = safe_text(str(value), "utc_offset")
    match = OFFSET_PATTERN.fullmatch(raw)
    if not match:
        raise ValueError(f"Invalid utc_offset: {raw!r}")
    sign, hours, minutes = match.groups()
    hours_value, minutes_value = int(hours), int(minutes)
    if hours_value > 14 or minutes_value > 59 or (hours_value == 14 and minutes_value):
        raise ValueError(f"Invalid utc_offset: {raw!r}")
    return f"UTC{sign or '+'}{hours_value:02d}:{minutes_value:02d}"


def validate_inventory(payload: object, day: date) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("shows"), list):
        raise ValueError("Inventory must be an object containing a shows list")

    shows: list[dict] = []
    seen: set[str] = set()
    for position, raw in enumerate(payload["shows"]):
        if not isinstance(raw, dict):
            raise ValueError(f"Inventory show {position} must be an object")
        identifier = safe_text(raw.get("id"), "id")
        match = ID_PATTERN.fullmatch(identifier)
        if not match or match.group(1) != day.strftime("%Y%m%d"):
            raise ValueError(f"Invalid CCTV-1 inventory id for {day}: {identifier!r}")
        if identifier in seen:
            raise ValueError(f"Duplicate CCTV-1 inventory id: {identifier}")
        seen.add(identifier)

        program = safe_text(raw.get("program"), "program")
        runtime = safe_text(raw.get("runtime"), "runtime")
        runtime_match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})", runtime)
        if (
            not runtime_match
            or int(runtime_match.group(2)) > 59
            or int(runtime_match.group(3)) > 59
            or int(runtime_match.group(1)) * 3600
            + int(runtime_match.group(2)) * 60
            + int(runtime_match.group(3))
            <= 0
        ):
            raise ValueError(f"Invalid runtime for {identifier}: {runtime!r}")
        start_time = safe_text(raw.get("start_time"), "start_time")
        stop_time = safe_text(raw.get("stop_time"), "stop_time")
        start_localtime = safe_text(raw.get("start_localtime"), "start_localtime")
        for field, value in (
            ("start_time", start_time),
            ("stop_time", stop_time),
            ("start_localtime", start_localtime),
        ):
            try:
                datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError as error:
                raise ValueError(f"Invalid {field} for {identifier}: {value!r}") from error
        offset = utc_offset_label(raw.get("utc_offset"))
        title = safe_text(raw.get("title", ""), "title", required=False)
        shows.append(
            {
                "id": identifier,
                "inventory_day": day.isoformat(),
                "program": program,
                "title": title,
                "runtime": runtime,
                "start_time_utc": start_time,
                "start_time_local": start_localtime,
                "stop_time_utc": stop_time,
                "utc_offset": offset,
                "official_video_url": None,
                "official_video_status": "no_verified_match",
                "media_note": (
                    "Visual Explorer 将 CCTV-1 标记为 Audio Only。"
                    "未核验到对应的公开官方单条视频；官方站内搜索不会自动匹配本节目。"
                ),
                "archive_url": f"https://archive.org/details/{identifier}",
                "visual_explorer_url": (
                    "https://visualexplorer.gdeltproject.org/tvv?"
                    + urlencode({"id": identifier})
                ),
                "official_search_url": (
                    "https://www.yangshipin.cn/search/result?"
                    + urlencode({"key": program})
                ),
            }
        )
    return shows


def fetch_inventory(day: date, timeout: int = 30) -> list[dict]:
    day_text = day.strftime("%Y%m%d")
    url = f"{INVENTORY_BASE}CCTV1.{day_text}.inventory.json"
    request = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Inventory response exceeded {MAX_RESPONSE_BYTES} bytes")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid inventory JSON for {day_text}") from error
    return validate_inventory(payload, day)


def read_existing() -> dict | None:
    if not OUTPUT.exists():
        return None
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Refusing to replace unreadable snapshot {OUTPUT}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("shows"), list):
        raise ValueError(f"Refusing to replace invalid snapshot {OUTPUT}")
    if not isinstance(payload.get("day_status"), list):
        raise ValueError(f"Refusing to replace snapshot without day_status: {OUTPUT}")
    seen: set[str] = set()
    for show in payload["shows"]:
        if not isinstance(show, dict) or not isinstance(show.get("id"), str):
            raise ValueError(f"Refusing to replace snapshot with invalid show: {OUTPUT}")
        if not ID_PATTERN.fullmatch(show["id"]) or show["id"] in seen:
            raise ValueError(f"Refusing to replace snapshot with invalid or duplicate id: {OUTPUT}")
        seen.add(show["id"])
    return payload


def retain_previous_show(show: dict, day: date) -> dict:
    """Rebuild a retained record from validated fields; never carry old URLs or media fields."""
    match = ID_PATTERN.fullmatch(show.get("id", ""))
    if not match or match.group(1) != day.strftime("%Y%m%d"):
        raise ValueError(f"Invalid retained CCTV-1 inventory id: {show.get('id')!r}")
    saved_offset = SAVED_OFFSET_PATTERN.fullmatch(show.get("utc_offset", ""))
    if not saved_offset:
        raise ValueError(f"Invalid retained UTC offset for {show['id']}")
    sign, hours, minutes = saved_offset.groups()
    rebuilt = validate_inventory(
        {
            "shows": [
                {
                    "id": show["id"],
                    "program": show.get("program"),
                    "title": show.get("title", ""),
                    "runtime": show.get("runtime"),
                    "start_time": show.get("start_time_utc"),
                    "stop_time": show.get("stop_time_utc"),
                    "start_localtime": show.get("start_time_local"),
                    "utc_offset": f"{sign}{hours}{minutes}",
                }
            ]
        },
        day,
    )[0]
    generated_at = show.get("snapshot_generated_at")
    if isinstance(generated_at, str):
        rebuilt["snapshot_generated_at"] = generated_at
    rebuilt["snapshot_freshness"] = "retained_after_fetch_failure"
    return rebuilt


def build_snapshot(today: date, existing: dict | None) -> dict:
    requested_days = (today, today - timedelta(days=1))
    previous_shows = {
        show.get("id"): show
        for show in (existing or {}).get("shows", [])
        if isinstance(show, dict) and isinstance(show.get("id"), str)
    }
    fetched: dict[str, list[dict]] = {}
    failures: dict[str, str] = {}
    for day in requested_days:
        key = day.isoformat()
        try:
            fetched[key] = fetch_inventory(day)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            failures[key] = f"{type(error).__name__}: {error}"

    if not fetched:
        details = "; ".join(f"{day}: {reason}" for day, reason in failures.items())
        raise RuntimeError(f"All CCTV-1 inventories failed; snapshot preserved. {details}")

    retained_by_day = {
        day.isoformat(): [
            retain_previous_show(show, day)
            for show in previous_shows.values()
            if show.get("inventory_day") == day.isoformat()
        ]
        for day in requested_days
    }
    shows_by_id: dict[str, dict] = {}
    statuses = []
    for day in requested_days:
        key = day.isoformat()
        if key in fetched:
            selected = fetched[key]
            statuses.append(
                {"day": key, "status": "success", "show_count": len(selected)}
            )
        else:
            selected = retained_by_day[key]
            statuses.append(
                {
                    "day": key,
                    "status": "error",
                    "show_count": len(selected),
                    "retained_show_count": len(selected),
                    "error": failures[key],
                }
            )
        for show in selected:
            shows_by_id.setdefault(show["id"], show)

    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    successful_at = {
        status["day"]: generated
        for status in statuses
        if status["status"] == "success"
    }
    for show in shows_by_id.values():
        show.setdefault("snapshot_freshness", "current")
        if show.get("inventory_day") in successful_at:
            show["snapshot_generated_at"] = generated
        elif existing:
            old_show = previous_shows.get(show["id"], {})
            show["snapshot_generated_at"] = old_show.get(
                "snapshot_generated_at", existing.get("generated_at", "")
            )

    return {
        "schema_version": "1.0",
        "snapshot_state": "current",
        "generated_at": generated,
        "source": (
            "https://visualexplorer.gdeltproject.org/ve/site/inv/json/"
        ),
        "source_label": "GDELT TV News Visual Explorer CCTV-1 programme inventory",
        "source_notice": (
            "研究性索引，不是 CCTV/央视频官方发布或授权。"
            "Visual Explorer 的节目元数据、字幕和媒体增强为自动处理，"
            "节目可能缺失、延迟或存在音视频问题。"
        ),
        "date_window": "Inventory 文件日及节目 ID 日期均按 UTC；节目同时保留原站当地时间与 UTC 偏移。",
        "timezone": "UTC",
        "day_status": statuses,
        "latest_successful_at": generated,
        "shows": sorted(
            shows_by_id.values(),
            key=lambda show: (show.get("start_time_utc", ""), show["id"]),
            reverse=True,
        ),
    }


def atomic_write(payload: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="cctv1-", suffix=".json.tmp", dir=OUTPUT.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, OUTPUT)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        help="UTC date to use as today (YYYY-MM-DD); defaults to current UTC date",
    )
    args = parser.parse_args()
    today = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    payload = build_snapshot(today, read_existing())
    atomic_write(payload)
    print(
        f"Wrote {len(payload['shows'])} CCTV-1 programme records to {OUTPUT}; "
        f"day statuses: {payload['day_status']}"
    )


if __name__ == "__main__":
    main()
