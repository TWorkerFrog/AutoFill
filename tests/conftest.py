"""Общая инфраструктура тестов AutoFill.

Все тесты идут под offscreen-платформой Qt: ни один тест не открывает
нативные диалоги и не ждёт реального экрана.  Модальные подтверждения
подменяются стабом через фикстуру ``window_factory``.
"""

from __future__ import annotations

import os
import sys
from contextlib import suppress
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Реальные шрифты на машине с тестами (Windows-раннер CI имеет Arial).
TTF_CANDIDATES = (
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def any_ttf_path() -> str | None:
    for candidate in TTF_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


@pytest.fixture(scope="session")
def qapp():
    """Один QApplication на весь прогон."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(scope="session")
def any_ttf() -> str:
    path = any_ttf_path()
    if path is None:
        pytest.skip("Нет доступного TTF-шрифта")
    return path


@pytest.fixture
def tmp_store(tmp_path):
    """Свежий SettingsStore во временном каталоге."""
    from core.settings import SettingsStore

    return SettingsStore(tmp_path / "settings.json")


@pytest.fixture
def window_factory(qapp, tmp_store, monkeypatch):
    """Строит DiplomaGenerator, читающий временный settings.json.

    ``__init__`` окна сам создаёт ``SettingsStore()`` и грузит настройки
    пользователя, поэтому класс стора подменяется до сборки.  Модальные
    подтверждения подменяются стабом, возвращающим 0 (первая кнопка).
    """

    import ui.main_window as mw

    created: list = []

    def make(store=None, *, show: bool = False, **kwargs):
        target = store if store is not None else tmp_store
        monkeypatch.setattr(mw, "SettingsStore", lambda path=None: target)
        window = mw.DiplomaGenerator(**kwargs)
        window._message = lambda *args, **kwargs: 0
        created.append(window)
        if show:
            window.show()
        return window

    yield make
    for window in created:
        with suppress(Exception):
            window.close()
        window.deleteLater()


@pytest.fixture(autouse=True)
def _restore_language():
    """Тесты i18n меняют глобальный язык — возвращаем русский после."""

    from core.i18n import set_language

    yield
    set_language("ru")
