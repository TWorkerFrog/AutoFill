from __future__ import annotations

import random
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.paths import (
    PathAllocator,
    backup_corrupt_file,
    cleanup_manifest,
    ensure_output_dir,
    load_json,
    load_manifest,
    read_text_file,
    safe_filename,
    safe_pdf_stem,
    safe_stem_from_parts,
    save_manifest,
    write_json_atomic,
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


class PathFuzzTests(unittest.TestCase):
    """Фаззинг с фиксированным зерном: сотни случайных строк, но набор
    одинаковый при каждом прогоне."""

    ALPHABET = list('Иван<>:"/\\|?* \t.\x00\x1f\x7f\ufeff0123456789CONcom1абвAUX_')

    def _random_stems(self, count: int = 400) -> list[str]:
        rng = random.Random(1234)
        stems = []
        for _ in range(count):
            length = rng.randint(0, 150)
            stems.append("".join(rng.choice(self.ALPHABET) for _ in range(length)))
        return stems

    def test_safe_filename_invariants_hold_for_random_input(self):
        forbidden = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
        reserved = {"con", "prn", "aux", "nul", "com1", "lpt1"}
        for stem in self._random_stems():
            name = safe_filename(stem)
            self.assertTrue(name, f"пусто для {stem!r}")
            self.assertFalse(forbidden.search(name), f"мусор в {name!r}")
            self.assertEqual(name, name.rstrip(" ."), f"точки в конце {name!r}")
            self.assertLessEqual(len(name), 100)
            self.assertFalse(name.split(".")[0].casefold() in reserved, name)

    def test_safe_filename_never_collides_after_random_input(self):
        # Разные исходные строки либо дают разные имена, либо безопасно
        # сводятся к одинаковым - главное, чтобы имя не превышало лимит
        # и не содержало запрещённых символов при создании файла.
        rng = random.Random(99)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            created = set()
            for _ in range(120):
                stem = "".join(rng.choice(self.ALPHABET) for _ in range(rng.randint(1, 120)))
                name = safe_filename(stem)
                path = directory / f"{name}.txt"
                # Повторы ожидаемы: safe_filename не обязан уникализировать.
                path.write_text("x", encoding="utf-8")
                created.add(path.name)

    def test_safe_filename_truncates_long_input(self):
        name = safe_filename("И" * 500)
        self.assertLessEqual(len(name), 100)

    def test_safe_filename_strips_control_characters(self):
        self.assertEqual(safe_filename("Ив\x00ан"), "Ив_ан")
        self.assertEqual(safe_filename("Ив\x1fан"), "Ив_ан")

    def test_safe_filename_replaces_bom(self):
        self.assertEqual(safe_filename("\ufeffИванов"), "Иванов")


class PathAllocatorExtraTests(unittest.TestCase):
    def test_new_name_returns_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            allocator = PathAllocator(tmp)
            self.assertEqual(allocator.resolve("Иванов", ".pdf").name, "Иванов.pdf")

    def test_numbering_continues_past_existing_numbered(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "Иванов.pdf").write_text("x", encoding="utf-8")
            (directory / "Иванов_2.pdf").write_text("x", encoding="utf-8")
            allocator = PathAllocator(directory)
            self.assertEqual(allocator.resolve("Иванов", ".pdf").name, "Иванов_3.pdf")

    def test_reserve_blocks_name_without_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            allocator = PathAllocator(tmp)
            allocator.reserve("Иванов.pdf")
            self.assertEqual(allocator.resolve("Иванов", ".pdf").name, "Иванов_2.pdf")

    def test_suffix_without_dot_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            allocator = PathAllocator(tmp)
            self.assertEqual(allocator.resolve("Иванов", "png").name, "Иванов.png")

    def test_suffixes_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            allocator = PathAllocator(tmp)
            self.assertEqual(allocator.resolve("Иванов", ".pdf").name, "Иванов.pdf")
            self.assertEqual(allocator.resolve("Иванов", ".png").name, "Иванов.png")

    def test_missing_directory_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            allocator = PathAllocator(Path(tmp) / "absent" / "deep")
            self.assertEqual(allocator.resolve("Иванов", ".pdf").name, "Иванов.pdf")

    def test_safe_filename_applied_to_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            allocator = PathAllocator(tmp)
            self.assertEqual(allocator.resolve('Ив<ан>:"?*', ".pdf").name, "Ив_ан_____.pdf")


class ReadTextFileExtraTests(unittest.TestCase):
    def test_utf8_with_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "names.txt"
            path.write_bytes("Иванов\n".encode("utf-8-sig"))
            self.assertEqual(read_text_file(path), "Иванов\n")

    def test_utf16_le_with_bom(self):
        import codecs

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "names.txt"
            path.write_bytes(
                codecs.BOM_UTF16_LE + "Иванов\n".encode("utf-16-le")
            )
            self.assertIn("Иванов", read_text_file(path))

    def test_utf16_be_with_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "names.txt"
            path.write_bytes("Иванов\n".encode("utf-16"))
            self.assertIn("Иванов", read_text_file(path))

    def test_empty_file_is_empty_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "names.txt"
            path.write_bytes(b"")
            self.assertEqual(read_text_file(path), "")

    def test_missing_file_raises(self):
        with self.assertRaises(OSError):
            read_text_file(Path("Z:/absolutely/absent/file.txt"))


class JsonAndBackupTests(unittest.TestCase):
    def test_write_json_atomic_roundtrip_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            write_json_atomic(path, {"имя": "Иванов", "n": 2})
            self.assertEqual(load_json(path), {"имя": "Иванов", "n": 2})
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))

    def test_write_json_atomic_replaces_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            path.write_text("old", encoding="utf-8")
            write_json_atomic(path, {"new": True})
            self.assertEqual(load_json(path), {"new": True})
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_backup_corrupt_file_renames(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{broken", encoding="utf-8")
            backup = backup_corrupt_file(path)
            self.assertIsNotNone(backup)
            self.assertTrue(Path(str(backup)).is_file())
            self.assertFalse(path.exists())
            self.assertIn(".corrupt-", str(backup))

    def test_backup_corrupt_file_missing_returns_none(self):
        self.assertIsNone(backup_corrupt_file(Path("Z:/absent.json")))

    def test_ensure_output_dir_fallback_used_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = ensure_output_dir("", fallback=Path(tmp) / "from-fallback")
            self.assertEqual(path.name, "from-fallback")

    def test_ensure_output_dir_relative_joins_home(self):
        path = ensure_output_dir("autofill-test-relative-dir")
        try:
            self.assertTrue(path.is_dir())
        finally:
            path.rmdir()


if __name__ == "__main__":
    unittest.main()
