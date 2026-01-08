import random
from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from gui.app import VRetroApp
from gui.elements.card import GameCard


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
                    content=search_bar, padding=ft.Padding.only(left=30, right=30)
                ),
                ft.Container(height=10),
                ft.Container(
                    content=self.game_grid,
                    padding=ft.Padding.only(left=30, right=30, bottom=30),
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
            if logo_path.exists():
                logo_widget = ft.Image(
                    src=str(logo_path),
                    width=400,
                    height=200,
                    fit=ft.BoxFit.CONTAIN,
                )
            else:
                logo_widget = ft.Text(
                    self.console_meta.name,
                    size=48,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                )

            action_buttons = ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: self._show_console_info(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: self._show_console_config(),
                        tooltip="console settings",
                    ),
                    ft.IconButton(
                        icon=ft.Icons.COMPRESS,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: self._bulk_compress_games(),
                        tooltip="bulk compress games",
                    ),
                    ft.IconButton(
                        icon=ft.Icons.IMAGE_SEARCH,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: self._download_console_artwork(),
                        tooltip="download console artwork",
                    ),
                ]
            )

            return ft.Container(
                content=ft.Stack(
                    [
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
                                colors=["#00000000", "#000000DD"],
                            ),
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Container(
                                        content=action_buttons,
                                        alignment=ft.Alignment.TOP_RIGHT,
                                    ),
                                    ft.Container(expand=True),
                                    logo_widget,
                                ],
                                spacing=0,
                            ),
                            padding=40,
                            width=float("inf"),
                            height=300,
                        ),
                    ],
                    width=float("inf"),
                    height=300,
                ),
                width=float("inf"),
                height=300,
            )

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
                            icon=ft.Icons.SETTINGS,
                            on_click=lambda _: self._show_console_config(),
                            tooltip="console settings",
                        ),
                        ft.IconButton(
                            icon=ft.Icons.COMPRESS,
                            on_click=lambda _: self._bulk_compress_games(),
                            tooltip="bulk compress games",
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
                        icon=ft.Icons.SETTINGS,
                        on_click=lambda _: self._show_console_config(),
                        tooltip="console settings",
                    ),
                    ft.IconButton(
                        icon=ft.Icons.COMPRESS,
                        on_click=lambda _: self._bulk_compress_games(),
                        tooltip="bulk compress games",
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
            card = GameCard(game, lambda _, g=game: self.app.show_game(g)).create()
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
                border=ft.Border.all(2, ft.Colors.OUTLINE),
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
                border=ft.Border.all(2, ft.Colors.AMBER),
                border_radius=12,
                padding=15,
            )
            self.game_grid.controls.append(warning)

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

    def _bulk_compress_games(self) -> None:
        from src.util.compression import is_compressed

        uncompressed_games = []
        for game in self.games:
            resources_dir = game.path / "resources"
            if not resources_dir.exists():
                continue

            base_files = list(resources_dir.glob("base.*"))
            if not base_files:
                continue

            if not any(is_compressed(f) for f in base_files):
                uncompressed_games.append(game)

        if not uncompressed_games:
            dialog = ft.AlertDialog(
                title=ft.Text("no games to compress"),
                content=ft.Text("all games are already compressed"),
                actions=[
                    ft.TextButton("ok", on_click=lambda _: self.app.page.pop_dialog())
                ],
            )
            self.app.page.show_dialog(dialog)
            return

        self.progress_text = ft.Text(
            f"preparing to compress {len(uncompressed_games)} games..."
        )
        self.progress_bar = ft.ProgressBar(value=0)

        progress_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("bulk compression"),
            content=ft.Container(
                content=ft.Column(
                    [
                        self.progress_text,
                        self.progress_bar,
                    ],
                    spacing=20,
                ),
                width=400,
            ),
        )

        self.app.page.show_dialog(progress_dialog)

        import threading

        from src.util.compression import compress_game_directory

        def compress_all():
            total = len(uncompressed_games)
            success_count = 0

            for i, game in enumerate(uncompressed_games):
                self.progress_text.value = (
                    f"compressing {game.metadata.get_title()}... ({i + 1}/{total})"
                )
                self.progress_bar.value = i / total
                self.app.page.update()

                success = compress_game_directory(game.path, "7z", 9, verbose=False)
                if success:
                    success_count += 1

            self.progress_bar.value = 1.0
            self.app.page.update()

            self.app.page.pop_dialog()

            result_dialog = ft.AlertDialog(
                title=ft.Text("compression complete"),
                content=ft.Text(
                    f"compressed {success_count} of {total} games\n\n"
                    f"saved space by compressing rom files"
                ),
                actions=[
                    ft.TextButton("ok", on_click=lambda _: self.app.page.pop_dialog())
                ],
            )
            self.app.page.show_dialog(result_dialog)

        threading.Thread(target=compress_all, daemon=True).start()

    def _show_console_info(self) -> None:
        from ..elements.dialogs import ConsoleInfoDialog

        dialog = ConsoleInfoDialog(self.app.page, self.console_meta, self.app.library)
        self.app.page.show_dialog(dialog.create())

    def _show_console_config(self) -> None:
        from ..elements.dialogs import ConsoleConfigDialog

        dialog = ConsoleConfigDialog(
            self.app.page,
            self.console_meta,
            self.app.library,
            lambda: self.app.show_console(self.app.current_console),
        )
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
