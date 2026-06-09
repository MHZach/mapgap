import threading
import time


class ScanProgress:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running: bool = False
        self.total: int = 0
        self.loaded: int = 0
        self.n_batches: int = 0
        self.batch: int = 0
        self.indexed: int = 0
        self.skipped: int = 0
        self._started_at: float = 0.0

    def reset(self, total: int, n_batches: int) -> None:
        with self._lock:
            self.running = True
            self.total = total
            self.loaded = 0
            self.n_batches = n_batches
            self.batch = 0
            self.indexed = 0
            self.skipped = 0
            self._started_at = time.monotonic()

    def inc_loaded(self) -> None:
        with self._lock:
            self.loaded += 1

    def inc_skipped(self) -> None:
        with self._lock:
            self.skipped += 1

    def set_batch(self, batch: int, indexed: int) -> None:
        with self._lock:
            self.batch = batch
            self.indexed = indexed

    def finish(self, indexed: int, skipped: int) -> None:
        with self._lock:
            self.running = False
            self.indexed = indexed
            self.skipped = skipped

    def snapshot(self) -> dict:
        with self._lock:
            pct = round(self.loaded / self.total * 100) if self.total else 0
            elapsed = time.monotonic() - self._started_at if self._started_at else 0.0
            imgs_per_sec = round(self.indexed / elapsed, 1) if elapsed > 1 and self.indexed else 0.0
            eta_sec = round((self.total - self.loaded) / (self.loaded / elapsed)) if elapsed > 1 and self.loaded else None
            return {
                "running": self.running,
                "total": self.total,
                "loaded": self.loaded,
                "pct": pct,
                "n_batches": self.n_batches,
                "batch": self.batch,
                "indexed": self.indexed,
                "skipped": self.skipped,
                "imgs_per_sec": imgs_per_sec,
                "eta_sec": eta_sec,
            }


progress = ScanProgress()
