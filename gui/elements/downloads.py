from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from download_manager import DownloadManager, DownloadStatus, DownloadTask


class DownloadsPanel:
    def __init__(self, page: ft.Page, download_manager: "DownloadManager"):
        self.page = page
        self.download_manager = download_manager
        self.expanded = False

        self.download_manager.add_callback(self._on_downloads_changed)

        self.container: ft.Container = None
        self.downloads_list: ft.Column = None
        self.toggle_button: ft.IconButton = None
        self.header_text: ft.Text = None
        self.clear_button: ft.IconButton = None

    def create(self) -> ft.Container:
        self.header_text = ft.Text(
            "downloads",
            size=14,
            weight=ft.FontWeight.W_500,
        )

        self.clear_button = ft.IconButton(
            icon=ft.Icons.CLEAR_ALL,
            icon_size=16,
            tooltip="clear completed",
            on_click=lambda _: self._clear_completed(),
            visible=False,
        )

        self.toggle_button = ft.IconButton(
            icon=ft.Icons.EXPAND_LESS,
            icon_size=20,
            on_click=lambda _: self._toggle_expanded(),
        )

        header_row = ft.Row(
            [
                ft.Icon(ft.Icons.DOWNLOAD, size=20),
                self.header_text,
                ft.Container(expand=True),
                self.clear_button,
                self.toggle_button,
            ],
            spacing=5,
        )

        self.downloads_list = ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        downloads_container = ft.Container(
            content=self.downloads_list,
            padding=ft.padding.only(top=10),
            visible=True,
        )

        self.container = ft.Container(
            content=ft.Column(
                [
                    header_row,
                    downloads_container,
                ],
                spacing=5,
            ),
            padding=15,
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.OUTLINE)),
            visible=False,
        )

        self._refresh()

        return self.container

    def _toggle_expanded(self):
        self.expanded = not self.expanded

        downloads_container = self.container.content.controls[1]
        downloads_container.visible = self.expanded

        self.toggle_button.icon = (
            ft.Icons.EXPAND_LESS if self.expanded else ft.Icons.EXPAND_MORE
        )

        self.page.update()

    def _clear_completed(self):
        self.download_manager.clear_completed()
        self._refresh()

    def _on_downloads_changed(self):
        try:
            self._refresh()
            self.page.update()
        except Exception:
            pass

    def _refresh(self):
        tasks = self.download_manager.get_all_tasks()

        if not tasks:
            self.container.visible = False
            return

        self.container.visible = True

        active_count = len(self.download_manager.get_active_tasks())
        total_count = len(tasks)

        if active_count > 0:
            self.header_text.value = f"downloads ({active_count}/{total_count})"
        else:
            self.header_text.value = f"downloads ({total_count})"

        completed = any(t.status.value in ["complete", "failed"] for t in tasks)
        self.clear_button.visible = completed

        self.downloads_list.controls.clear()

        for task in tasks:
            card = self._create_download_card(task)
            self.downloads_list.controls.append(card)

    def _create_download_card(self, task: "DownloadTask") -> ft.Container:
        status_color = self._get_status_color(task.status.value)

        title_row = ft.Row(
            [
                ft.Text(
                    task.game_name,
                    size=13,
                    weight=ft.FontWeight.W_500,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=16,
                    on_click=lambda _, tid=task.id: self._cancel_download(tid),
                    visible=task.status.value not in ["complete", "failed"],
                ),
            ],
            spacing=5,
        )

        status_text = ft.Text(
            task.status.value,
            size=11,
            color=status_color,
        )

        progress_bar = ft.ProgressBar(
            value=task.progress,
            height=3,
            visible=task.status.value not in ["complete", "failed"],
        )

        error_text = None
        if task.error:
            error_text = ft.Text(
                task.error,
                size=11,
                color=ft.Colors.ERROR,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

        content_controls = [title_row, status_text, progress_bar]

        if error_text:
            content_controls.append(error_text)

        return ft.Container(
            content=ft.Column(
                content_controls,
                spacing=5,
            ),
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

    def _get_status_color(self, status: str) -> str:
        if status == "complete":
            return ft.Colors.GREEN
        elif status == "failed":
            return ft.Colors.ERROR
        elif status == "queued":
            return ft.Colors.ON_SURFACE_VARIANT
        else:
            return ft.Colors.PRIMARY

    def _cancel_download(self, task_id: str):
        self.download_manager.cancel_download(task_id)
        self._refresh()

    def cleanup(self):
        self.download_manager.remove_callback(self._on_downloads_changed)
