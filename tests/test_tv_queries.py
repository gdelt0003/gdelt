from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_tv_gkg import gdelt_link, gdelt_links, video_source_links  # noqa: E402
from tv_queries import build_tv_clipgallery_url, build_tv_query  # noqa: E402


class TvQueryTests(unittest.TestCase):
    station_ids = {"CNN", "KGO"}

    def test_encodes_valid_station_and_positive_term(self) -> None:
        url = build_tv_clipgallery_url('"climate change"', "cnn", self.station_ids)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["query"], ['"climate change" station:CNN'])
        self.assertEqual(query["mode"], ["clipgallery"])

    def test_rejects_missing_station_or_positive_term(self) -> None:
        with self.assertRaisesRegex(ValueError, "station ID"):
            build_tv_query("climate", None, self.station_ids)
        with self.assertRaisesRegex(ValueError, "positive"):
            build_tv_query("station:CNN", None, self.station_ids)
        with self.assertRaisesRegex(ValueError, "positive"):
            build_tv_query("-climate station:CNN", None, self.station_ids)
        with self.assertRaisesRegex(ValueError, "listed by"):
            build_tv_query("climate", "CNNW", self.station_ids)

    def test_rejects_archive_item_id_as_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "Archive item IDs"):
            build_tv_query(
                "CNNW_20261007_040000_The_Story_Is_With_Elex_Michaelson",
                "CNN",
                self.station_ids,
            )

    def test_recent_archive_item_keeps_original_without_tv_id_query(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        identifier = "CNNW_20261007_040000_The_Story_Is_With_Elex_Michaelson"
        self.assertIsNone(gdelt_link(identifier, now.isoformat()))
        links = video_source_links(identifier, now.isoformat(), "CNNW", ["climate"])
        urls = [link["url"] for link in links]
        self.assertIn(f"https://archive.org/details/{identifier}", urls)
        self.assertTrue(any("/api/v2/doc/doc?" in url for url in urls))
        self.assertTrue(any("/api/v2/events/events?" in url for url in urls))
        self.assertFalse(any("/api/v2/tv/tv?" in url for url in urls))
        self.assertFalse(any(identifier in url for url in urls if "/api/v2/tv/tv?" in url))

    def test_keyword_links_preserve_doc_and_event_without_station_guess(self) -> None:
        links = gdelt_links(["climate", "change"])
        self.assertEqual(
            [link["label"] for link in links],
            ["GDELT 新闻/GKG", "GDELT 事件"],
        )
        urls = [link["url"] for link in links]
        self.assertTrue(all("climate+change" in url for url in urls))

    def test_tv_link_is_generated_only_with_explicit_verified_station(self) -> None:
        links = gdelt_links(["climate", "change"], "CNN", self.station_ids)
        tv_links = [link for link in links if "/api/v2/tv/tv?" in link["url"]]
        self.assertEqual(len(tv_links), 1)
        query = parse_qs(urlsplit(tv_links[0]["url"]).query)["query"][0]
        self.assertEqual(query, "climate change station:CNN")
        with self.assertRaisesRegex(ValueError, "must be verified"):
            gdelt_links(["climate"], "CNN")

    def test_hardcoded_tv_clipgallery_link_has_station_and_positive_term(self) -> None:
        html = (Path(__file__).resolve().parents[1] / "video.html").read_text(encoding="utf-8")
        links = re.findall(
            r'href="(https://api\.gdeltproject\.org/api/v2/tv/tv\?[^"]+)"',
            html,
        )
        for link in links:
            params = parse_qs(urlsplit(unescape(link)).query)
            self.assertEqual(params.get("mode"), ["clipgallery"])
            self.assertEqual(
                build_tv_query(params.get("query", [""])[0], None, self.station_ids),
                params["query"][0],
            )

    def test_older_archive_item_uses_visual_explorer_and_archive_source(self) -> None:
        old_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        identifier = "KQED_20261005_010000_PBS_News_Hour"
        links = video_source_links(identifier, old_date, "KQED", [])
        urls = [link["url"] for link in links]
        self.assertTrue(any("visualexplorer.gdeltproject.org/tvv?id=" in url for url in urls))
        self.assertIn(f"https://archive.org/details/{identifier}", urls)
        self.assertFalse(any("/api/v2/tv/tv?" in url for url in urls))


if __name__ == "__main__":
    unittest.main()
