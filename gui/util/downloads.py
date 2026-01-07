import re
import threading
import time
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from src.data.library import CONSOLE_EXTENSIONS, GameMetadata


class DownloadStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    METADATA = "creating metadata"
    ARTWORK = "downloading artwork"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class DownloadTask:
    id: str
    game_name: str
    console: str
    status: DownloadStatus
    progress: float
    error: Optional[str] = None
    igdb_game: Optional[Any] = None
    source: Optional[Any] = None


class DownloadManager:
    def __init__(self, library, sources, db, steamgrid):
        self.library = library
        self.sources = sources
        self.db = db
        self.steamgrid = steamgrid

        self.tasks: dict[str, DownloadTask] = {}
        self.active_downloads: int = 0
        self.max_concurrent: int = 3

        self.callbacks: list[Callable] = []
        self._last_notify: float = 0
        self._notify_throttle: float = 0.5

        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def _notify_callbacks(self):
        current_time = time.time()
        if current_time - self._last_notify < self._notify_throttle:
            return

        self._last_notify = current_time
        for callback in self.callbacks:
            try:
                callback()
            except Exception:
                pass

    def queue_download(
        self, game_name: str, console: str, source, igdb_game=None
    ) -> str:
        task_id = str(uuid4())

        task = DownloadTask(
            id=task_id,
            game_name=game_name,
            console=console,
            status=DownloadStatus.QUEUED,
            progress=0.0,
            igdb_game=igdb_game,
            source=source,
        )

        self.tasks[task_id] = task
        self._notify_callbacks()

        return task_id

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> list[DownloadTask]:
        return list(self.tasks.values())

    def get_active_tasks(self) -> list[DownloadTask]:
        return [
            t
            for t in self.tasks.values()
            if t.status
            in [
                DownloadStatus.QUEUED,
                DownloadStatus.DOWNLOADING,
                DownloadStatus.EXTRACTING,
                DownloadStatus.METADATA,
                DownloadStatus.ARTWORK,
            ]
        ]

    def cancel_download(self, task_id: str):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status != DownloadStatus.COMPLETE:
                task.status = DownloadStatus.FAILED
                task.error = "cancelled by user"
                self._notify_callbacks()

    def clear_completed(self):
        to_remove = [
            tid
            for tid, task in self.tasks.items()
            if task.status in [DownloadStatus.COMPLETE, DownloadStatus.FAILED]
        ]

        for tid in to_remove:
            del self.tasks[tid]

        self._notify_callbacks()

    def _worker_loop(self):
        while True:
            time.sleep(0.5)

            if self.active_downloads >= self.max_concurrent:
                continue

            queued = [
                t for t in self.tasks.values() if t.status == DownloadStatus.QUEUED
            ]

            if not queued:
                continue

            task = queued[0]
            self.active_downloads += 1

            download_thread = threading.Thread(
                target=self._process_download, args=(task,), daemon=True
            )
            download_thread.start()

    def _update_task(self, task: DownloadTask, status: DownloadStatus, progress: float):
        task.status = status
        task.progress = progress
        self._notify_callbacks()

    def _process_download(self, task: DownloadTask):
        try:
            console_code_upper = task.console.upper()
            console_meta = self.library.get_console_metadata(console_code_upper)

            if not console_meta:
                task.status = DownloadStatus.FAILED
                task.error = "console not found"
                self._notify_callbacks()
                return

            console_dir = self.library.console_root / console_meta.name
            games_dir = console_dir / "games"

            game_slug = re.sub(r"[^\w\s-]", "", task.game_name.lower())
            game_slug = re.sub(r"[-\s]+", "-", game_slug).strip("-")

            game_dir = games_dir / game_slug
            game_dir.mkdir(parents=True, exist_ok=True)
            (game_dir / "resources").mkdir(exist_ok=True)
            (game_dir / "saves").mkdir(exist_ok=True)
            (game_dir / "graphics").mkdir(exist_ok=True)

            download_dir = game_dir / "resources"
            extension = CONSOLE_EXTENSIONS.get(console_code_upper, "bin")
            dest_file = download_dir / f"base.{extension}"

            self._update_task(task, DownloadStatus.DOWNLOADING, 0.2)

            success = self.sources.download_file(task.source, dest_file, task.game_name)

            if not success:
                task.status = DownloadStatus.FAILED
                task.error = "download failed"
                self._notify_callbacks()
                return

            if console_code_upper == "SWITCH" and dest_file.suffix == ".zip":
                self._update_task(task, DownloadStatus.EXTRACTING, 0.4)

                if not self._extract_switch_game(dest_file, download_dir):
                    task.status = DownloadStatus.FAILED
                    task.error = "extraction failed"
                    self._notify_callbacks()
                    return

            self._update_task(task, DownloadStatus.METADATA, 0.6)

            metadata = GameMetadata(
                code=f"{console_code_upper.lower()}-{game_slug}",
                console=console_code_upper,
                id=0,
                title={"NA": task.game_name},
                publisher={"NA": "unknown"},
                year=0,
                region="NA",
            )

            if task.igdb_game:
                metadata.id = task.igdb_game.id
                metadata.title = {"NA": task.igdb_game.name}
                metadata.publisher = {"NA": task.igdb_game.publisher or "unknown"}
                metadata.year = task.igdb_game.year or 0

            metadata.save(game_dir / "metadata.json")

            if self.steamgrid and self.steamgrid.api_key:
                try:
                    self._update_task(task, DownloadStatus.ARTWORK, 0.8)

                    graphics_dir = game_dir / "graphics"
                    graphics_dir.mkdir(parents=True, exist_ok=True)

                    search_name = (
                        task.igdb_game.name if task.igdb_game else task.game_name
                    )
                    games = self.steamgrid.search_game(search_name)

                    if games and len(games) > 0:
                        game_id = games[0].get("id")

                        for asset_type, file_name in [
                            ("grids", "grid"),
                            ("heroes", "hero"),
                            ("logos", "logo"),
                            ("icons", "icon"),
                        ]:
                            assets = self.steamgrid.get_assets(game_id, asset_type)
                            if assets and len(assets) > 0:
                                url = assets[0].get("url")
                                if url:
                                    dest = graphics_dir / f"{file_name}.png"
                                    self.steamgrid.download_asset(url, dest)
                except Exception:
                    pass

            self._update_task(task, DownloadStatus.COMPLETE, 1.0)

        except Exception as e:
            task.status = DownloadStatus.FAILED
            task.error = str(e)
            self._notify_callbacks()
        finally:
            self.active_downloads -= 1

    def _extract_switch_game(self, zip_path: Path, dest_dir: Path) -> bool:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                xci_files = [f for f in zf.namelist() if f.lower().endswith(".xci")]

                if xci_files:
                    xci_file = xci_files[0]
                    zf.extract(xci_file, dest_dir)

                    extracted = dest_dir / xci_file
                    target = dest_dir / "base.xci"

                    if extracted != target:
                        extracted.rename(target)

                    zip_path.unlink()
                    return True

            return False
        except Exception:
            return False
