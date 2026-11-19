"""Тема окна и диалогов не должна разъезжаться.

Регрессия: ``apply_settings`` менял ``current_theme``, но не перекрашивал
окно, если нужная радиокнопка уже была выбрана.  В итоге главное окно
оставалось светлым, а диалоги открывались в тёмной теме.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

import resources_rc  # noqa: E402, F401
import ui.main_window as mw  # noqa: E402
from core.settings import AppSettings  # noqa: E402


class ThemeSyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()
        store_path = Path(cls.temp_dir.name) / "settings.json"
        real_store = mw.SettingsStore
        mw.SettingsStore = lambda: real_store(store_path)
        cls.addClassCleanup(setattr, mw, "SettingsStore", real_store)
        cls.store_path = store_path

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def make_window(self, theme: str):
        window = mw.DiplomaGenerator()
        # Модальные диалоги в тестах не нужны: сразу подтверждаем.
        window._message = lambda *args, **kwargs: 0
        window.apply_settings(AppSettings(theme=theme))
        return window

    def assert_theme_applied(self, window, expected: str) -> None:
        self.assertEqual(window.current_theme, expected)
        self.assertEqual(window.property("theme"), expected)

    def test_switch_between_explicit_themes(self):
        window = self.make_window("light")
        self.assert_theme_applied(window, "light")
        window.apply_settings(AppSettings(theme="dark"))
        self.assert_theme_applied(window, "dark")
        window.apply_settings(AppSettings(theme="light"))
        self.assert_theme_applied(window, "light")
        window.close()

    def test_repeated_apply_keeps_theme(self):
        window = self.make_window("light")
        window.apply_settings(AppSettings(theme="light"))
        self.assert_theme_applied(window, "light")
        window.close()

    def test_reset_applies_default_theme(self):
        window = self.make_window("light")
        window.reset_settings()
        self.assert_theme_applied(window, window.current_theme)
        self.assertIn(window.property("theme"), {"light", "dark"})
        window.close()

    def test_theme_choice_after_reset_is_consistent(self):
        window = self.make_window("light")
        window.reset_settings()
        choice = window.get_theme_choice()
        expected = window._resolve_theme(choice)
        self.assert_theme_applied(window, expected)
        window.close()


if __name__ == "__main__":
    unittest.main()
