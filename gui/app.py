import os
import sys
from pathlib import Path
from typing import Optional

import flet as ft

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.config import VRetroConfig, get_config_path
from src.data.database import OnlineDatabase
from src.data.library import GameLibrary
from src.util.sources import SourceManager

from .elements.dialogs import (
    FirstTimeSetupDialog,
    InstallConsoleDialog,
    InstallGameDialog,
    SettingsDialog,
)
from .elements.downloads import DownloadsPanel
from .elements.sidebar import Sidebar
from .util.downloads import DownloadManager
from .util.steamgrid import SteamGridDB
from .util.theme import ThemeManager
from .views.console import ConsoleView
from .views.game import GameView
from .views.welcome import WelcomeView


class VRetroApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.title = "vretro"
        self.page.padding = 0
        self.page.window.icon = "gui/assets/logo.png"

        config_path = get_config_path()
        if not config_path.exists():
            self._show_first_time_setup()
            return

        self._initialize()
        self._apply_theme()
        self._setup_ui()
        self._load_library()

    def _initialize(self) -> None:
        self.config = VRetroConfig.load()
        self.theme_manager = ThemeManager()
        self.theme_manager.set_theme_mode(self.config.theme_mode)
        if self.config.primary_color:
            self.theme_manager.set_primary_color(self.config.primary_color)

        self.library = GameLibrary(self.config.get_games_root())
        self.sources = SourceManager()
        self.db = OnlineDatabase(self.config)
        self.steamgrid = SteamGridDB()
        self.steamgrid.api_key = self.config.steamgrid_api_key

        self.download_manager = DownloadManager(
            self.library, self.sources, self.db, self.steamgrid
        )

        self.download_manager.add_callback(self._on_download_complete)

        self.current_console: Optional[str] = None
        self.current_game = None
        self.all_games: list = []

    def _apply_theme(self) -> None:
        self.page.theme_mode = self.theme_manager.get_theme_mode()
        theme = self.theme_manager.create_theme()
        self.page.theme = theme
        self.page.dark_theme = theme
        self.page.update()

    def _show_first_time_setup(self) -> None:
        dialog = FirstTimeSetupDialog(self.page, self._on_setup_complete)
        self.page.show_dialog(dialog.create())

    def _on_setup_complete(self) -> None:
        self._initialize()
        self._apply_theme()
        self._setup_ui()
        self._load_library()

    def _setup_ui(self) -> None:
        self.sidebar = Sidebar(self, self.library)
        self.main_content = ft.Container(expand=True)
        self.downloads_panel = DownloadsPanel(self.page, self.download_manager)

        self.page.add(
            ft.Row(
                [
                    self.sidebar.create(self.downloads_panel),
                    ft.VerticalDivider(width=1),
                    self.main_content,
                ],
                spacing=0,
                expand=True,
            )
        )

        self._show_welcome()

    def _load_library(self) -> None:
        self.library.scan(verbose=False)
        self.sidebar.refresh()

    def _show_welcome(self) -> None:
        self.current_console = None
        self.current_game = None
        if self.config.theme_mode == "dynamic":
            self.theme_manager.set_dynamic_source(None)
            self._apply_theme()
        view = WelcomeView(self)
        self.main_content.content = view.create()
        self.page.update()

    def show_console(self, console_code: str) -> None:
        self.current_console = console_code
        self.current_game = None

        console_meta = self.library.get_console_metadata(console_code)
        games = self.library.filter_by_console(console_code)
        self.all_games = sorted(games, key=lambda g: g.metadata.get_title())

        if self.config.theme_mode == "dynamic":
            console_dir = self.library.console_root / console_meta.name
            hero_path = console_dir / "graphics" / "hero.png"
            if hero_path.exists():
                self.theme_manager.set_dynamic_source(hero_path)
                self._apply_theme()

        view = ConsoleView(self, console_meta, self.all_games)
        self.main_content.content = view.create()
        self.sidebar.refresh()
        self.page.update()

    def show_game(self, game) -> None:
        self.current_game = game

        if self.config.theme_mode == "dynamic":
            hero_path = game.path / "graphics" / "hero.png"
            if hero_path.exists():
                self.theme_manager.set_dynamic_source(hero_path)
                self._apply_theme()

        view = GameView(self, game)
        self.main_content.content = view.create()
        self.sidebar.refresh()
        self.page.update()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.page, self.config, self._on_settings_saved)
        self.page.show_dialog(dialog.create())

    def _on_settings_saved(self) -> None:
        self.config = VRetroConfig.load()
        self.theme_manager.set_theme_mode(self.config.theme_mode)
        if self.config.primary_color:
            self.theme_manager.set_primary_color(self.config.primary_color)
        self._apply_theme()
        self.steamgrid.api_key = self.config.steamgrid_api_key
        self.library = GameLibrary(self.config.get_games_root())
        self._load_library()

    def show_install_console(self) -> None:
        dialog = InstallConsoleDialog(
            self.page, self.library, self.sources, self.steamgrid, self._load_library
        )
        self.page.show_dialog(dialog.create())

    def show_install_game(self) -> None:
        if not self.current_console:
            return
        dialog = InstallGameDialog(
            self.page,
            self.current_console,
            self.library,
            self.sources,
            self.db,
            self.steamgrid,
            self.download_manager,
            lambda: self.show_console(self.current_console),
        )
        self.page.show_dialog(dialog.create())

    def _on_download_complete(self):
        try:
            active_tasks = self.download_manager.get_active_tasks()

            if len(active_tasks) == 0:
                self._load_library()

                if self.current_console:
                    self.show_console(self.current_console)
                else:
                    self._show_welcome()
        except Exception:
            pass
