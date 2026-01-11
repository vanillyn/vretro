import subprocess
import threading
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from gui.app import VRetroApp

from src.util.compression import (
    compress_game_directory,
    decompress_game_directory,
    is_compressed,
)
from src.util.launch import launch_game
from src.util.mods import ModManager


class GameView:
    def __init__(self, app: "VRetroApp", game) -> None:
        self.app = app
        self.game = game
        self.show_details = True
        self.game_details = None
        self.is_playing = False
        self.mod_manager = ModManager(game.path)
        self.achievements = []
        self.user_progress = None

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

        if self.app.config.retroachievements_api_key:
            threading.Thread(target=self._load_achievements, daemon=True).start()

        hero_section = self._create_hero(hero_path, logo_path)
        launch_section = self._create_launch_section()
        description_section = self._create_description_section()
        settings_section = self._create_quick_settings_row()
        self.achievements_container = ft.Container()
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
                            settings_section,
                            self.achievements_container,
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

    def _load_achievements(self) -> None:
        import logging

        from src.util.achievements import RetroAchievementsAPI

        logger = logging.getLogger(__name__)
        logger.info(f"loading achievements for {self.game.metadata.get_title()}")

        ra_api = RetroAchievementsAPI(
            self.app.config.retroachievements_api_key,
            self.app.config.retroachievements_username,
        )

        console_meta = self.app.library.get_console_metadata(self.game.metadata.console)

        if not self.game.metadata.retroachievements_id:
            if console_meta and console_meta.retroachievements_console_id:
                logger.info(
                    f"searching retroachievements with console id {console_meta.retroachievements_console_id}"
                )
                game_id = ra_api.search_game(
                    console_meta.retroachievements_console_id,
                    self.game.metadata.get_title(),
                )

                if game_id:
                    logger.info(f"found retroachievements game id: {game_id}")
                    self.game.metadata.retroachievements_id = game_id
                    self.game.metadata.save(self.game.path / "metadata.json")
                else:
                    logger.warning(
                        f"could not find retroachievements game for {self.game.metadata.get_title()}"
                    )
                    return
            else:
                logger.warning(
                    f"console {self.game.metadata.console} has no retroachievements_console_id"
                )
                return

        if self.game.metadata.retroachievements_id:
            logger.info(
                f"fetching achievements for game id {self.game.metadata.retroachievements_id}"
            )
            self.achievements = ra_api.get_game_achievements(
                self.game.metadata.retroachievements_id
            )
            self.user_progress = ra_api.get_user_progress(
                self.game.metadata.retroachievements_id
            )

            if self.achievements or self.user_progress:
                logger.info(f"loaded {len(self.achievements)} achievements")
                self.achievements_container.content = (
                    self._create_achievements_section()
                )
                if self.app.page:
                    self.app.page.update()
            else:
                logger.warning("no achievements or progress data received")

    def _create_achievements_section(self) -> ft.Column:
        if not self.achievements and not self.user_progress:
            return ft.Column()

        content = []

        if self.user_progress:
            progress_bar = ft.ProgressBar(
                value=self.user_progress.earned_hardcore
                / max(self.user_progress.total_achievements, 1),
                height=8,
                border_radius=4,
            )

            progress_text = ft.Text(
                f"{self.user_progress.earned_hardcore}/{self.user_progress.total_achievements} achievements • {self.user_progress.earned_points}/{self.user_progress.total_points} points",
                size=14,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )

            content.extend([progress_bar, ft.Container(height=10), progress_text])

        if self.achievements:
            unlocked = [a for a in self.achievements if a.unlocked]

            if unlocked:
                content.append(ft.Container(height=10))
                content.append(
                    ft.Text("recent unlocks", size=14, weight=ft.FontWeight.W_500)
                )

                recent_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=10)

                for achievement in unlocked[:10]:
                    recent_row.controls.append(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Image(
                                        src=achievement.badge_url,
                                        width=64,
                                        height=64,
                                        fit=ft.BoxFit.COVER,
                                        border_radius=8,
                                    ),
                                    ft.Text(
                                        achievement.title,
                                        size=11,
                                        max_lines=2,
                                        text_align=ft.TextAlign.CENTER,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=5,
                            ),
                            width=80,
                        )
                    )

                content.append(recent_row)

        return ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.EMOJI_EVENTS, size=20),
                            ft.Text(
                                "achievements", size=18, weight=ft.FontWeight.W_500
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=ft.Padding.only(left=40, right=40, bottom=10),
                ),
                ft.Container(
                    content=ft.Column(content, spacing=10),
                    padding=ft.Padding.only(left=40, right=40),
                ),
            ]
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
            on_click=lambda _: threading.Thread(target=self._launch).start(),
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
                    on_click=lambda _: threading.Thread(
                        target=self._launch, kwargs={"fullscreen": True}, daemon=True
                    ).start(),
                ),
                ft.PopupMenuItem(
                    "debug launch",
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=lambda _: threading.Thread(
                        target=self._launch, kwargs={"debug": True}, daemon=True
                    ).start(),
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
                    ft.IconButton(
                        icon=ft.Icons.EXTENSION,
                        on_click=lambda _: self._browse_gamebanana(),
                        tooltip="browse gamebanana mods",
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

    def _create_compression_section(self) -> ft.Container:
        resources_dir = self.game.path / "resources"
        if not resources_dir.exists():
            return ft.Container()

        base_files = list(resources_dir.glob("base.*"))
        if not base_files:
            return ft.Container()

        compressed = any(is_compressed(f) for f in base_files)

        status_icon = ft.Icon(
            ft.Icons.FOLDER_ZIP if compressed else ft.Icons.FOLDER_OPEN,
            color=ft.Colors.PRIMARY if compressed else ft.Colors.ON_SURFACE_VARIANT,
            size=20,
        )

        status_text = ft.Text(
            "compressed" if compressed else "uncompressed",
            size=14,
            color=ft.Colors.PRIMARY if compressed else ft.Colors.ON_SURFACE_VARIANT,
        )

        action_button = ft.OutlinedButton(
            "decompress" if compressed else "compress",
            icon=ft.Icons.UNFOLD_MORE if compressed else ft.Icons.COMPRESS,
            on_click=lambda _: self._toggle_compression(compressed),
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            status_icon,
                            ft.Text("storage", size=18, weight=ft.FontWeight.W_500),
                        ],
                        spacing=10,
                    ),
                    ft.Row(
                        [
                            status_text,
                            ft.Container(expand=True),
                            action_button,
                        ],
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
            padding=0,
        )

    def _create_mods_section(self) -> ft.Container:
        mods_dir = self.game.path / "mods"
        if not mods_dir.exists() or not any(mods_dir.iterdir()):
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.EXTENSION, size=20),
                                ft.Text("mods", size=18, weight=ft.FontWeight.W_500),
                            ],
                            spacing=10,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    "no mods installed",
                                    size=14,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                ft.Container(expand=True),
                                ft.OutlinedButton(
                                    "manage mods",
                                    icon=ft.Icons.SETTINGS,
                                    on_click=lambda _: self._open_mod_manager(),
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=10,
                ),
                padding=ft.Padding.only(left=40, right=40),
            )

        enabled_mods = [m for m in self.mod_manager.mods if m.enabled]
        total_mods = len(self.mod_manager.mods)

        mod_chips = []
        for mod in enabled_mods[:3]:
            mod_chips.append(
                ft.Container(
                    content=ft.Text(
                        mod.name,
                        size=12,
                        weight=ft.FontWeight.W_400,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                    border_radius=16,
                )
            )

        if len(enabled_mods) > 3:
            mod_chips.append(
                ft.Container(
                    content=ft.Text(
                        f"+{len(enabled_mods) - 3} more",
                        size=12,
                        weight=ft.FontWeight.W_400,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border_radius=16,
                )
            )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.EXTENSION,
                                size=20,
                                color=ft.Colors.PRIMARY if enabled_mods else None,
                            ),
                            ft.Text("mods", size=18, weight=ft.FontWeight.W_500),
                        ],
                        spacing=10,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                f"{len(enabled_mods)}/{total_mods} enabled",
                                size=14,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Container(expand=True),
                            ft.OutlinedButton(
                                "manage mods",
                                icon=ft.Icons.SETTINGS,
                                on_click=lambda _: self._open_mod_manager(),
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(
                        content=ft.Row(
                            mod_chips,
                            spacing=8,
                            wrap=True,
                        ),
                        padding=ft.Padding.only(top=10),
                    )
                    if mod_chips
                    else ft.Container(),
                ],
                spacing=10,
            ),
            padding=0,
        )

    def _create_quick_settings_row(self) -> ft.Control:
        compression_section = self._create_compression_section()
        mods_section = self._create_mods_section()

        compression_section.expand = True
        mods_section.expand = True

        return ft.Container(
            content=ft.Row(
                controls=[
                    compression_section,
                    ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                    mods_section,
                ],
                spacing=20,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.symmetric(horizontal=40, vertical=10),
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
                                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
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

    def _toggle_compression(self, is_compressed: bool) -> None:
        progress = ft.AlertDialog(
            modal=True,
            title=ft.Text("processing"),
            content=ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Text(
                        "decompressing..." if is_compressed else "compressing...",
                        size=14,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
            ),
        )

        self.app.page.show_dialog(progress)

        def process():
            if is_compressed:
                success = decompress_game_directory(self.game.path, verbose=False)
                action = "decompression"
            else:
                success = compress_game_directory(
                    self.game.path, "7z", 9, verbose=False
                )
                action = "compression"

            self.app.page.pop_dialog()

            if success:
                self._show_info("success", f"{action} complete")
                self.app.show_game(self.game)
            else:
                self._show_error("error", f"{action} failed")

        threading.Thread(target=process, daemon=True).start()

    def _open_mod_manager(self) -> None:
        from ..elements.dialogs import ModManagerDialog

        dialog = ModManagerDialog(
            self.app.page, self.mod_manager, lambda: self.app.show_game(self.game)
        )
        self.app.page.show_dialog(dialog.create())

    def _browse_gamebanana(self) -> None:
        from ..elements.dialogs import GameBananaDialog

        dialog = GameBananaDialog(
            self.app.page,
            self.game,
            self.mod_manager,
            lambda: self.app.show_game(self.game),
        )
        self.app.page.show_dialog(dialog.create())

    def _load_game_details(self) -> None:
        if self.game.metadata.id > 0:
            details = self.app.db.get_game_details(self.game.metadata.id)
            if details:
                self.game_details = details

    def _open_url(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    def _launch(self, fullscreen: bool = False, debug: bool = False) -> None:
        if self.is_playing:
            return

        self.is_playing = True
        self.launch_button.content = "playing"
        self.launch_button.icon = ft.Icons.STOP
        self.launch_button.disabled = True
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
        self.launch_button.content = "launch"
        self.launch_button.icon = ft.Icons.PLAY_ARROW
        self.launch_button.disabled = False

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
