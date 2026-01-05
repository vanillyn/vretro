import subprocess
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from gui.app import VRetroApp

from src.util.launch import launch_game


class GameView:
    def __init__(self, app: "VRetroApp", game) -> None:
        self.app = app
        self.game = game
        self.show_details = False

    def create(self) -> ft.Column:
        graphics_dir = self.game.path / "graphics"
        hero_path = graphics_dir / "hero.png"
        logo_path = graphics_dir / "logo.png"

        if not hero_path.exists():
            hero_path = self.game.path / "assets" / "hero.png"
        if not logo_path.exists():
            logo_path = self.game.path / "assets" / "logo.png"

        hero_section = self._create_hero(hero_path, logo_path)
        launch_section = self._create_launch_section()
        details_section = self._create_details_section()

        return ft.Column(
            [
                hero_section,
                launch_section,
                details_section,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )

    def _create_hero(self, hero_path, logo_path) -> ft.Container:
        if hero_path.exists():
            if logo_path.exists():
                logo_widget = ft.Image(
                    src=str(logo_path),
                    width=400,
                    fit=ft.BoxFit.CONTAIN,
                )
            else:
                logo_widget = ft.Text(
                    self.game.metadata.get_title(),
                    size=48,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                )

            return ft.Container(
                content=ft.Stack(
                    [
                        ft.Image(
                            src=str(hero_path),
                            width=float("inf"),
                            height=400,
                            fit=ft.BoxFit.COVER,
                        ),
                        ft.Container(
                            width=float("inf"),
                            height=400,
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment.TOP_CENTER,
                                end=ft.Alignment.BOTTOM_CENTER,
                                colors=["#00000000", "#000000CC"],
                            ),
                        ),
                        ft.Container(
                            content=logo_widget,
                            padding=40,
                            alignment=ft.Alignment.BOTTOM_LEFT,
                            width=float("inf"),
                            height=400,
                        ),
                    ],
                    width=float("inf"),
                    height=400,
                ),
                width=float("inf"),
                height=400,
            )

        if logo_path.exists():
            return ft.Container(
                content=ft.Image(
                    src=str(logo_path),
                    width=400,
                    fit=ft.BoxFit.CONTAIN,
                ),
                padding=40,
            )

        return ft.Container(
            content=ft.Text(
                self.game.metadata.get_title(),
                size=48,
                weight=ft.FontWeight.BOLD,
            ),
            padding=40,
        )

    def _create_launch_section(self) -> ft.Container:
        playtime_seconds = getattr(self.game.metadata, "playtime", 0)

        if playtime_seconds == 0:
            playtime_str = "never played"
        else:
            hours = playtime_seconds // 3600
            minutes = (playtime_seconds % 3600) // 60

            if hours > 0:
                playtime_str = f"{hours}h {minutes}m played"
            else:
                playtime_str = f"{minutes}m played"

        options_menu = ft.PopupMenuButton(
            icon=ft.Icons.ARROW_DROP_DOWN,
            items=[
                ft.PopupMenuItem(
                    "customize game",
                    icon=ft.Icons.EDIT,
                    on_click=lambda _: self._edit_metadata(),
                ),
                ft.PopupMenuItem(
                    "manage saves",
                    icon=ft.Icons.SAVE,
                    on_click=lambda _: self._open_saves(),
                ),
                ft.PopupMenuItem(
                    "open game files",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda _: self._open_files(),
                ),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(
                    "search on igdb",
                    icon=ft.Icons.DATASET,
                    on_click=lambda _: self._search_igdb(),
                ),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(
                    "launch in fullscreen",
                    icon=ft.Icons.FULLSCREEN,
                    on_click=lambda _: self._launch(fullscreen=True),
                ),
                ft.PopupMenuItem(
                    "launch without custom variables",
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=lambda _: self._launch(debug=True),
                ),
            ],
        )

        return ft.Container(
            content=ft.Row(
                [
                    ft.FilledButton(
                        "launch",
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=lambda _: self._launch(),
                        height=70,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD),
                        ),
                    ),
                    options_menu,
                    ft.IconButton(
                        icon=ft.Icons.IMAGE_SEARCH,
                        on_click=lambda _: self._download_artwork(),
                        tooltip="download artwork",
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        playtime_str,
                        size=16,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=40,
        )

    def _create_details_section(self) -> ft.Container:
        publisher = (
            list(self.game.metadata.publisher.values())[0]
            if self.game.metadata.publisher
            else "unknown"
        )

        console_meta = self.app.library.get_console_metadata(self.game.metadata.console)

        detail_rows = [
            self._detail_row(
                "console",
                console_meta.name if console_meta else self.game.metadata.console,
            ),
            self._detail_row("year", str(self.game.metadata.year)),
            self._detail_row("publisher", publisher),
            self._detail_row("region", self.game.metadata.region),
        ]

        if console_meta:
            detail_rows.append(self._detail_row("emulator", console_meta.emulator.name))

        dlc_dir = self.game.resources_path / "dlc"
        if dlc_dir.exists() and any(dlc_dir.iterdir()):
            detail_rows.append(
                self._detail_row(
                    "dlc", f"{len(list(dlc_dir.iterdir()))} files", ft.Icons.EXTENSION
                )
            )

        updates_dir = self.game.resources_path / "updates"
        if updates_dir.exists() and any(updates_dir.iterdir()):
            detail_rows.append(
                self._detail_row(
                    "updates",
                    f"{len(list(updates_dir.iterdir()))} files",
                    ft.Icons.SYSTEM_UPDATE,
                )
            )

        self.details_content = ft.Column(
            detail_rows,
            visible=self.show_details,
            spacing=12,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=20),
                                ft.Text("details", size=18, weight=ft.FontWeight.W_500),
                                ft.Container(expand=True),
                                ft.Icon(
                                    ft.Icons.EXPAND_MORE
                                    if not self.show_details
                                    else ft.Icons.EXPAND_LESS,
                                    size=20,
                                ),
                            ],
                        ),
                        ink=True,
                        on_click=lambda _: self._toggle_details(),
                        padding=10,
                        border_radius=8,
                    ),
                    self.details_content,
                ]
            ),
            padding=ft.padding.only(left=40, right=40, bottom=40),
        )

    def _detail_row(self, label: str, value: str, icon=None) -> ft.Container:
        label_parts = []
        if icon:
            label_parts.append(ft.Icon(icon, size=16))
        label_parts.append(
            ft.Text(
                label,
                size=14,
                weight=ft.FontWeight.W_500,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Row(
                            label_parts,
                            spacing=8,
                        ),
                        width=120,
                    ),
                    ft.Text(
                        value,
                        size=14,
                        weight=ft.FontWeight.W_400,
                    ),
                ],
                spacing=20,
            ),
            padding=ft.padding.only(left=10),
        )

    def _toggle_details(self) -> None:
        self.show_details = not self.show_details
        self.details_content.visible = self.show_details
        self.app.page.update()

    def _launch(self, fullscreen: bool = None, debug: bool = False) -> None:
        success = launch_game(
            self.game,
            self.app.config,
            self.app.library,
            fullscreen=fullscreen,
            verbose=False,
            debug=debug,
        )

        if success:
            self.app.library.scan(verbose=False)
            self.app.show_game(self.game)
        else:
            self._show_error(
                "launch failed", f"couldn't launch {self.game.metadata.get_title()}"
            )

    def _edit_metadata(self) -> None:
        from ..elements.dialogs import EditMetadataDialog

        dialog = EditMetadataDialog(
            self.app.page, self.game, lambda: self.app.show_game(self.game)
        )
        self.app.page.show_dialog(dialog.create())

    def _open_saves(self) -> None:
        if self.game.saves_path.exists():
            subprocess.Popen(["xdg-open", str(self.game.saves_path)])
        else:
            self._show_info("no saves", "no save directory found")

    def _open_files(self) -> None:
        if self.game.resources_path.exists():
            subprocess.Popen(["xdg-open", str(self.game.resources_path)])
        else:
            self._show_info("not found", "resources directory not found")

    def _search_igdb(self) -> None:
        """Search IGDB for this game and update metadata"""
        if not self.app.config.igdb_client_id or not self.app.config.igdb_client_secret:
            self._show_error(
                "igdb not configured",
                "igdb api credentials not configured.\n\nadd them in settings.",
            )
            return

        from ..elements.dialogs import IGDBSearchDialog

        dialog = IGDBSearchDialog(
            self.app.page,
            self.game,
            self.app.db,
            lambda: self.app.show_game(self.game),
        )
        self.app.page.show_dialog(dialog.create())

    def _download_artwork(self) -> None:
        if not self.app.steamgrid.api_key:
            self._show_error(
                "api key required",
                "steamgriddb api key not configured.\n\nadd it in settings.",
            )
            return

        from ..elements.dialogs import ArtworkDialog

        dialog = ArtworkDialog(
            self.app.page,
            self.game,
            self.app.steamgrid,
            lambda: self.app.show_game(self.game),
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

    def _show_info(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("ok", on_click=lambda _: self.app.page.pop_dialog()),
            ],
        )
        self.app.page.show_dialog(dialog)
