"""Метаданные шрифтов, порядок начертаний и кеш сканирования."""

from __future__ import annotations

import pytest

from core.font_utils import (
    STYLE_ORDER,
    get_font_metadata,
    ordered_style_names,
)


@pytest.fixture(scope="module")
def arial_ttf(any_ttf):
    return any_ttf


class TestGetFontMetadata:
    def test_real_font_has_family(self, arial_ttf):
        family, style = get_font_metadata(arial_ttf)
        assert family is not None and family.strip()
        assert style is not None and style.strip()

    def test_garbage_file_returns_none_pair(self, tmp_path):
        fake = tmp_path / "fake.ttf"
        fake.write_bytes(b"not a font at all" * 10)
        assert get_font_metadata(fake) == (None, None)

    def test_empty_file_returns_none_pair(self, tmp_path):
        fake = tmp_path / "empty.ttf"
        fake.write_bytes(b"")
        assert get_font_metadata(fake) == (None, None)

    def test_missing_file_returns_none_pair(self, tmp_path):
        assert get_font_metadata(tmp_path / "absent.ttf") == (None, None)


class TestOrderedStyleNames:
    def test_regular_before_bold_before_italic(self):
        ordered = ordered_style_names(["Bold", "Italic", "Regular"])
        assert ordered == ["Regular", "Bold", "Italic"]

    def test_weights_from_thin_to_black(self):
        ordered = ordered_style_names(["Black", "Thin", "Medium", "Light", "Bold"])
        assert ordered == ["Thin", "Light", "Medium", "Bold", "Black"]

    def test_italic_variants_grouped_after_uprights(self):
        ordered = ordered_style_names(["Bold Italic", "Bold", "Thin"])
        assert ordered.index("Bold Italic") > ordered.index("Bold")
        assert ordered[0] == "Thin"

    def test_unknown_styles_go_last_alphabetically(self):
        ordered = ordered_style_names(["Zeta", "Regular", "Alpha Custom"])
        assert ordered[-2:] == ["Alpha Custom", "Zeta"]
        assert ordered[0] == "Regular"

    def test_empty_input(self):
        assert ordered_style_names([]) == []

    def test_style_order_has_no_duplicates(self):
        assert len(STYLE_ORDER) == len(set(STYLE_ORDER))
