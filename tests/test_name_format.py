"""Режимы переноса ФИО, авто-перенос по ширине и русские формы множества."""

from __future__ import annotations

import pytest

from core.name_format import (
    format_name_lines,
    plural,
    resolve_auto_lines,
    wrap_text,
)
from PIL import ImageFont


@pytest.fixture(scope="module")
def font(any_ttf):
    return ImageFont.truetype(any_ttf, size=40)


class TestFormatNameLines:
    def test_single_line_joins_everything(self):
        assert format_name_lines(["Иванов", "Иван", "Иванович"], "single_line") == [
            "Иванов Иван Иванович"
        ]

    def test_single_line_empty(self):
        assert format_name_lines([], "single_line") == [""]
        assert format_name_lines(["", "   "], "single_line") == [""]

    def test_split_surname_three_parts(self):
        assert format_name_lines(["Иванов", "Иван", "Иванович"], "split_surname") == [
            "Иванов",
            "Иван Иванович",
        ]

    def test_split_surname_two_parts_stays_two_lines(self):
        assert format_name_lines(["Иванов", "Иван"], "split_surname") == [
            "Иванов",
            "Иван",
        ]

    def test_split_surname_one_part(self):
        assert format_name_lines(["Иванов"], "split_surname") == ["Иванов"]

    def test_split_all(self):
        assert format_name_lines(["Иванов", "Иван", "Иванович"], "split_all") == [
            "Иванов",
            "Иван",
            "Иванович",
        ]

    def test_custom_split_after_two(self):
        assert format_name_lines(
            ["Иванов", "Иван", "Иванович"], "custom", split_after=2
        ) == ["Иванов Иван", "Иванович"]

    def test_custom_split_after_beyond_words_count(self):
        assert format_name_lines(
            ["Иванов", "Иван"], "custom", split_after=5
        ) == ["Иванов Иван"]

    def test_custom_split_after_clamped_to_one(self):
        assert format_name_lines(
            ["Иванов", "Иван"], "custom", split_after=0
        ) == ["Иванов", "Иван"]

    def test_auto_returns_none(self):
        assert format_name_lines(["Иванов", "Иван"], "auto") is None

    def test_unknown_mode_falls_back_to_single_line(self):
        assert format_name_lines(["Иванов", "Иван"], "neznaet") == ["Иванов Иван"]

    def test_parts_are_stripped(self):
        assert format_name_lines(["  Иванов ", "", "Иван  "], "single_line") == [
            "Иванов Иван"
        ]


class TestWrapText:
    def test_short_text_is_one_line(self, font):
        lines = wrap_text("Иван", font, 1000, 0)
        assert lines == ["Иван"]

    def test_narrow_width_wraps_every_word(self, font):
        lines = wrap_text("Иванов Иван Иванович", font, 50, 0)
        assert len(lines) >= 3
        assert " ".join(lines) == "Иванов Иван Иванович"

    def test_never_drops_words(self, font):
        text = "Иванов Иван Иванович Дополнительноеоченьдлинноеслово"
        lines = wrap_text(text, font, 120, 0)
        assert " ".join(lines) == text

    def test_letter_spacing_narrows_capacity(self, font):
        wide = wrap_text("Иванов Иван Иванович", font, 200, 0)
        spaced = wrap_text("Иванов Иван Иванович", font, 200, 6)
        assert len(spaced) >= len(wide)


class TestResolveAutoLines:
    def test_wide_image_is_single_line(self, font):
        lines = resolve_auto_lines(
            ["Иванов", "Иван", "Иванович"], font, 0, 4000, 36
        )
        assert lines == ["Иванов Иван Иванович"]

    def test_narrow_image_wraps(self, font):
        lines = resolve_auto_lines(
            ["Иванов", "Иван", "Иванович"], font, 0, 300, 36
        )
        assert len(lines) >= 2
        assert " ".join(lines) == "Иванов Иван Иванович"

    def test_margin_eats_width(self, font):
        comfortable = resolve_auto_lines(
            ["Иванов", "Иван", "Иванович"], font, 0, 900, 36
        )
        squeezed = resolve_auto_lines(
            ["Иванов", "Иван", "Иванович"], font, 0, 900, 380
        )
        assert len(squeezed) >= len(comfortable)

    def test_tiny_width_still_returns_words(self, font):
        lines = resolve_auto_lines(["Иванов", "Иван"], font, 0, 10, 0)
        assert " ".join(lines) == "Иванов Иван"

    def test_empty_parts(self, font):
        assert resolve_auto_lines(["", "  "], font, 0, 400, 36) == [""]


class TestPlural:
    def test_russian_forms(self):
        forms = ("грамота", "грамоты", "грамот")
        assert plural(1, forms) == "грамота"
        assert plural(2, forms) == "грамоты"
        assert plural(5, forms) == "грамот"
        assert plural(11, forms) == "грамот"
        assert plural(12, forms) == "грамот"
        assert plural(14, forms) == "грамот"
        assert plural(21, forms) == "грамота"
        assert plural(22, forms) == "грамоты"
        assert plural(100, forms) == "грамот"
        assert plural(101, forms) == "грамота"

    def test_negative_uses_absolute(self):
        forms = ("грамота", "грамоты", "грамот")
        assert plural(-1, forms) == "грамота"
        assert plural(-5, forms) == "грамот"
