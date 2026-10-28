from __future__ import annotations

import unittest

from ui.overlays import safe_area_rect


class SafeAreaRectTests(unittest.TestCase):
    def test_zero_and_negative_margin_disable_guide(self):
        self.assertIsNone(safe_area_rect(900, 650, 0))
        self.assertIsNone(safe_area_rect(900, 650, -10))

    def test_rect_is_inset_by_margin(self):
        rect = safe_area_rect(900, 650, 36)
        self.assertIsNotNone(rect)
        assert rect is not None
        self.assertEqual(rect.x(), 36)
        self.assertEqual(rect.y(), 36)
        self.assertEqual(rect.width(), 827)
        self.assertEqual(rect.height(), 577)
        self.assertEqual(rect.right(), 863)
        self.assertEqual(rect.bottom(), 613)

    def test_large_margin_is_clamped_to_half_size(self):
        rect = safe_area_rect(1000, 800, 399)
        self.assertIsNotNone(rect)
        assert rect is not None
        self.assertEqual(rect.x(), 399)
        self.assertEqual(rect.y(), 399)
        self.assertEqual(rect.right(), 600)
        self.assertEqual(rect.bottom(), 400)

    def test_margin_equal_to_half_size_has_no_area(self):
        self.assertIsNone(safe_area_rect(900, 650, 325))
        self.assertIsNone(safe_area_rect(1000, 800, 400))

    def test_high_resolution_template(self):
        rect = safe_area_rect(6000, 4000, 100)
        self.assertIsNotNone(rect)
        assert rect is not None
        self.assertEqual(rect.x(), 100)
        self.assertEqual(rect.y(), 100)
        self.assertEqual(rect.right(), 5899)
        self.assertEqual(rect.bottom(), 3899)


if __name__ == "__main__":
    unittest.main()
