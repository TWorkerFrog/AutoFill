from __future__ import annotations

import random
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
                text_color=(12, 34, 56, 128),
                safe_area_color=(1, 2, 3, 255),
                marker_color=(4, 5, 6, 64),
                x_auto=False,
                x=321,
                name_mode="auto",
                output_format="png",
                theme="light",
                language="en",
                window_geometry="abc",
            )
            store.save(source)
            loaded = store.load()
            self.assertEqual(loaded.template_path, source.template_path)
            self.assertEqual(loaded.font_size, 72)
            self.assertEqual(loaded.text_color, (12, 34, 56, 128))
            self.assertEqual(loaded.safe_area_color, (1, 2, 3, 255))
            self.assertEqual(loaded.marker_color, (4, 5, 6, 64))
            self.assertFalse(loaded.x_auto)
            self.assertEqual(loaded.x, 321)
            self.assertEqual(loaded.name_mode, "auto")
            self.assertEqual(loaded.theme, "light")
            self.assertEqual(loaded.language, "en")

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
        self.assertEqual(settings.theme, "system")
        self.assertEqual(settings.text_color, (17, 34, 51, 255))
        self.assertEqual(settings.safe_area_color, (170, 187, 204, 255))
        self.assertEqual(settings.marker_color, (1, 2, 3, 255))
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
        self.assertEqual(settings.line_spacing, 0)
        self.assertEqual(settings.margin, 36)
        self.assertEqual(settings.split_after, 1)
        self.assertEqual(settings.text_color, (0, 0, 0, 255))
        self.assertEqual(settings.align, "left")
        self.assertEqual(settings.name_mode, "single_line")
        self.assertEqual(settings.output_format, "pdf")
        self.assertEqual(settings.pdf_mode, "multi")
        self.assertEqual(settings.theme, "system")
        self.assertEqual(settings.preview_mode, "test")
        self.assertEqual(settings.template_path, "")
        self.assertEqual(settings.font_path, "")
        self.assertFalse(settings.x_auto)
        self.assertTrue(settings.y_auto)
        self.assertFalse(settings.preview)
        self.assertEqual(settings.splitter_sizes, [1, 3])

    def test_alpha_and_language_are_normalized(self):
        settings = normalize_settings(
            {
                "text_color": "#11223344",
                "safe_area_color": [10, 20, 30, 40],
                "language": "de",
            }
        )
        self.assertEqual(settings.text_color, (17, 34, 51, 68))
        self.assertEqual(settings.safe_area_color, (10, 20, 30, 40))
        self.assertEqual(settings.language, "ru")

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


class SettingsDefaultsTests(unittest.TestCase):
    """Значения по умолчанию — часть продукта, изменения роняют тест."""

    def test_defaults(self):
        settings = AppSettings()
        self.assertEqual(settings.font_size, 100)
        self.assertEqual(settings.letter_spacing, 0)
        self.assertEqual(settings.x_offset, 0)
        self.assertEqual(settings.y_offset, 0)
        self.assertEqual(settings.line_spacing, 0)
        self.assertEqual(settings.margin, 36)  # поля печати по умолчанию 36
        self.assertEqual(settings.text_color, (0, 0, 0, 255))
        self.assertEqual(settings.safe_area_color, (250, 9, 9, 255))  # FA0909
        self.assertEqual(settings.marker_color, (250, 9, 9, 255))  # FA0909
        self.assertEqual(settings.align, "left")
        self.assertEqual(settings.name_mode, "single_line")
        self.assertEqual(settings.output_format, "pdf")
        self.assertEqual(settings.pdf_mode, "multi")
        self.assertEqual(settings.pdf_name, "Все_грамоты")
        self.assertFalse(settings.preview)  # модальный предпросмотр выключен
        self.assertEqual(settings.theme, "system")
        self.assertEqual(settings.language, "ru")
        self.assertEqual(settings.color_input_format, "Hex")
        self.assertTrue(settings.ask_before_move)
        self.assertFalse(settings.cleanup_previous)

    def test_auto_flags_default_true(self):
        settings = AppSettings()
        self.assertTrue(settings.x_auto)
        self.assertTrue(settings.y_auto)


class ColorParsingTests(unittest.TestCase):
    def test_hex6_gets_full_alpha(self):
        self.assertEqual(normalize_settings({"text_color": "#FF0000"}).text_color, (255, 0, 0, 255))

    def test_hex8_keeps_alpha(self):
        self.assertEqual(
            normalize_settings({"text_color": "#FA090980"}).text_color, (250, 9, 9, 128)
        )

    def test_hex_invalid_returns_black(self):
        self.assertEqual(normalize_settings({"text_color": "#ZZZZZZ"}).text_color, (0, 0, 0, 255))
        self.assertEqual(normalize_settings({"text_color": "#12345"}).text_color, (0, 0, 0, 255))

    def test_component_out_of_range_clamped(self):
        self.assertEqual(
            normalize_settings({"text_color": [300, -20, 128, 500]}).text_color,
            (255, 0, 128, 255),
        )

    def test_none_color_returns_black(self):
        self.assertEqual(normalize_settings({"text_color": None}).text_color, (0, 0, 0, 255))


class SettingsFuzzTests(unittest.TestCase):
    """Фаззинг нормализации: любой мусор обязан превратиться в валидную схему."""

    GARBAGE = [
        None, "text", 42, -1, 1.5e300, [], {}, [1, 2], {"a": 1}, True, False,
        "#FFF", "#FFF0", "x" * 500, float("nan"), float("inf"), [None] * 5,
    ]

    def test_normalize_random_garbage_is_always_valid(self):
        rng = random.Random(777)
        fields = list(AppSettings().__dataclass_fields__)
        for _ in range(300):
            raw = {name: rng.choice(self.GARBAGE) for name in fields if rng.random() < 0.4}
            settings = normalize_settings(raw)
            # Инварианты валидной схемы после любой нормализации:
            self.assertIn(settings.theme, {"dark", "light", "system"})
            self.assertIn(settings.language, {"ru", "en"})
            self.assertIn(settings.color_input_format, {"Hex", "RGB", "HSL"})
            self.assertIn(settings.align, {"left", "center", "right"})
            self.assertIn(settings.name_mode, {"single_line", "split_surname", "split_all", "custom", "auto"})
            self.assertIn(settings.output_format, {"png", "pdf"})
            self.assertIn(settings.pdf_mode, {"multi", "single"})
            self.assertIn(settings.preview_mode, {"test", "longest", "custom"})
            for color in (settings.text_color, settings.safe_area_color, settings.marker_color):
                self.assertEqual(len(color), 4)
                self.assertTrue(all(0 <= part <= 255 for part in color))
            self.assertTrue(all(isinstance(size, int) and size >= 0 for size in settings.splitter_sizes))
            self.assertTrue(all(isinstance(size, int) and size >= 0 for size in settings.main_splitter_sizes))
            self.assertIsInstance(settings.font_size, int)
            self.assertTrue(1 <= settings.font_size <= 2000)

    def test_store_roundtrip_preserves_all_scalars(self):
        rng = random.Random(31)
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            source = AppSettings(
                font_size=rng.randint(1, 2000),
                letter_spacing=rng.randint(-20, 200),
                line_spacing=rng.randint(-100, 1000),
                margin=rng.randint(0, 5000),
                split_after=rng.randint(1, 30),
            )
            store.save(source)
            loaded = store.load()
            for name in ("font_size", "letter_spacing", "line_spacing", "margin", "split_after"):
                self.assertEqual(getattr(loaded, name), getattr(source, name))


class SettingsStoreBackupTests(unittest.TestCase):
    def test_save_creates_bak_of_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            store.save(AppSettings(font_size=100))
            store.save(AppSettings(font_size=200))
            backups = list(Path(tmp).glob("settings.json.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(store.load().font_size, 200)

    def test_load_falls_back_to_defaults_after_backup(self):
        # Повреждённый файл уезжает в .corrupt-*, настройки сбрасываются.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = SettingsStore(path)
            store.save(AppSettings(font_size=150))
            path.write_text("[][", encoding="utf-8")
            loaded = store.load()
            self.assertEqual(loaded, AppSettings())
            self.assertFalse(path.exists())

    def test_list_fields_normalized_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(
                '{"main_splitter_sizes": [900, 700], "splitter_sizes": "bad"}',
                encoding="utf-8",
            )
            settings = SettingsStore(path).load()
            self.assertEqual(settings.main_splitter_sizes, [900, 700])
            self.assertEqual(settings.splitter_sizes, [])


if __name__ == "__main__":
    unittest.main()
