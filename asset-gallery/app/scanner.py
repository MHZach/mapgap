import hashlib
import logging
import queue
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import get_settings
from app.embeddings import embedder
from app.models import ImagePayload, ScanResult
from app.progress import progress
from app.store import store

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
THUMB_SIZE = (420, 420)

# How many batches to pre-load into memory while GPU/MPS is encoding
_PIPELINE_DEPTH = 3


def folder_tags_for(path: Path, root: Path) -> list[str]:
    """Return all directory components between root and the file as tags.

    Example: root=data/images, path=data/images/compendium/2025/shot.jpg
             → ["compendium", "2025"]
    """
    try:
        rel = path.relative_to(root)
        return [p.lower() for p in rel.parts[:-1]]  # exclude filename itself
    except ValueError:
        return []


def scan_directory(directory: Path | None = None, limit: int | None = None) -> ScanResult:
    settings = get_settings()
    root = (directory or settings.image_dir).expanduser().resolve()
    excluded = settings.excluded_paths
    all_files = [
        p for p in root.rglob("*")
        if p.suffix.lower() in IMAGE_EXTENSIONS
        and not any(p.is_relative_to(excl) for excl in excluded)
    ]
    if limit:
        all_files = all_files[:limit]

    # ── Skip already-indexed images ──────────────────────────────────────────
    log.info("Checking %d files against existing index…", len(all_files))
    existing_ids = store.get_all_ids()
    files = [f for f in all_files if stable_id(f) not in existing_ids]
    skipped_upfront = len(all_files) - len(files)
    if skipped_upfront:
        log.info("Skipping %d already-indexed images, processing %d new ones.",
                 skipped_upfront, len(files))

    batch_size = settings.scan_batch_size
    n_batches = (len(files) + batch_size - 1) // batch_size if files else 0
    progress.reset(total=len(files), n_batches=n_batches)

    result = ScanResult(scanned=len(all_files), indexed=0, skipped=skipped_upfront, errors=[])

    if not files:
        progress.finish(indexed=0, skipped=skipped_upfront)
        return result

    # ── Producer-consumer pipeline ───────────────────────────────────────────
    # Producer: loads + thumbnails batches concurrently (I/O-bound, ThreadPool)
    # Consumer: encodes + upserts on GPU/MPS/CPU (compute-bound, main thread)
    # Buffer: _PIPELINE_DEPTH batches in flight to keep compute unit saturated
    loaded_queue: queue.Queue = queue.Queue(maxsize=_PIPELINE_DEPTH)

    def producer() -> None:
        batches = [files[i: i + batch_size] for i in range(0, len(files), batch_size)]
        for batch_paths in batches:
            loaded: list[dict] = []
            with ThreadPoolExecutor() as pool:
                future_to_path = {pool.submit(_load_for_batch, p, root): p for p in batch_paths}
                for future in as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        loaded.append(future.result())
                    except (OSError, UnidentifiedImageError, ValueError) as exc:
                        result.skipped += 1
                        result.errors.append(f"{path}: {exc}")
                        progress.inc_skipped()
                    progress.inc_loaded()
            loaded_queue.put(loaded)
        loaded_queue.put(None)  # sentinel

    producer_thread = threading.Thread(target=producer, daemon=True)
    producer_thread.start()

    # Consumer: encode + upsert each batch as it arrives
    batch_idx = 0
    while True:
        loaded = loaded_queue.get()
        if loaded is None:
            break
        if not loaded:
            batch_idx += 1
            continue

        try:
            vectors = embedder.encode_images_batch([item["image"] for item in loaded])
        except Exception as exc:
            for item in loaded:
                result.skipped += 1
                result.errors.append(f"{item['path']}: encode error: {exc}")
                progress.inc_skipped()
            batch_idx += 1
            continue

        payloads: list[ImagePayload] = []
        for item, vector in zip(loaded, vectors):
            motif_class, motif_score = embedder.classify_motif_vector(vector)
            payloads.append(ImagePayload(
                id=item["id"],
                path=str(item["path"]),
                filename=item["path"].name,
                width=item["width"],
                height=item["height"],
                aspect_ratio=item["aspect_ratio"],
                aspect_class=aspect_class(item["aspect_ratio"]),
                motif_class=motif_class,
                motif_score=motif_score,
                folder_tags=item["folder_tags"],
                thumbnail_url=f"/api/images/{item['id']}/thumbnail",
            ))

        store.upsert_many(payloads, vectors)
        result.indexed += len(payloads)
        batch_idx += 1
        progress.set_batch(batch=batch_idx, indexed=result.indexed)

    producer_thread.join()
    progress.finish(indexed=result.indexed, skipped=result.skipped)
    return result


def _load_for_batch(path: Path, root: Path) -> dict:
    path = path.expanduser().resolve()
    image_id = stable_id(path)
    with Image.open(path) as img:
        width, height = img.size
        if width <= 0 or height <= 0:
            raise ValueError("invalid dimensions")
        rgb = img.convert("RGB")
        make_thumbnail(rgb, image_id)
    return {
        "id": image_id,
        "path": path,
        "image": rgb,
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 4),
        "folder_tags": folder_tags_for(path, root),
    }


def make_thumbnail(image: Image.Image, image_id: str) -> None:
    settings = get_settings()
    thumb = image.copy()
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(settings.thumb_dir / f"{image_id}.jpg", "JPEG", quality=85, optimize=True)


def aspect_class(aspect_ratio: float) -> str:
    if 0.9 <= aspect_ratio <= 1.1:
        return "square"
    if aspect_ratio > 1.1:
        return "landscape"
    return "portrait"


def stable_id(path: Path) -> str:
    stat = path.stat()
    key = f"{path}:{stat.st_size}:{int(stat.st_mtime)}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, digest))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan images into local Qdrant.")
    parser.add_argument("directory", nargs="?", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    scan = scan_directory(args.directory, args.limit)
    print(scan.model_dump_json(indent=2))
