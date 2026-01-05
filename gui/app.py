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
from .elements.sidebar import Sidebar
from .util.steamgrid import SteamGridDB
from .views.console import ConsoleView
from .views.game import GameView
from .views.welcome import WelcomeView


class VRetroApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.title = "vretro"
        self.page.padding = 0
        self.page.theme_mode = ft.ThemeMode.DARK

        config_path = get_config_path()
        if not config_path.exists():
            self._show_first_time_setup()
            return

        self._initialize()
        self._setup_ui()
        self._load_library()

    def _initialize(self) -> None:
        self.config = VRetroConfig.load()
        self.library = GameLibrary(self.config.get_games_root())
        self.sources = SourceManager()
        self.db = OnlineDatabase(self.config)
        self.steamgrid = SteamGridDB()
        self.steamgrid.api_key = getattr(self.config, "steamgrid_api_key", None)

        self.current_console: Optional[str] = None
        self.current_game = None
        self.all_games: list = []

    def _show_first_time_setup(self) -> None:
        dialog = FirstTimeSetupDialog(self.page, self._on_setup_complete)
        self.page.show_dialog(dialog.create())

    def _on_setup_complete(self) -> None:
        self._initialize()
        self._setup_ui()
        self._load_library()

    def _setup_ui(self) -> None:
        self.sidebar = Sidebar(self, self.library)
        self.main_content = ft.Container(expand=True)

        self.page.add(
            ft.Row(
                [
                    self.sidebar.create(),
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
        view = WelcomeView(self)
        self.main_content.content = view.create()
        self.page.update()

    def show_console(self, console_code: str) -> None:
        self.current_console = console_code
        self.current_game = None

        console_meta = self.library.get_console_metadata(console_code)
        games = self.library.filter_by_console(console_code)
        self.all_games = sorted(games, key=lambda g: g.metadata.get_title())

        view = ConsoleView(self, console_meta, self.all_games)
        self.main_content.content = view.create()
        self.sidebar.refresh()
        self.page.update()

    def show_game(self, game) -> None:
        self.current_game = game
        view = GameView(self, game)
        self.main_content.content = view.create()
        self.sidebar.refresh()
        self.page.update()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.page, self.config, self._on_settings_saved)
        self.page.show_dialog(dialog.create())

    def _on_settings_saved(self) -> None:
        self.library = GameLibrary(self.config.get_games_root())
        self._load_library()

    def show_install_console(self) -> None:
        dialog = InstallConsoleDialog(
            self.page, self.library, self.sources, self._load_library
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
            lambda: self.show_console(self.current_console),
        )
        self.page.show_dialog(dialog.create())
