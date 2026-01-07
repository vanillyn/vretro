import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional


class ProgressStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in progress"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressStep:
    name: str
    status: ProgressStatus
    progress: float
    message: str = ""
    error: Optional[str] = None


class ProgressTracker:
    def __init__(self, task_name: str):
        self.task_name = task_name
        self.steps: List[ProgressStep] = []
        self.current_step: Optional[ProgressStep] = None
        self.callbacks: List[Callable] = []
        self._lock = threading.Lock()

    def add_step(self, name: str) -> None:
        with self._lock:
            step = ProgressStep(
                name=name,
                status=ProgressStatus.PENDING,
                progress=0.0,
            )
            self.steps.append(step)
            self._notify()

    def start_step(self, name: str) -> None:
        with self._lock:
            for step in self.steps:
                if step.name == name:
                    step.status = ProgressStatus.IN_PROGRESS
                    step.progress = 0.0
                    self.current_step = step
                    self._notify()
                    break

    def update_step(
        self,
        name: str,
        progress: float,
        message: str = "",
    ) -> None:
        with self._lock:
            for step in self.steps:
                if step.name == name:
                    step.progress = progress
                    step.message = message
                    self._notify()
                    break

    def complete_step(self, name: str) -> None:
        with self._lock:
            for step in self.steps:
                if step.name == name:
                    step.status = ProgressStatus.COMPLETE
                    step.progress = 1.0
                    self._notify()
                    break

    def fail_step(self, name: str, error: str) -> None:
        with self._lock:
            for step in self.steps:
                if step.name == name:
                    step.status = ProgressStatus.FAILED
                    step.error = error
                    self._notify()
                    break

    def get_overall_progress(self) -> float:
        if not self.steps:
            return 0.0

        total = sum(step.progress for step in self.steps)
        return total / len(self.steps)

    def is_complete(self) -> bool:
        return all(
            step.status in [ProgressStatus.COMPLETE, ProgressStatus.FAILED]
            for step in self.steps
        )

    def has_errors(self) -> bool:
        return any(step.status == ProgressStatus.FAILED for step in self.steps)

    def add_callback(self, callback: Callable) -> None:
        self.callbacks.append(callback)

    def _notify(self) -> None:
        for callback in self.callbacks:
            try:
                callback()
            except Exception:
                pass


class ProgressDialog:
    def __init__(self, page, tracker: ProgressTracker):
        self.page = page
        self.tracker = tracker
        self.dialog = None

        self.tracker.add_callback(self._on_update)

    def create(self):
        import flet as ft

        self.title_text = ft.Text(self.tracker.task_name, size=20)

        self.overall_progress = ft.ProgressBar(
            value=0,
            height=8,
            border_radius=4,
        )

        self.steps_column = ft.Column(
            spacing=15,
            scroll=ft.ScrollMode.AUTO,
        )

        self._populate_steps()

        self.dialog = ft.AlertDialog(
            title=self.title_text,
            content=ft.Container(
                content=ft.Column(
                    [
                        self.overall_progress,
                        ft.Container(height=20),
                        self.steps_column,
                    ],
                    spacing=10,
                ),
                width=500,
                height=400,
            ),
            modal=True,
        )

        return self.dialog

    def _populate_steps(self) -> None:
        import flet as ft

        self.steps_column.controls.clear()

        for step in self.tracker.steps:
            icon = self._get_status_icon(step.status)
            color = self._get_status_color(step.status)

            step_row = ft.Row(
                [
                    ft.Icon(icon, color=color, size=24),
                    ft.Column(
                        [
                            ft.Text(
                                step.name,
                                size=14,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                step.message or step.status.value,
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=15,
            )

            step_container = ft.Container(
                content=ft.Column(
                    [
                        step_row,
                        ft.ProgressBar(
                            value=step.progress,
                            height=3,
                            visible=step.status == ProgressStatus.IN_PROGRESS,
                        ),
                    ],
                    spacing=8,
                ),
                padding=15,
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
                if step.status == ProgressStatus.IN_PROGRESS
                else None,
                animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT),
            )

            if step.error:
                error_text = ft.Container(
                    content=ft.Text(
                        step.error,
                        size=11,
                        color=ft.Colors.ERROR,
                    ),
                    padding=ft.Padding.only(left=39, top=5),
                )
                step_container.content.controls.append(error_text)

            self.steps_column.controls.append(step_container)

    def _get_status_icon(self, status: ProgressStatus) -> str:
        import flet as ft

        if status == ProgressStatus.COMPLETE:
            return ft.Icons.CHECK_CIRCLE
        elif status == ProgressStatus.FAILED:
            return ft.Icons.ERROR
        elif status == ProgressStatus.IN_PROGRESS:
            return ft.Icons.SYNC
        else:
            return ft.Icons.CIRCLE_OUTLINED

    def _get_status_color(self, status: ProgressStatus) -> str:
        import flet as ft

        if status == ProgressStatus.COMPLETE:
            return ft.Colors.GREEN
        elif status == ProgressStatus.FAILED:
            return ft.Colors.ERROR
        elif status == ProgressStatus.IN_PROGRESS:
            return ft.Colors.PRIMARY
        else:
            return ft.Colors.ON_SURFACE_VARIANT

    def _on_update(self) -> None:
        try:
            self.overall_progress.value = self.tracker.get_overall_progress()
            self._populate_steps()

            if self.tracker.is_complete():
                if self.dialog and self.page:
                    time.sleep(1)
                    self.page.pop_dialog()

            if self.page:
                self.page.update()
        except Exception:
            pass
