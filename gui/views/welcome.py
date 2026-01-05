from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from ..app import VRetroApp


class WelcomeView:
    def __init__(self, app: "VRetroApp") -> None:
        self.app = app

    def create(self) -> ft.Column:
        return ft.Column(
            [
                ft.Container(
                    content=ft.Text(
                        "select a console to get started",
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                )
            ]
        )
