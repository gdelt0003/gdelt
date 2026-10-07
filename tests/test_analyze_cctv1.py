from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_cctv1 import build_snapshot, validate_inventory  # noqa: E402


class Cctv1InventoryTests(unittest.TestCase):
    def show(self, day: date) -> dict:
        return {
            "id": f"CCTV1_{day:%Y%m%d}_020000",
            "program": "新闻联播",
            "title": "新闻联播",
            "runtime": "00:30:00",
            "start_time": f"{day:%Y-%m-%d} 02:00:00",
            "stop_time": f"{day:%Y-%m-%d} 02:30:00",
            "start_localtime": f"{day:%Y-%m-%d} 10:00:00",
            "utc_offset": "+0800",
        }

    def test_empty_inventory_is_a_valid_success(self) -> None:
        self.assertEqual(validate_inventory({"shows": []}, date(2026, 10, 7)), [])

    def test_invalid_inventory_and_wrong_day_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "shows list"):
            validate_inventory({}, date(2026, 10, 7))
        with self.assertRaisesRegex(ValueError, "Invalid CCTV-1 inventory id"):
            validate_inventory(
                {"shows": [self.show(date(2026, 10, 6))]},
                date(2026, 10, 7),
            )

    def test_records_do_not_claim_verified_official_video(self) -> None:
        day = date(2026, 10, 7)
        record = validate_inventory({"shows": [self.show(day)]}, day)[0]
        self.assertIsNone(record["official_video_url"])
        self.assertEqual(record["official_video_status"], "no_verified_match")
        self.assertNotIn("thumbnail", record)
        self.assertEqual(
            record["archive_url"],
            f"https://archive.org/details/{record['id']}",
        )

    def test_failed_day_is_distinct_from_empty_success_and_keeps_prior_records(self) -> None:
        today = date(2026, 10, 7)
        yesterday = date(2026, 10, 6)
        prior = validate_inventory({"shows": [self.show(yesterday)]}, yesterday)[0]
        prior["snapshot_generated_at"] = "2026-10-06T12:00:00+00:00"
        existing = {
            "generated_at": "2026-10-06T12:00:00+00:00",
            "shows": [prior],
            "day_status": [],
        }

        def fetch(day: date) -> list[dict]:
            if day == today:
                return []
            raise URLError("temporary upstream failure")

        with patch("analyze_cctv1.fetch_inventory", side_effect=fetch):
            snapshot = build_snapshot(today, existing)

        self.assertEqual(
            [(row["day"], row["status"], row["show_count"]) for row in snapshot["day_status"]],
            [("2026-10-07", "success", 0), ("2026-10-06", "error", 1)],
        )
        self.assertEqual(len(snapshot["shows"]), 1)
        self.assertEqual(
            snapshot["shows"][0]["snapshot_freshness"],
            "retained_after_fetch_failure",
        )

    def test_all_inventory_failures_abort_snapshot_generation(self) -> None:
        with patch(
            "analyze_cctv1.fetch_inventory",
            side_effect=URLError("temporary upstream failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "snapshot preserved"):
                build_snapshot(date(2026, 10, 7), None)


if __name__ == "__main__":
    unittest.main()
