#!/usr/bin/env python3
"""Validate the static site's JSON snapshots and local HTML references."""
from __future__ import annotations

import json
import ast
import math
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
    print(f"Validated {len(files)} JSON files")


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
