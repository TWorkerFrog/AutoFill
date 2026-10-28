"""Сборка Windows-исполняемого файла AutoFill через PyInstaller.

Скрипт можно запускать из любого каталога: все пути считаются от корня
репозитория.  Перед сборкой всегда перекомпилируются Qt-ресурсы, чтобы иконки
в ``icons/`` не расходились с устаревшим ``resources_rc.py``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _rcc_executable() -> str | None:
    executable = shutil.which("pyside6-rcc")
    if executable:
        return executable
    candidates = [
        Path(sys.executable).parent / "pyside6-rcc.exe",
        Path(sys.executable).parent / "pyside6-rcc",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def compile_resources() -> bool:
    print("Компиляция Qt-ресурсов…")
    qrc = ROOT / "resources.qrc"
    if not qrc.is_file():
        print(f"Не найден файл ресурсов: {qrc}")
        return False
    rcc = _rcc_executable()
    if rcc is None:
        print("Не найден pyside6-rcc. Установите PySide6: python -m pip install -r requirements.txt")
        return False

    result = subprocess.run(
        [rcc, str(qrc.name), "-o", "resources_rc.py"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print("Ошибка компиляции ресурсов:")
        print(result.stderr or result.stdout)
        return False
    print("resources_rc.py обновлён")
    return True


def build_exe() -> int:
    print("=" * 60)
    print("СБОРКА AutoFill")
    print("=" * 60)

    if not compile_resources():
        return 1

    icon_path = ROOT / "icons" / "app_icon.ico"
    if not icon_path.is_file():
        print(f"Не найдена иконка: {icon_path}")
        return 1
    if not (ROOT / "style.qss").is_file():
        print("Не найден style.qss")
        return 1

    for folder in ("build", "dist"):
        target = ROOT / folder
        if target.exists():
            shutil.rmtree(target)
            print(f"Удалено: {target.name}")

    separator = os.pathsep
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "AutoFill",
        "--icon",
        str(icon_path),
        "--add-data",
        f"{ROOT / 'style.qss'}{separator}.",
        "--hidden-import",
        "pypdf",
        "--collect-submodules",
        "fontTools",
        "--clean",
        "--noconfirm",
        str(ROOT / "main.py"),
    ]

    print("\nСборка…")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        print("\nОШИБКА СБОРКИ!")
        return result.returncode

    print("\n" + "=" * 60)
    print("СБОРКА УСПЕШНА")
    print("=" * 60)
    print(f"EXE: {ROOT / 'dist' / 'AutoFill.exe'}")
    return 0


if __name__ == "__main__":
    sys.exit(build_exe())
