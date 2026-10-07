#!/usr/bin/env python3
"""Validate the static site's JSON snapshots and local HTML references."""
from __future__ import annotations

import json
import ast
import math
import re
import shutil
import subprocess
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class LocalReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value.strip())


class InlineScripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []
        self._inline = False
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self._inline = not any(name == "src" for name, _ in attrs)
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._inline:
            self._current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._inline:
            self.sources.append("".join(self._current))
            self._inline = False


def validate_json() -> None:
    files = sorted((ROOT / "data").rglob("*.json"))
    if not files:
        raise ValueError("No JSON data files found")
    for path in files:
        with path.open(encoding="utf-8") as stream:
            json.load(stream)

    latest = json.loads((ROOT / "data" / "latest.json").read_text(encoding="utf-8"))
    video = json.loads((ROOT / "data" / "video.json").read_text(encoding="utf-8"))
    if not isinstance(latest, dict) or not isinstance(latest.get("generated_at"), str):
        raise ValueError("data/latest.json is missing generated_at")
    if not isinstance(video, dict) or not isinstance(video.get("generated_at"), str):
        raise ValueError("data/video.json is missing generated_at")
    if not isinstance(video.get("latest_videos"), list):
        raise ValueError("data/video.json is missing latest_videos list")
    for story in latest.get("top_news", []):
        for place in story.get("locations", []):
            latitude, longitude = place.get("latitude"), place.get("longitude")
            if latitude is None and longitude is None:
                continue
            if (
                not isinstance(latitude, (int, float))
                or not isinstance(longitude, (int, float))
                or not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise ValueError(f"Invalid coordinates in story {story.get('id', '<unknown>')}")
    validate_cctv1()
    print(f"Validated {len(files)} JSON files")


def validate_cctv1() -> None:
    path = ROOT / "data" / "cctv1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0":
        raise ValueError("data/cctv1.json has an unsupported schema_version")
    shows = payload.get("shows")
    day_status = payload.get("day_status")
    if not isinstance(shows, list) or not isinstance(day_status, list):
        raise ValueError("data/cctv1.json must contain shows and day_status lists")
    if payload.get("snapshot_state") == "not_collected":
        if shows or day_status or payload.get("generated_at") is not None:
            raise ValueError("Uncollected CCTV-1 snapshot must be explicitly empty")
        return
    if payload.get("snapshot_state") != "current":
        raise ValueError("CCTV-1 snapshot_state must be current or not_collected")
    for key in ("generated_at", "latest_successful_at"):
        value = payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f"CCTV-1 snapshot is missing {key}")
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"CCTV-1 {key} is not an ISO timestamp") from error

    id_pattern = re.compile(r"^CCTV1_(\d{8})_(\d{6})(?:_[A-Za-z0-9-]+)?$")
    seen: set[str] = set()
    for show in shows:
        if not isinstance(show, dict):
            raise ValueError("CCTV-1 shows entries must be objects")
        identifier = show.get("id")
        match = id_pattern.fullmatch(identifier) if isinstance(identifier, str) else None
        if not match or identifier in seen:
            raise ValueError(f"Invalid or duplicate CCTV-1 ID: {identifier!r}")
        seen.add(identifier)
        try:
            inventory_day = date.fromisoformat(show["inventory_day"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid inventory_day for {identifier}") from error
        if inventory_day.strftime("%Y%m%d") != match.group(1):
            raise ValueError(f"CCTV-1 ID date mismatch for {identifier}")
        for field in ("program", "title", "runtime", "start_time_utc", "start_time_local", "stop_time_utc", "utc_offset"):
            if not isinstance(show.get(field), str) or not show[field]:
                raise ValueError(f"CCTV-1 {identifier} is missing string field {field}")
        runtime = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})", show["runtime"])
        if not runtime or int(runtime.group(2)) > 59 or int(runtime.group(3)) > 59:
            raise ValueError(f"Invalid CCTV-1 runtime for {identifier}")
        for field in ("start_time_utc", "start_time_local", "stop_time_utc"):
            try:
                datetime.strptime(show[field], "%Y-%m-%d %H:%M:%S")
            except ValueError as error:
                raise ValueError(f"Invalid CCTV-1 {field} for {identifier}") from error
        if show.get("official_video_url") is not None or show.get("official_video_status") != "no_verified_match":
            raise ValueError(f"CCTV-1 {identifier} must not claim an unverified official video")
        _validate_cctv_url(show.get("archive_url"), "archive.org", f"/details/{identifier}", {})
        _validate_cctv_url(
            show.get("visual_explorer_url"),
            "visualexplorer.gdeltproject.org",
            "/tvv",
            {"id": identifier},
        )
        _validate_cctv_url(
            show.get("official_search_url"),
            "www.yangshipin.cn",
            "/search/result",
            {"key": show["program"]},
        )
    for status in day_status:
        if not isinstance(status, dict) or status.get("status") not in {"success", "error"}:
            raise ValueError("CCTV-1 day_status has an invalid entry")
        try:
            date.fromisoformat(status["day"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("CCTV-1 day_status has an invalid day") from error
        if not isinstance(status.get("show_count"), int) or status["show_count"] < 0:
            raise ValueError("CCTV-1 day_status has an invalid show_count")
        if status["status"] == "success" and status.get("error"):
            raise ValueError("Successful CCTV-1 inventory day cannot contain an error")
        if status["status"] == "error" and not isinstance(status.get("error"), str):
            raise ValueError("Failed CCTV-1 inventory day must include its error")
        records_for_day = sum(show["inventory_day"] == status["day"] for show in shows)
        if records_for_day != status["show_count"]:
            raise ValueError(f"CCTV-1 show_count mismatch for {status['day']}")


def _validate_cctv_url(
    value: object, host: str, path: str, expected_query: dict[str, str]
) -> None:
    if not isinstance(value, str):
        raise ValueError("CCTV-1 external URL must be a string")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != host
        or parsed.netloc != host
        or parsed.path != path
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or parse_qs(parsed.query, keep_blank_values=True) != expected_query
    ):
        raise ValueError(f"Disallowed CCTV-1 external URL: {value!r}")


def validate_python() -> None:
    files = sorted((ROOT / "scripts").rglob("*.py"))
    if not files:
        raise ValueError("No Python scripts found")
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print(f"Validated Python syntax in {len(files)} scripts")


def validate_inline_javascript() -> None:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required to validate inline JavaScript")
    count = 0
    for html_file in sorted(ROOT.rglob("*.html")):
        parser = InlineScripts()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for source in parser.sources:
            if not source.strip():
                continue
            result = subprocess.run(
                [node, "--check", "-"],
                input=source,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise ValueError(
                    f"Invalid inline JavaScript in {html_file.relative_to(ROOT)}:\n"
                    + result.stderr
                )
            count += 1
    print(f"Validated inline JavaScript in {count} scripts")


def validate_local_references() -> None:
    html_files = sorted(ROOT.rglob("*.html"))
    failures: list[str] = []
    for html_file in html_files:
        parser = LocalReferences()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for reference in parser.references:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = unquote(parsed.path).lstrip("/")
            resolved = (ROOT / target) if reference.startswith("/") else (html_file.parent / target)
            if not resolved.resolve().is_relative_to(ROOT.resolve()) or not resolved.exists():
                failures.append(f"{html_file.relative_to(ROOT)} -> {reference}")
    if failures:
        raise ValueError("Broken local HTML references:\n" + "\n".join(failures))
    print(f"Validated local links in {len(html_files)} HTML files")


if __name__ == "__main__":
    validate_python()
    validate_json()
    validate_inline_javascript()
    validate_local_references()
