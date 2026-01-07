from pathlib import Path
from typing import TYPE_CHECKING, Optional

import flet as ft

if TYPE_CHECKING:
    from gui.app import VRetroApp
from gui.elements.card import ConsoleCard


class WelcomeView:
    def __init__(self, app: "VRetroApp") -> None:
        self.app = app

    def create(self) -> ft.Column:
        self.console_grid = ft.GridView(
            expand=True,
            runs_count=5,
            max_extent=180,
            child_aspect_ratio=0.8,
            spacing=20,
            run_spacing=20,
        )

        self._populate_consoles()

        return ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "vretro",
                                size=48,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "select a console to get started",
                                size=16,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=40,
                ),
                ft.Container(
                    content=self.console_grid,
                    padding=ft.Padding.only(left=40, right=40, bottom=40),
                    expand=True,
                ),
            ],
            spacing=0,
        )

    def _populate_consoles(self) -> None:
        self.console_grid.controls.clear()

        if not self.app.library.consoles or not self.app.library.games:
            self.app.library.scan(verbose=False)

        consoles = sorted(self.app.library.get_consoles())

        for console_code in consoles:
            console_meta = self.app.library.get_console_metadata(console_code)
            games = [
                g for g in self.app.library.games if g.metadata.console == console_code
            ]

            card = ConsoleCard(
                console_code,
                console_meta,
                len(games),
                lambda _, cc=console_code: self.app.show_console(cc),
                self._get_console_path(console_meta),
            ).create()
            self.console_grid.controls.append(card)

        add_btn = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.ADD_CIRCLE_OUTLINE,
                            size=64,
                            color=ft.Colors.PRIMARY,
                        ),
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "install console",
                            size=14,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        padding=10,
                    ),
                ],
                spacing=0,
            ),
            border=ft.border.all(2, ft.Colors.OUTLINE),
            border_radius=12,
            ink=True,
            on_click=lambda _: self.app.show_install_console(),
        )
        self.console_grid.controls.append(add_btn)

    def _get_console_path(self, console_meta) -> Optional[Path]:
        if not console_meta:
            return None

        console_dir = self.app.library.console_root / console_meta.name
        icon_path = console_dir / "graphics" / "icon.png"
        logo_path = console_dir / "graphics" / "logo.png"

        if icon_path.exists():
            return icon_path
        elif logo_path.exists():
            return logo_path

        return None
