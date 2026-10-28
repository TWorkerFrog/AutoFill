from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.paths import (
    PathAllocator,
    cleanup_manifest,
    ensure_output_dir,
    load_manifest,
    read_text_file,
    safe_filename,
    safe_pdf_stem,
    safe_stem_from_parts,
    save_manifest,
)


class PathTests(unittest.TestCase):
    def test_safe_filename_removes_windows_invalid_chars(self):
        self.assertEqual(safe_filename('Иванов: Иван/Иванович?'), "Иванов_ Иван_Иванович_")
        self.assertEqual(safe_filename("..."), "грамота")
        self.assertEqual(safe_filename("CON"), "_CON")
        self.assertEqual(safe_filename("Имя."), "Имя")

    def test_safe_stem_from_parts(self):
        self.assertEqual(safe_stem_from_parts(["Иванов", "Иван"]), "Иванов_Иван")

    def test_safe_pdf_stem_does_not_duplicate_extension(self):
        self.assertEqual(safe_pdf_stem("Мой.pdf"), "Мой")
        self.assertEqual(safe_pdf_stem("Мой.PDF"), "Мой")
        self.assertEqual(safe_pdf_stem("Мой"), "Мой")
        self.assertEqual(safe_pdf_stem(""), "Все_грамоты")

    def test_allocator_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "Иванов.pdf").write_text("x", encoding="utf-8")
            allocator = PathAllocator(directory)
            first = allocator.resolve("Иванов", ".pdf")
            second = allocator.resolve("Иванов", ".pdf")
            self.assertEqual(first.name, "Иванов_2.pdf")
            self.assertEqual(second.name, "Иванов_3.pdf")

    def test_ensure_output_dir_creates_and_is_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = ensure_output_dir(Path(tmp) / "nested" / "out")
            self.assertTrue(path.is_dir())
            (path / "probe.txt").write_text("ok", encoding="utf-8")

    def test_manifest_cleanup_only_removes_managed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            managed = directory / "managed.png"
            foreign = directory / "foreign.png"
            managed.write_text("x", encoding="utf-8")
            foreign.write_text("x", encoding="utf-8")
            save_manifest(directory, ["managed.png"])
            self.assertEqual(load_manifest(directory), ["managed.png"])
            removed, errors = cleanup_manifest(directory)
            self.assertEqual(removed, 1)
            self.assertEqual(errors, [])
            self.assertFalse(managed.exists())
            self.assertTrue(foreign.exists())

    def test_manifest_cleanup_can_exclude_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            template = directory / "template.png"
            managed = directory / "managed.png"
            template.write_text("template", encoding="utf-8")
            managed.write_text("x", encoding="utf-8")
            save_manifest(directory, ["template.png", "managed.png"])
            removed, errors = cleanup_manifest(directory, exclude=template)
            self.assertEqual(removed, 1)
            self.assertEqual(errors, [])
            self.assertTrue(template.exists())
            self.assertFalse(managed.exists())
            self.assertEqual(load_manifest(directory), [])

    def test_manifest_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            outside = directory.parent / "outside-autofill.txt"
            outside.write_text("x", encoding="utf-8")
            save_manifest(directory, ["../outside-autofill.txt"])
            removed, errors = cleanup_manifest(directory)
            self.assertEqual(removed, 0)
            self.assertTrue(outside.exists())
            outside.unlink()

    def test_read_text_file_supports_common_encodings(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            text = "Иванов Иван\nПетров Пётр\n"
            for encoding in ("utf-8", "utf-16", "cp1251"):
                path = directory / f"names-{encoding}.txt"
                path.write_bytes(text.encode(encoding))
                self.assertEqual(read_text_file(path), text)

    def test_read_text_file_reports_undefined_cp1251_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "names.txt"
            path.write_bytes(b"\x98")
            with self.assertRaises(UnicodeError):
                read_text_file(path)

    def test_cleanup_keeps_failed_file_in_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            managed = directory / "locked.png"
            managed.write_text("x", encoding="utf-8")
            save_manifest(directory, ["locked.png"])
            with patch.object(Path, "unlink", side_effect=OSError("locked")):
                removed, errors = cleanup_manifest(directory)
            self.assertEqual(removed, 0)
            self.assertTrue(errors)
            self.assertTrue(managed.exists())
            self.assertEqual(load_manifest(directory), ["locked.png"])

    def test_load_json_corrupt_returns_default(self):
        from core.paths import load_json

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{broken", encoding="utf-8")
            self.assertIsNone(load_json(path))
            self.assertEqual(load_json(path, default={}), {})


if __name__ == "__main__":
    unittest.main()
