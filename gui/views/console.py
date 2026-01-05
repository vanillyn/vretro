import random
from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from gui.app import VRetroApp


class ConsoleView:
    def __init__(self, app: "VRetroApp", console_meta, games: list) -> None:
        self.app = app
        self.console_meta = console_meta
        self.games = games
        self.filtered_games = games.copy()

    def create(self) -> ft.Column:
        search_bar = ft.TextField(
            hint_text="search games...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search,
            border_radius=20,
        )

        self.game_grid = ft.GridView(
            expand=True,
            runs_count=4,
            max_extent=200,
            child_aspect_ratio=0.7,
            spacing=15,
            run_spacing=15,
        )

        self._populate_grid()

        header = self._create_header()

        return ft.Column(
            [
                header,
                ft.Container(height=20),
                ft.Container(
                    content=search_bar, padding=ft.padding.only(left=30, right=30)
                ),
                ft.Container(height=10),
                ft.Container(
                    content=self.game_grid,
                    padding=ft.padding.only(left=30, right=30, bottom=30),
                    expand=True,
                ),
            ],
            spacing=0,
        )

    def _create_header(self) -> ft.Control:
        console_dir = self.app.library.console_root / self.console_meta.name
        hero_path = console_dir / "graphics" / "hero.png"
        logo_path = console_dir / "graphics" / "logo.png"

        if not hero_path.exists():
            hero_path = self._get_random_game_hero()

        if hero_path and hero_path.exists():
            stack_children = [
                ft.Image(
                    src=str(hero_path),
                    width=float("inf"),
                    height=300,
                    fit=ft.BoxFit.COVER,
                ),
                ft.Container(
                    width=float("inf"),
                    height=300,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_CENTER,
                        end=ft.Alignment.BOTTOM_CENTER,
                        colors=["#00000000", "#000000CC"],
                    ),
                ),
            ]

            if logo_path.exists():
                stack_children.append(
                    ft.Container(
                        content=ft.Image(
                            src=str(logo_path),
                            width=400,
                            fit=ft.BoxFit.CONTAIN,
                        ),
                        alignment=ft.Alignment.BOTTOM_LEFT,
                        padding=40,
                    )
                )
            else:
                stack_children.append(
                    ft.Container(
                        content=ft.Text(
                            self.console_meta.name,
                            size=48,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        alignment=ft.Alignment.BOTTOM_LEFT,
                        padding=40,
                    )
                )

            stack_children.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.INFO_OUTLINE,
                                icon_color=ft.Colors.WHITE,
                                on_click=lambda _: self._show_console_info(),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.IMAGE_SEARCH,
                                icon_color=ft.Colors.WHITE,
                                on_click=lambda _: self._download_console_artwork(),
                                tooltip="download console artwork",
                            ),
                        ]
                    ),
                    alignment=ft.Alignment.TOP_RIGHT,
                    padding=20,
                )
            )

            return ft.Stack(stack_children, width=float("inf"), height=300)

        if logo_path.exists():
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Image(
                            src=str(logo_path),
                            width=400,
                            fit=ft.BoxFit.CONTAIN,
                        ),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.INFO_OUTLINE,
                            on_click=lambda _: self._show_console_info(),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.IMAGE_SEARCH,
                            on_click=lambda _: self._download_console_artwork(),
                            tooltip="download console artwork",
                        ),
                    ]
                ),
                padding=40,
            )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        self.console_meta.name,
                        size=48,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        on_click=lambda _: self._show_console_info(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.IMAGE_SEARCH,
                        on_click=lambda _: self._download_console_artwork(),
                        tooltip="download console artwork",
                    ),
                ]
            ),
            padding=40,
        )

    def _get_random_game_hero(self) -> Path:
        if not self.games:
            return None

        game = random.choice(self.games)
        hero_path = game.path / "graphics" / "hero.png"

        if hero_path.exists():
            return hero_path

        for game in self.games:
            hero_path = game.path / "graphics" / "hero.png"
            if hero_path.exists():
                return hero_path

        return None

    def _populate_grid(self) -> None:
        self.game_grid.controls.clear()

        for game in self.filtered_games:
            card = self._create_game_card(game)
            self.game_grid.controls.append(card)

        has_sources = self._check_sources_available()

        if has_sources:
            add_btn = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.ADD_CIRCLE_OUTLINE,
                            size=48,
                            color=ft.Colors.PRIMARY,
                        ),
                        ft.Text(
                            "install game", size=14, text_align=ft.TextAlign.CENTER
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                border=ft.border.all(2, ft.Colors.OUTLINE),
                border_radius=12,
                ink=True,
                on_click=lambda _: self.app.show_install_game(),
            )
            self.game_grid.controls.append(add_btn)
        else:
            warning = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.WARNING_OUTLINED,
                            size=48,
                            color=ft.Colors.AMBER,
                        ),
                        ft.Text(
                            "no sources available",
                            size=14,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "add a vrdb source in settings",
                            size=12,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=5,
                ),
                border=ft.border.all(2, ft.Colors.AMBER),
                border_radius=12,
                padding=15,
            )
            self.game_grid.controls.append(warning)

    def _create_game_card(self, game) -> ft.Container:
        graphics_dir = game.path / "graphics"
        grid_path = graphics_dir / "grid.png"

        if not grid_path.exists():
            assets_dir = game.path / "assets"
            grid_path = assets_dir / "grid.png"

        if grid_path.exists():
            image = ft.Image(src=str(grid_path), fit=ft.BoxFit.COVER, border_radius=8)
            show_title = False
        else:
            thumb_path = game.get_thumbnail_path()
            if thumb_path and thumb_path.exists():
                image = ft.Image(
                    src=str(thumb_path), fit=ft.BoxFit.COVER, border_radius=8
                )
                show_title = True
            else:
                image = ft.Container(
                    content=ft.Icon(ft.Icons.VIDEOGAME_ASSET, size=48),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=8,
                    alignment=ft.Alignment.CENTER,
                )
                show_title = True

        controls = [ft.Container(content=image, expand=True)]

        if show_title:
            controls.append(
                ft.Container(
                    content=ft.Text(
                        game.metadata.get_title(),
                        size=14,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    padding=10,
                )
            )

        return ft.Container(
            content=ft.Column(controls, spacing=0),
            border_radius=12,
            ink=True,
            on_click=lambda _, g=game: self.app.show_game(g),
        )

    def _check_sources_available(self) -> bool:
        console_code = self.app.current_console.upper()
        vrdb_console = self.app.sources.vrdb.get_console(console_code)

        if not vrdb_console:
            return False

        return len(vrdb_console.games) > 0

    def _on_search(self, e) -> None:
        query = e.control.value.lower()

        if not query:
            self.filtered_games = self.games.copy()
        else:
            self.filtered_games = [
                g for g in self.games if query in g.metadata.get_title().lower()
            ]

        self._populate_grid()
        self.app.page.update()

    def _show_console_info(self) -> None:
        from ..elements.dialogs import ConsoleInfoDialog

        dialog = ConsoleInfoDialog(self.app.page, self.console_meta, self.app.library)
        self.app.page.show_dialog(dialog.create())

    def _download_console_artwork(self) -> None:
        if not self.app.steamgrid.api_key:
            self._show_error(
                "api key required",
                "steamgriddb api key not configured.\n\nadd it in settings.",
            )
            return

        from ..elements.dialogs import ConsoleArtworkDialog

        dialog = ConsoleArtworkDialog(
            self.app.page,
            self.console_meta,
            self.app.steamgrid,
            self.app.library,
            lambda: self.app.show_console(self.app.current_console),
        )
        self.app.page.show_dialog(dialog.create())

    def _show_error(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("ok", on_click=lambda _: self.app.page.pop_dialog()),
            ],
        )
        self.app.page.show_dialog(dialog)
