"""Локализация: словарь EN полон, tr() и язык работают согласованно.

Главный тест — скан всех ``tr("...")`` литералов в исходниках: каждая
русская строка интерфейса обязана иметь английский перевод.  Забытая
строка в ``i18n_en.py`` роняет тест, а не уезжает пользователю.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    is_english,
    language,
    set_language,
    tr,
)
from core.i18n_en import EN

ROOT = Path(__file__).resolve().parents[1]


def _iter_sources():
    for folder in ("core", "ui"):
        yield from (ROOT / folder).rglob("*.py")
    yield ROOT / "main.py"


def collect_tr_keys() -> set[str]:
    """Собирает все строковые литералы вызовов tr("...").

    AST автоматически склеивает соседние литералы ("a" "b") и учитывает
    переносы строк внутри строки - то, что реально увидит tr() в рантайме.
    """

    keys: set[str] = set()
    for path in _iter_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


@pytest.fixture
def ru_language():
    set_language("ru")
    yield
    set_language("ru")


class TestDictionaryCompleteness:
    def test_every_tr_literal_is_translated(self):
        missing = sorted(collect_tr_keys() - set(EN))
        assert not missing, f"Нет перевода для: {missing[:10]}"

    def test_dictionary_keys_exist_in_sources(self):
        # Мёртвые ключи не ошибка, но их рост мешает: проверяем, что словарь
        # не разросся мусором сильнее, чем ключей в коде.
        keys = collect_tr_keys()
        assert len(EN) <= 4 * len(keys) + 40

    def test_all_values_are_nonempty_strings(self):
        bad = [key for key, value in EN.items() if not isinstance(value, str) or not value.strip()]
        assert not bad, f"Пустые или не-строковые переводы: {bad[:5]}"

    def test_known_ui_strings_are_translated(self):
        for key in (
            "Основные",
            "Позиция",
            "Имя",
            "Вывод",
            "Настройки",
            "Живой предпросмотр",
            "Сгенерировать грамоты",
            "Обзор",
            "Сброс настроек",
        ):
            assert key in EN, f"Нет ключа «{key}»"
            assert EN[key] != key or key == "Обзор"  # «Обзор» совпадает допустимо


class TestTr:
    def test_ru_returns_source(self, ru_language):
        assert language() == "ru"
        assert not is_english()
        assert tr("Настройки") == "Настройки"

    def test_en_translates(self):
        set_language("en")
        assert is_english()
        assert tr("Настройки") == EN["Настройки"]

    def test_en_unknown_key_returns_source(self):
        set_language("en")
        assert tr("Такой строки точно нет 42") == "Такой строки точно нет 42"

    def test_language_invalid_falls_back_to_ru(self):
        set_language("de")
        assert language() == DEFAULT_LANGUAGE == "ru"
        assert not is_english()


class TestLanguageRegistry:
    def test_languages_known(self):
        assert set(LANGUAGES) == {"ru", "en"}
        assert all(isinstance(name, str) and name for name in LANGUAGES.values())
