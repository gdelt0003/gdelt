#!/usr/bin/env python3
"""Validate the static site's JSON snapshots and local HTML references."""
from __future__ import annotations

import json
import ast
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
    print(f"Validated {len(files)} JSON files")


def validate_python() -> None:
    files = sorted((ROOT / "scripts").rglob("*.py"))
    if not files:
        raise ValueError("No Python scripts found")
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print(f"Validated Python syntax in {len(files)} scripts")


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
    validate_local_references()
