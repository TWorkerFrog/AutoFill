from __future__ import annotations

import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from core.generator import (
    GenerationJob,
    OutputConfig,
    RenderConfig,
    generate,
)


def _font_path() -> str:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    raise unittest.SkipTest("Нет доступного TTF-шрифта для теста")


def _template(directory: Path, size=(400, 300), *, rgba=False) -> Path:
    mode = "RGBA" if rgba else "RGB"
    image = Image.new(mode, size, (255, 255, 255, 0) if rgba else "white")
    path = directory / "template.png"
    image.save(path, dpi=(216, 216))
    return path


def _render_config(font_path: str) -> RenderConfig:
    return RenderConfig(
        font_path=font_path,
        font_size=28,
        x="center",
        y="center",
        align="center",
        margin=20,
        name_mode="split_surname",
    )


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.font_path = _font_path()
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.template = _template(self.directory)

    def tearDown(self):
        self.tmp.cleanup()

    def test_png_output_and_manifest(self):
        output = self.directory / "out"
        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван", "Иванович"), ("Петров", "Пётр", "Петрович")),
            render=_render_config(self.font_path),
            output=OutputConfig(str(output), output_format="png"),
        )
        result = generate(job)
        self.assertFalse(result.cancelled)
        self.assertEqual(result.created, 2)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.files), 2)
        self.assertTrue(all(Path(path).is_file() for path in result.files))
        self.assertTrue((output / ".autofill-manifest.json").is_file())
        with Image.open(result.files[0]) as image:
            self.assertAlmostEqual(float(image.info["dpi"][0]), 216.0, delta=2)

    def test_pdf_single_page_size_uses_template_dpi(self):
        output = self.directory / "out"
        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван", "Иванович"), ("Петров", "Пётр", "Петрович")),
            render=_render_config(self.font_path),
            output=OutputConfig(
                str(output),
                output_format="pdf",
                pdf_mode="single",
                pdf_name="All",
            ),
        )
        result = generate(job)
        self.assertEqual(result.created, 2)
        self.assertEqual(len(result.files), 1)
        target = Path(result.files[0])
        data = target.read_bytes()
        media_boxes = re.findall(rb"/MediaBox\s*\[([^\]]+)\]", data)
        self.assertEqual(len(media_boxes), 2)
        # 400 px / 216 dpi * 72 = 133.33 pt; 300 px / 216 dpi * 72 = 100 pt.
        values = [float(value) for value in media_boxes[0].split()]
        self.assertAlmostEqual(values[2], 133.333, delta=0.5)
        self.assertAlmostEqual(values[3], 100.0, delta=0.5)

    def test_conflict_number_policy(self):
        output = self.directory / "out"
        output.mkdir()
        existing = output / "Иванов_Иван.pdf"
        existing.write_bytes(b"old")
        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван"),),
            render=_render_config(self.font_path),
            output=OutputConfig(str(output), output_format="pdf", conflict_policy="number"),
        )
        result = generate(job)
        self.assertEqual(result.created, 1)
        self.assertTrue(existing.exists())
        self.assertTrue(Path(result.files[0]).name.endswith("_2.pdf"))

    def test_conflict_skip_policy(self):
        output = self.directory / "out"
        output.mkdir()
        existing = output / "Иванов_Иван.png"
        existing.write_bytes(b"old")
        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван"),),
            render=_render_config(self.font_path),
            output=OutputConfig(str(output), output_format="png", conflict_policy="skip"),
        )
        result = generate(job)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(existing.read_bytes(), b"old")

    def test_output_never_overwrites_selected_template(self):
        template = self.directory / "Иванов_Иван.png"
        Image.new("RGB", (400, 300), "red").save(template)
        original = template.read_bytes()
        job = GenerationJob(
            template_path=str(template),
            people=(("Иванов", "Иван"),),
            render=_render_config(self.font_path),
            output=OutputConfig(
                str(self.directory), output_format="png", conflict_policy="replace",
            ),
        )
        result = generate(job)
        self.assertEqual(result.created, 1)
        self.assertEqual(template.read_bytes(), original)
        self.assertEqual(Path(result.files[0]).name, "Иванов_Иван_2.png")

    def test_duplicate_names_get_numbers_in_one_run(self):
        for policy in ("number", "replace", "skip"):
            with self.subTest(policy=policy):
                output = self.directory / f"out-{policy}"
                job = GenerationJob(
                    template_path=str(self.template),
                    people=(("Иванов", "Иван"), ("Иванов", "Иван")),
                    render=_render_config(self.font_path),
                    output=OutputConfig(
                        str(output), output_format="png", conflict_policy=policy,
                    ),
                )
                result = generate(job)
                self.assertEqual(result.created, 2)
                names = sorted(Path(path).name for path in result.files)
                self.assertEqual(names, ["Иванов_Иван.png", "Иванов_Иван_2.png"])

    def test_cancel_mid_generation(self):
        cancel = threading.Event()
        output = self.directory / "out"

        def progress(done, _total, _name):
            if done == 1:
                cancel.set()

        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван"), ("Петров", "Пётр"), ("Сидоров", "Сидор")),
            render=_render_config(self.font_path),
            output=OutputConfig(str(output), output_format="png"),
        )
        result = generate(job, progress=progress, cancel_event=cancel)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.created, 1)
        self.assertEqual(len(result.files), 1)

    def test_pdf_fallback_without_pypdf(self):
        output = self.directory / "out"
        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван"), ("Петров", "Пётр")),
            render=_render_config(self.font_path),
            output=OutputConfig(
                str(output),
                output_format="pdf",
                pdf_mode="single",
                pdf_name="Fallback",
            ),
        )
        with patch("importlib.util.find_spec", return_value=None):
            result = generate(job)
        self.assertEqual(result.created, 2)
        self.assertEqual(len(result.files), 1)
        data = Path(result.files[0]).read_bytes()
        self.assertEqual(len(re.findall(rb"/MediaBox\s*\[", data)), 2)

    def test_cancel_before_start(self):
        cancel = threading.Event()
        cancel.set()
        output = self.directory / "out"
        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван"),),
            render=_render_config(self.font_path),
            output=OutputConfig(str(output), output_format="png"),
        )
        result = generate(job, cancel_event=cancel)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.files, [])

    def test_cleanup_manifest_does_not_touch_foreign_files(self):
        output = self.directory / "out"
        output.mkdir()
        managed = output / "managed.png"
        foreign = output / "foreign.png"
        managed.write_bytes(b"x")
        foreign.write_bytes(b"x")
        from core.paths import save_manifest

        save_manifest(output, ["managed.png"])
        job = GenerationJob(
            template_path=str(self.template),
            people=(("Иванов", "Иван"),),
            render=_render_config(self.font_path),
            output=OutputConfig(str(output), output_format="png", cleanup_previous=True),
        )
        result = generate(job)
        self.assertEqual(result.created, 1)
        self.assertFalse(managed.exists())
        self.assertTrue(foreign.exists())


if __name__ == "__main__":
    unittest.main()
