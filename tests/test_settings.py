from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.settings import AppSettings, SettingsStore, normalize_settings


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = SettingsStore(path)
            source = AppSettings(
                template_path="C:/tmp/template.png",
                font_size=72,
                text_color=(12, 34, 56),
                safe_area_color=(1, 2, 3),
                marker_color=(4, 5, 6),
                x_auto=False,
                x=321,
                name_mode="auto",
                output_format="png",
                theme="light",
                window_geometry="abc",
            )
            store.save(source)
            loaded = store.load()
            self.assertEqual(loaded.template_path, source.template_path)
            self.assertEqual(loaded.font_size, 72)
            self.assertEqual(loaded.text_color, (12, 34, 56))
            self.assertEqual(loaded.safe_area_color, (1, 2, 3))
            self.assertEqual(loaded.marker_color, (4, 5, 6))
            self.assertFalse(loaded.x_auto)
            self.assertEqual(loaded.x, 321)
            self.assertEqual(loaded.name_mode, "auto")
            self.assertEqual(loaded.theme, "light")

    def test_normalize_old_and_invalid_values(self):
        settings = normalize_settings(
            {
                "font_size": 0,
                "x_offset": -999999,
                "line_spacing": 9999,
                "output_format": "docx",
                "theme": "neon",
                "text_color": "#112233",
                "safe_area_color": "#AABBCC",
                "marker_color": [1, 2, 3],
                "splitter_sizes": ["bad", 10],
            }
        )
        self.assertEqual(settings.font_size, 100)
        self.assertEqual(settings.x_offset, -100000)
        self.assertEqual(settings.line_spacing, 1000)
        self.assertEqual(settings.output_format, "pdf")
        self.assertEqual(settings.theme, "dark")
        self.assertEqual(settings.text_color, (17, 34, 51))
        self.assertEqual(settings.safe_area_color, (170, 187, 204))
        self.assertEqual(settings.marker_color, (1, 2, 3))
        self.assertEqual(settings.splitter_sizes, [10])

    def test_normalize_arbitrary_invalid_types(self):
        settings = normalize_settings(
            {
                "font_size": {"bad": 1},
                "letter_spacing": "abc",
                "x": [],
                "x_offset": {},
                "y_offset": None,
                "line_spacing": [1],
                "margin": "no",
                "split_after": {},
                "text_color": {"r": 1},
                "align": [],
                "name_mode": [],
                "output_format": {},
                "pdf_mode": [],
                "theme": [],
                "preview_mode": {},
                "template_path": 123,
                "font_path": [],
                "x_auto": "false",
                "y_auto": "true",
                "preview": "no",
                "splitter_sizes": [1, "bad", 3.7, float("nan")],
            }
        )
        self.assertEqual(settings.font_size, 100)
        self.assertEqual(settings.letter_spacing, 0)
        self.assertEqual(settings.x, 0)
        self.assertEqual(settings.x_offset, 0)
        self.assertEqual(settings.y_offset, 0)
        self.assertEqual(settings.line_spacing, 4)
        self.assertEqual(settings.margin, 36)
        self.assertEqual(settings.split_after, 1)
        self.assertEqual(settings.text_color, (0, 0, 0))
        self.assertEqual(settings.align, "left")
        self.assertEqual(settings.name_mode, "single_line")
        self.assertEqual(settings.output_format, "pdf")
        self.assertEqual(settings.pdf_mode, "multi")
        self.assertEqual(settings.theme, "dark")
        self.assertEqual(settings.preview_mode, "test")
        self.assertEqual(settings.template_path, "")
        self.assertEqual(settings.font_path, "")
        self.assertFalse(settings.x_auto)
        self.assertTrue(settings.y_auto)
        self.assertFalse(settings.preview)
        self.assertEqual(settings.splitter_sizes, [1, 3])

    def test_corrupt_file_is_backed_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{not json", encoding="utf-8")
            loaded = SettingsStore(path).load()
            self.assertEqual(loaded.font_size, 100)
            self.assertFalse(path.exists())
            backups = list(Path(tmp).glob("settings.json.corrupt-*"))
            self.assertEqual(len(backups), 1)

    def test_missing_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            loaded = SettingsStore(Path(tmp) / "absent.json").load()
            self.assertEqual(loaded, AppSettings())


if __name__ == "__main__":
    unittest.main()
