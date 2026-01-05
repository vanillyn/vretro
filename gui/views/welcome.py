from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from gui.app import VRetroApp


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
                    padding=ft.padding.only(left=40, right=40, bottom=40),
                    expand=True,
                ),
            ],
            spacing=0,
        )

    def _populate_consoles(self) -> None:
        self.console_grid.controls.clear()

        if not self.app.library.consoles:
            self.app.library.scan_consoles(verbose=False)

        consoles = sorted(self.app.library.get_consoles())

        for console_code in consoles:
            console_meta = self.app.library.get_console_metadata(console_code)
            games = self.app.library.filter_by_console(console_code)
            name = console_meta.name if console_meta else console_code

            icon_widget = self._get_console_icon(console_meta)

            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Container(content=icon_widget, expand=True),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        name,
                                        size=14,
                                        weight=ft.FontWeight.W_500,
                                        text_align=ft.TextAlign.CENTER,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"{len(games)} games",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                                spacing=2,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=10,
                        ),
                    ],
                    spacing=0,
                ),
                border_radius=12,
                ink=True,
                on_click=lambda _, c=console_code: self.app.show_console(c),
            )
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

    def _get_console_icon(self, console_meta) -> ft.Control:
        if not console_meta:
            return ft.Container(
                content=ft.Icon(ft.Icons.VIDEOGAME_ASSET, size=64),
                alignment=ft.Alignment.CENTER,
            )

        console_dir = self.app.library.console_root / console_meta.name
        icon_path = console_dir / "graphics" / "icon.png"
        logo_path = console_dir / "graphics" / "logo.png"

        if icon_path.exists():
            return ft.Container(
                content=ft.Image(
                    src=str(icon_path),
                    fit=ft.BoxFit.CONTAIN,
                ),
                alignment=ft.Alignment.CENTER,
                padding=20,
            )
        elif logo_path.exists():
            return ft.Container(
                content=ft.Image(
                    src=str(logo_path),
                    fit=ft.BoxFit.CONTAIN,
                ),
                alignment=ft.Alignment.CENTER,
                padding=20,
            )

        return ft.Container(
            content=ft.Icon(ft.Icons.VIDEOGAME_ASSET, size=64),
            alignment=ft.Alignment.CENTER,
        )
