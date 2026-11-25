#!/usr/bin/env python3
"""Тесты проекта. Запуск: python -m unittest discover -s tests -v"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build  # noqa: E402


class DataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = build.load_data()

    def test_data_valid(self) -> None:
        errors, _warnings = build.validate(self.data)
        self.assertEqual(errors, [])

    def test_numbering_is_contiguous(self) -> None:
        numbers = [n for n, _e in build.numbered_entries(self.data)]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

    def test_ids_unique(self) -> None:
        ids = [e["id"] for e in self.data["entries"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_sections_known(self) -> None:
        known = {s["id"] for s in self.data["sections"]}
        for entry in self.data["entries"]:
            self.assertIn(entry["section"], known)


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = build.load_data()

    def test_html_has_all_entries(self) -> None:
        html = build.render_html(self.data)
        self.assertIn("<!DOCTYPE html>", html)
        for entry in self.data["entries"]:
            self.assertIn(build.iconize(build.esc(entry["title"])), html)

    def test_modern_has_all_entries(self) -> None:
        html = build.render_modern(self.data)
        printed = build.render_modern(self.data, print_mode=True)
        for entry in self.data["entries"]:
            self.assertIn(build.iconize(build.esc(entry["title"])), html)
            self.assertIn(build.iconize(build.esc(entry["title"])), printed)

    def test_txt_has_all_entries(self) -> None:
        txt = build.render_txt(self.data)
        for entry in self.data["entries"]:
            self.assertIn(entry["title"], txt)

    def test_html_escapes_markup(self) -> None:
        data = copy.deepcopy(self.data)
        data["entries"][0]["title"] = "<script>alert(1)</script>"
        html = build.render_html(data)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class ExtendTests(unittest.TestCase):
    """Проверяет, что листок действительно дополняемый."""

    def setUp(self) -> None:
        self.data = build.load_data()

    def test_inserting_entry_renumbers(self) -> None:
        data = copy.deepcopy(self.data)
        before = len(build.numbered_entries(data))
        new_entry = {
            "id": "test-insert",
            "section": data["sections"][0]["id"],
            "title": "Тестовая вставка",
            "hint": "Проверка нумерации.",
            "confidence": "single",
            "sources": [{"name": "test", "url": "https://example.com"}],
            "added": "2026-11-24",
            "added_by": "test",
        }
        data["entries"].insert(0, new_entry)
        numbers = [n for n, _e in build.numbered_entries(data)]
        self.assertEqual(len(numbers), before + 1)
        self.assertEqual(numbers[0], 1)
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        self.assertEqual(build.numbered_entries(data)[0][1]["id"], "test-insert")

    def test_confirmed_with_one_source_is_warned(self) -> None:
        data = copy.deepcopy(self.data)
        data["entries"][0]["confidence"] = "confirmed"
        data["entries"][0]["sources"] = [{"name": "one", "url": "https://example.com"}]
        errors, warnings = build.validate(data)
        self.assertTrue(any("2 источника" in w for w in warnings))
        errors_strict, _ = build.validate(data, strict=True)
        self.assertTrue(any("2 источника" in e for e in errors_strict))

    def test_spoiler_word_is_warned(self) -> None:
        data = copy.deepcopy(self.data)
        data["entries"][0]["hint"] = "Внутри тебя ждёт награда."
        _errors, warnings = build.validate(data)
        self.assertTrue(any("награда" in w for w in warnings))

    def test_unknown_section_is_error(self) -> None:
        data = copy.deepcopy(self.data)
        data["entries"][0]["section"] = "nowhere"
        errors, _ = build.validate(data)
        self.assertTrue(any("неизвестная секция" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
