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
        self.show_details = True
        self.game_details = None
        self.is_playing = False

    def create(self) -> ft.Container:
        graphics_dir = self.game.path / "graphics"
        hero_path = graphics_dir / "hero.png"
        logo_path = graphics_dir / "logo.png"

        if not hero_path.exists():
            hero_path = self.game.path / "assets" / "hero.png"
        if not logo_path.exists():
            logo_path = self.game.path / "assets" / "logo.png"

        if self.app.config.igdb_client_id and self.app.config.igdb_client_secret:
            self._load_game_details()

        hero_section = self._create_hero(hero_path, logo_path)
        launch_section = self._create_launch_section()
        description_section = self._create_description_section()
        screenshots_section = self._create_screenshots_section()
        details_section = self._create_details_section()

        return ft.Container(
            content=ft.Column(
                [
                    hero_section,
                    ft.Column(
                        [
                            launch_section,
                            description_section,
                            screenshots_section,
                            details_section,
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                        spacing=20,
                    ),
                ],
                spacing=0,
                tight=True,
            ),
            expand=True,
            padding=0,
        )

    def _create_hero(self, hero_path, logo_path) -> ft.Control:
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
                            height=300,
                            fit=ft.BoxFit.COVER,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Container(expand=True),
                                    logo_widget,
                                ],
                                spacing=0,
                            ),
                            padding=40,
                            width=float("inf"),
                            height=300,
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
                    ]
                ),
                padding=40,
            )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        self.game.metadata.get_title(),
                        size=48,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(expand=True),
                ]
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

        self.launch_button = ft.FilledButton(
            "launch",
            icon=ft.Icons.PLAY_ARROW,
            on_click=lambda _: self._launch(),
            height=70,
            style=ft.ButtonStyle(
                text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD),
            ),
        )

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
                    self.launch_button,
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

    def _create_screenshots_section(self) -> ft.Container:
        if not self.game_details or not self.game_details.screenshots:
            return ft.Container()

        screenshot_list = ft.Row(
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        )

        for i, url in enumerate(self.game_details.screenshots[:6]):
            screenshot_list.controls.append(
                ft.Container(
                    content=ft.Image(
                        src=url,
                        width=300,
                        height=170,
                        fit=ft.BoxFit.COVER,
                        border_radius=8,
                    ),
                    ink=True,
                    on_click=lambda _, u=url: self._open_url(u),
                )
            )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(
                            "screenshots",
                            size=18,
                            weight=ft.FontWeight.W_500,
                        ),
                        padding=ft.Padding.only(left=40, right=40, bottom=10),
                    ),
                    ft.Container(
                        content=screenshot_list,
                        padding=ft.Padding.only(left=40, right=40),
                    ),
                ]
            )
        )

    def _create_description_section(self) -> ft.Container:
        if not self.game_details:
            return ft.Container()

        content = []

        if self.game_details.genres:
            content.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(
                                    genre,
                                    size=12,
                                    weight=ft.FontWeight.W_400,
                                ),
                                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                border_radius=16,
                            )
                            for genre in self.game_details.genres
                        ],
                        spacing=8,
                        wrap=True,
                    ),
                    padding=ft.Padding.only(bottom=15),
                )
            )

        if self.game_details.summary:
            content.append(
                ft.Text(
                    self.game_details.summary,
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )

        if not content:
            return ft.Container()

        return ft.Container(
            content=ft.Column(content, spacing=10),
            padding=ft.Padding.only(left=40, right=40),
        )

    def _create_details_section(self) -> ft.Container:
        publisher = (
            list(self.game.metadata.publisher.values())[0]
            if self.game.metadata.publisher
            else "unknown"
        )

        console_meta = self.app.library.get_console_metadata(self.game.metadata.console)

        detail_rows = []

        detail_rows.append(
            self._detail_item(
                "console",
                console_meta.name if console_meta else self.game.metadata.console,
            )
        )

        if self.game_details and self.game_details.genres:
            detail_rows.append(
                self._detail_item("genres", " • ".join(self.game_details.genres))
            )

        detail_rows.append(self._detail_item("year", str(self.game.metadata.year)))
        detail_rows.append(self._detail_item("publisher", publisher))
        detail_rows.append(self._detail_item("region", self.game.metadata.region))

        if console_meta:
            detail_rows.append(
                self._detail_item("emulator", console_meta.emulator.name)
            )

        if self.game_details and self.game_details.rating:
            detail_rows.append(
                self._detail_item("rating", f"{self.game_details.rating:.1f}/100")
            )

        dlc_dir = self.game.resources_path / "dlc"
        if dlc_dir.exists() and any(dlc_dir.iterdir()):
            detail_rows.append(
                self._detail_item("dlc", f"{len(list(dlc_dir.iterdir()))} files")
            )

        updates_dir = self.game.resources_path / "updates"
        if updates_dir.exists() and any(updates_dir.iterdir()):
            detail_rows.append(
                self._detail_item(
                    "updates", f"{len(list(updates_dir.iterdir()))} files"
                )
            )

        self.details_content = ft.Container(
            content=ft.Column(
                detail_rows,
                spacing=15,
            ),
            visible=True,
            padding=ft.Padding.only(top=10),
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
                                    ft.Icons.EXPAND_LESS
                                    if self.show_details
                                    else ft.Icons.EXPAND_MORE,
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
            padding=ft.Padding.only(left=40, right=40, bottom=40),
        )

    def _detail_item(self, label: str, value: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Text(
                            label,
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        width=100,
                    ),
                    ft.Text(
                        value,
                        size=14,
                        weight=ft.FontWeight.W_400,
                    ),
                ],
                spacing=20,
            ),
            padding=ft.Padding.only(left=10),
        )

    def _toggle_details(self) -> None:
        self.show_details = not self.show_details
        self.details_content.visible = self.show_details
        self.app.page.update()

    def _load_game_details(self) -> None:
        if self.game.metadata.id > 0:
            details = self.app.db.get_game_details(self.game.metadata.id)
            if details:
                self.game_details = details

    def _open_url(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    def _launch(self, fullscreen: bool = None, debug: bool = False) -> None:
        if self.is_playing:
            return

        self.is_playing = True
        self.launch_button.text = "playing"
        self.launch_button.icon = ft.Icons.STOP
        self.launch_button.disabled = False
        self.app.page.update()

        success = launch_game(
            self.game,
            self.app.config,
            self.app.library,
            fullscreen=fullscreen,
            verbose=False,
            debug=debug,
        )

        self.is_playing = False
        self.launch_button.text = "launch"
        self.launch_button.icon = ft.Icons.PLAY_ARROW

        if success:
            self.app.library.scan(verbose=False)
            self.app.show_game(self.game)
        else:
            self.app.page.update()
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
