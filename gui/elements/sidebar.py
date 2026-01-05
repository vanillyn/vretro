from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from ..app import VRetroApp


class Sidebar:
    def __init__(self, app: "VRetroApp", library) -> None:
        self.app = app
        self.library = library
        self.container: ft.Container = None
        self.title_text: ft.Text = None
        self.list_view: ft.ListView = None

    def create(self) -> ft.Container:
        self.title_text = ft.Text(
            "consoles",
            size=12,
            weight=ft.FontWeight.BOLD,
        )

        self.list_view = ft.ListView(
            spacing=5,
            expand=True,
        )

        self.container = ft.Container(
            width=280,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text("vretro", size=24, weight=ft.FontWeight.BOLD),
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS,
                                    on_click=lambda _: self.app.show_settings(),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=20,
                    ),
                    ft.Divider(height=1),
                    ft.Container(
                        content=self.title_text,
                        padding=ft.padding.only(left=20, right=20, top=20, bottom=10),
                    ),
                    ft.Container(
                        content=self.list_view,
                        expand=True,
                        padding=ft.padding.only(left=10, right=10),
                    ),
                ],
                spacing=0,
            ),
        )

        self.refresh()
        return self.container

    def refresh(self) -> None:
        self.list_view.controls.clear()

        if not self.app.current_console:
            self._populate_consoles()
        else:
            self._populate_games()

        self.app.page.update()

    def _populate_consoles(self) -> None:
        self.title_text.value = "consoles"
        consoles = sorted(self.library.get_consoles())

        for console_code in consoles:
            console_meta = self.library.get_console_metadata(console_code)
            games = self.library.filter_by_console(console_code)
            name = console_meta.name if console_meta else console_code

            icon_widget = self._get_console_icon(console_meta)

            content = ft.Row(
                [
                    icon_widget,
                    ft.Column(
                        [
                            ft.Text(name, size=16, weight=ft.FontWeight.W_500),
                            ft.Text(f"{len(games)} games", size=12),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=10,
            )

            btn = ft.Container(
                content=content,
                padding=15,
                border_radius=8,
                ink=True,
                on_click=lambda _, c=console_code: self.app.show_console(c),
            )
            self.list_view.controls.append(btn)

        add_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE),
                    ft.Text("install console", size=16),
                ]
            ),
            padding=15,
            border_radius=8,
            ink=True,
            on_click=lambda _: self.app.show_install_console(),
        )
        self.list_view.controls.append(add_btn)

    def _populate_games(self) -> None:
        console_meta = self.library.get_console_metadata(self.app.current_console)
        self.title_text.value = (
            console_meta.name if console_meta else self.app.current_console
        )

        back_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ARROW_BACK),
                    ft.Text("back to consoles", size=16),
                ]
            ),
            padding=15,
            border_radius=8,
            ink=True,
            on_click=lambda _: self._back_to_consoles(),
        )
        self.list_view.controls.append(back_btn)
        self.list_view.controls.append(ft.Divider(height=1))

        games = sorted(self.app.all_games, key=lambda g: g.metadata.get_title())

        for game in games:
            icon_widget = self._get_game_icon(game)

            content = ft.Row(
                [
                    icon_widget,
                    ft.Text(
                        game.metadata.get_title(),
                        size=14,
                        weight=ft.FontWeight.W_400,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=10,
            )

            selected = (
                self.app.current_game
                and self.app.current_game.metadata.code == game.metadata.code
            )

            btn = ft.Container(
                content=content,
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if selected else None,
                ink=True,
                on_click=lambda _, g=game: self.app.show_game(g),
            )
            self.list_view.controls.append(btn)

    def _back_to_consoles(self) -> None:
        self.app.current_console = None
        self.app.current_game = None
        self.app._show_welcome()
        self.refresh()

    def _get_console_icon(self, console_meta) -> ft.Control:
        if console_meta:
            console_dir = self.library.console_root / console_meta.name
            icon_path = console_dir / "graphics" / "icon.png"
            if icon_path.exists():
                return ft.Image(
                    src=str(icon_path),
                    width=32,
                    height=32,
                    fit=ft.BoxFit.CONTAIN,
                )
        return ft.Icon(ft.Icons.VIDEOGAME_ASSET)

    def _get_game_icon(self, game) -> ft.Control:
        icon_path = game.path / "graphics" / "icon.png"
        logo_path = game.path / "graphics" / "logo.png"

        if icon_path.exists():
            return ft.Image(
                src=str(icon_path),
                width=32,
                height=32,
                fit=ft.BoxFit.CONTAIN,
            )
        elif logo_path.exists():
            return ft.Image(
                src=str(logo_path),
                width=32,
                height=32,
                fit=ft.BoxFit.CONTAIN,
            )
        return ft.Icon(ft.Icons.SPORTS_ESPORTS)
