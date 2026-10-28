from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from core.text_render import check_text_bounds, draw_text_block, layout_block, measure_block


def _font(size: int = 80):
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    raise unittest.SkipTest("Нет доступного TTF-шрифта для теста")


def _ink_bbox(image: Image.Image):
    background = Image.new("RGB", image.size, "white")
    return ImageChops.difference(image.convert("RGB"), background).getbbox()


class TextRenderTests(unittest.TestCase):
    def setUp(self):
        self.font = _font()
        self.image = Image.new("RGB", (800, 600), "white")
        self.draw = ImageDraw.Draw(self.image)

    def test_center_anchor_and_left_alignment(self):
        draw_text_block(
            self.draw, ["Тест"], self.font, (0, 0, 0),
            "center", "center", 0, 0, "left", 0, 0, 800, 600,
        )
        bbox = _ink_bbox(self.image)
        self.assertIsNotNone(bbox)
        self.assertLessEqual(abs((bbox[0] + bbox[2]) / 2 - 400), 6)
        self.assertLessEqual(abs((bbox[1] + bbox[3]) / 2 - 300), 10)

    def test_letter_spacing_keeps_left_anchor(self):
        draw_text_block(
            self.draw, ["Тест"], self.font, (0, 0, 0),
            100, 300, 0, 0, "left", 0, 20, 800, 600,
        )
        bbox = _ink_bbox(self.image)
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(bbox[0], 100)
        self.assertLessEqual(bbox[0], 112)

    def test_letter_spacing_centers_block(self):
        draw_text_block(
            self.draw, ["Тест"], self.font, (0, 0, 0),
            "center", "center", 0, 0, "center", 0, 20, 800, 600,
        )
        bbox = _ink_bbox(self.image)
        self.assertIsNotNone(bbox)
        self.assertLessEqual(abs((bbox[0] + bbox[2]) / 2 - 400), 6)

    def test_right_alignment(self):
        layout = layout_block(
            ["Тест"], self.font, 700, 300, "right", 0, 0, 800, 600,
        )
        self.assertAlmostEqual(layout.right, 700, delta=0.5)
        self.assertAlmostEqual(layout.line_left(0), 700 - layout.metrics.width, delta=0.5)

    def test_measure_block_uses_font_line_height(self):
        metrics = measure_block(["Одна", "Две"], self.font, letter_spacing=4, line_spacing=10)
        ascent, descent = self.font.getmetrics()
        self.assertEqual(metrics.height, 2 * (ascent + descent) + 10)
        self.assertGreaterEqual(metrics.width, metrics.line_widths[0])

    def test_bounds_include_offsets_and_vertical_edges(self):
        problems = check_text_bounds(
            ["Тест"], self.font, "center", "center", 0, 800, 40,
            img_height=600, y="center", x_offset=-500, y_offset=-400,
        )
        sides = {side for _line, _overflow, side in problems}
        self.assertIn("left", sides)
        self.assertIn("top", sides)

    def test_bounds_clean_center(self):
        problems = check_text_bounds(
            ["Тест"], self.font, "center", "center", 0, 800, 40,
            img_height=600, y="center",
        )
        self.assertEqual(problems, [])

    def test_auto_wrap_more_than_two_lines(self):
        from core.name_format import resolve_auto_lines

        narrow = resolve_auto_lines(
            ["Иванов", "Иван", "Иванович", "Дополнительное"],
            self.font,
            0,
            250,
            10,
        )
        self.assertGreaterEqual(len(narrow), 2)
        self.assertEqual(" ".join(narrow), "Иванов Иван Иванович Дополнительное")


if __name__ == "__main__":
    unittest.main()
