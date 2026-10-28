"""Worker для фоновой генерации грамот."""

from __future__ import annotations

import logging
import threading
import traceback

from PySide6.QtCore import QObject, Signal, Slot

from core.generator import GenerationJob, generate

log = logging.getLogger(__name__)


class GenerationWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, job: GenerationJob):
        super().__init__()
        self.job = job
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            result = generate(self.job, self._on_progress, self.cancel_event)
        except Exception:
            details = traceback.format_exc()
            log.error("Генерация завершилась ошибкой:\n%s", details)
            self.failed.emit(details)
            return
        self.finished.emit(result)

    def _on_progress(self, done: int, total: int, name: str) -> None:
        self.progress.emit(done, total, name)
