import re
import sys
import threading
from pathlib import Path
from typing import Callable

import flet as ft

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.config import VRetroConfig
from src.data.console import get_console_metadata
from src.data.library import CONSOLE_EXTENSIONS, GameMetadata
from src.util.download import download_emulator


class FirstTimeSetupDialog:
    def __init__(self, page: ft.Page, on_complete: Callable) -> None:
        self.page = page
        self.on_complete = on_complete

    def create(self) -> ft.AlertDialog:
        self.dir_input = ft.TextField(
            label="games directory",
            value=str(Path.home() / "games"),
            expand=True,
        )

        self.steamgrid_input = ft.TextField(
            label="steamgriddb api key (optional)",
            hint_text="leave blank to skip",
            password=True,
            can_reveal_password=True,
        )

        return ft.AlertDialog(
            modal=True,
            title=ft.Text("welcome to vretro", size=28, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("choose where to store your game library", size=16),
                        ft.Container(height=20),
                        self.dir_input,
                        ft.Container(height=20),
                        ft.Text(
                            "steamgriddb (optional)", size=18, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text("api key for downloading game artwork", size=14),
                        self.steamgrid_input,
                    ]
                ),
                width=500,
            ),
            actions=[
                ft.TextButton("cancel", on_click=lambda _: sys.exit(0)),
                ft.FilledButton("continue", on_click=self._on_submit),
            ],
        )

    def _on_submit(self, e) -> None:
        games_dir = self.dir_input.value or str(Path.home() / "games")
        steamgrid_key = self.steamgrid_input.value.strip() or None

        config = VRetroConfig.default()
        config.games_directory = games_dir
        config.steamgrid_api_key = steamgrid_key
        config.save()

        self.page.pop_dialog()
        self.on_complete()


class ConsoleConfigDialog:
    def __init__(self, page, console_meta, library, on_save) -> None:
        self.page = page
        self.console_meta = console_meta
        self.library = library
        self.on_save = on_save

    def create(self):
        console_dir = self.library.console_root / self.console_meta.name
        emulator_dir = console_dir / "emulator"

        emulator_status = (
            "installed"
            if emulator_dir.exists() and any(emulator_dir.iterdir())
            else "not installed"
        )

        self.status_text = ft.Text(f"status: {emulator_status}")
        self.progress_bar = ft.ProgressRing(visible=False)
        self.progress_text = ft.Text("", visible=False)

        content = ft.Column(
            [
                ft.Text("emulator", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"name: {self.console_meta.emulator.name}"),
                ft.Text(f"binary: {self.console_meta.emulator.binary}"),
                self.status_text,
                ft.Container(height=20),
                self.progress_bar,
                self.progress_text,
                ft.Container(height=20),
                ft.Row(
                    [
                        ft.FilledButton(
                            "download emulator",
                            on_click=lambda _: self._download_emulator(),
                        ),
                        ft.OutlinedButton(
                            "open emulator folder",
                            on_click=lambda _: self._open_emulator_folder(),
                        ),
                    ],
                    spacing=10,
                ),
            ],
            tight=True,
        )

        if self.console_meta.emulator.requires_bios:
            content.controls.insert(
                5,
                ft.Column(
                    [
                        ft.Text(
                            "required bios files:", size=14, weight=ft.FontWeight.W_500
                        ),
                        *[
                            ft.Text(f"  • {bios}", size=12)
                            for bios in self.console_meta.emulator.bios_files
                        ],
                    ],
                    spacing=5,
                ),
            )

        return ft.AlertDialog(
            title=ft.Text(f"{self.console_meta.name} configuration"),
            content=ft.Container(content=content, width=500),
            actions=[
                ft.TextButton("close", on_click=lambda _: self.page.pop_dialog()),
            ],
        )

    def _download_emulator(self):
        if not self.console_meta.emulator.download_url:
            self._show_error("error", "no download url available")
            return

        console_dir = self.library.console_root / self.console_meta.name
        emulator_dir = console_dir / "emulator"

        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_text.value = "downloading..."
        self.page.update()

        def download_thread():
            success = download_emulator(
                self.console_meta.code,
                self.console_meta.emulator.name,
                self.console_meta.emulator.download_url,
                emulator_dir,
            )

            self.progress_bar.visible = False
            self.progress_text.visible = False

            if success:
                self.status_text.value = "status: installed"
                self._show_info("success", "emulator downloaded")
            else:
                self._show_error("error", "download failed")

            self.page.update()

        threading.Thread(target=download_thread, daemon=True).start()

    def _open_emulator_folder(self):
        import subprocess

        console_dir = self.library.console_root / self.console_meta.name
        emulator_dir = console_dir / "emulator"

        if emulator_dir.exists():
            subprocess.Popen(["xdg-open", str(emulator_dir)])
        else:
            self._show_info("not found", "emulator directory not found")

    def _show_error(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _show_info(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)


class ConsoleArtworkDialog:
    def __init__(self, page, console_meta, steamgrid, library, on_download) -> None:
        self.page = page
        self.console_meta = console_meta
        self.steamgrid = steamgrid
        self.library = library
        self.on_download = on_download

    def create(self):
        self.search_input = ft.TextField(
            label="search",
            value=self.console_meta.name,
        )

        self.results_grids = [
            ft.GridView(
                expand=True,
                runs_count=3,
                max_extent=200,
                child_aspect_ratio=1.0,
                spacing=10,
                run_spacing=10,
            )
            for _ in range(3)
        ]

        tabs = ft.Tabs(
            selected_index=0,
            length=3,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="hero"),
                            ft.Tab(label="logo"),
                            ft.Tab(label="icon"),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=self.results_grids,
                    ),
                ],
            ),
            on_change=lambda _: self._on_search(None),
        )

        self.tabs = tabs

        return ft.AlertDialog(
            title=ft.Text("download console artwork"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                self.search_input,
                                ft.IconButton(
                                    icon=ft.Icons.SEARCH,
                                    on_click=self._on_search,
                                ),
                            ]
                        ),
                        tabs,
                        ft.Container(height=10),
                    ]
                ),
                width=700,
                height=600,
            ),
            actions=[
                ft.TextButton("close", on_click=lambda _: self.page.pop_dialog()),
            ],
            on_dismiss=lambda _: self.page.pop_dialog(),
        )

    def _on_search(self, e) -> None:
        selected_index = self.tabs.selected_index
        results = self.results_grids[selected_index]
        results.controls.clear()

        games = self.steamgrid.search_game(self.search_input.value)

        if not games:
            results.controls.append(ft.Text("no results found"))
            self.page.update()
            return

        game_id = games[0].get("id")

        asset_types = ["heroes", "logos", "icons"]
        file_names = ["hero", "logo", "icon"]
        asset_type = asset_types[selected_index]
        file_name = file_names[selected_index]

        assets = self.steamgrid.get_assets(game_id, asset_type)

        for asset in assets[:12]:
            url = asset.get("thumb") or asset.get("url")
            if not url:
                continue

            card = ft.Container(
                content=ft.Image(src=url, fit=ft.BoxFit.COVER),
                border_radius=8,
                ink=True,
                on_click=lambda _,
                full_url=asset.get("url"),
                fn=file_name: self._download(full_url, fn),
            )
            results.controls.append(card)

        self.page.update()

    def _download(self, url: str, asset_type: str) -> None:
        console_dir = self.library.console_root / self.console_meta.name
        graphics_dir = console_dir / "graphics"
        graphics_dir.mkdir(parents=True, exist_ok=True)
        dest = graphics_dir / f"{asset_type}.png"

        if self.steamgrid.download_asset(url, dest):
            self.page.pop_dialog()
            self._show_info("success", f"downloaded {asset_type}")
            self.on_download()
        else:
            self._show_error("error", "download failed")

    def _show_error(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _show_info(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)


class SettingsDialog:
    def __init__(self, page: ft.Page, config: VRetroConfig, on_save: Callable) -> None:
        self.page = page
        self.config = config
        self.on_save = on_save

    def create(self) -> ft.AlertDialog:
        self.games_dir_input = ft.TextField(
            label="games directory",
            value=self.config.games_directory,
        )

        self.fullscreen_check = ft.Checkbox(
            label="fullscreen by default",
            value=self.config.fullscreen,
        )

        self.region_dropdown = ft.Dropdown(
            label="preferred region",
            value=self.config.preferred_region,
            options=[
                ft.dropdown.Option("NA"),
                ft.dropdown.Option("EU"),
                ft.dropdown.Option("JP"),
                ft.dropdown.Option("KR"),
                ft.dropdown.Option("CN"),
            ],
        )

        self.igdb_client_id = ft.TextField(
            label="igdb client id",
            value=self.config.igdb_client_id or "",
        )

        self.igdb_client_secret = ft.TextField(
            label="igdb client secret",
            value=self.config.igdb_client_secret or "",
            password=True,
            can_reveal_password=True,
        )

        self.steamgrid_key = ft.TextField(
            label="steamgriddb api key",
            value=self.config.steamgrid_api_key or "",
            password=True,
            can_reveal_password=True,
        )

        self.theme_dropdown = ft.Dropdown(
            label="theme mode",
            value=self.config.theme_mode or "system",
            options=[
                ft.dropdown.Option("light", "light"),
                ft.dropdown.Option("dark", "dark"),
                ft.dropdown.Option("system", "system (follow xresources)"),
                ft.dropdown.Option("dynamic", "dynamic (from artwork)"),
            ],
        )

        self.primary_color_input = ft.TextField(
            label="custom primary color (hex)",
            value=self.config.primary_color or "",
            hint_text="#1976d2",
        )

        tabs = ft.Tabs(
            selected_index=0,
            length=4,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="general"),
                            ft.Tab(label="theme"),
                            ft.Tab(label="igdb api"),
                            ft.Tab(label="steamgriddb"),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    [
                                        self.games_dir_input,
                                        self.fullscreen_check,
                                        self.region_dropdown,
                                    ]
                                ),
                                padding=20,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        self.theme_dropdown,
                                        self.primary_color_input,
                                        ft.Text(
                                            "theme mode:",
                                            size=12,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                        ft.Text(
                                            "• system: follows xresources theme\n"
                                            "• dynamic: extracts colors from game/console artwork\n"
                                            "• light/dark: fixed theme",
                                            size=11,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                    ]
                                ),
                                padding=20,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        self.igdb_client_id,
                                        self.igdb_client_secret,
                                    ]
                                ),
                                padding=20,
                            ),
                            ft.Container(
                                content=ft.Column([self.steamgrid_key]),
                                padding=20,
                            ),
                        ],
                    ),
                ],
            ),
        )

        return ft.AlertDialog(
            title=ft.Text("settings"),
            content=ft.Container(content=tabs, width=600, height=400),
            actions=[
                ft.TextButton("cancel", on_click=lambda _: self.page.pop_dialog()),
                ft.FilledButton("save", on_click=self._on_submit),
            ],
        )

    def _on_submit(self, e) -> None:
        self.config.games_directory = self.games_dir_input.value
        self.config.fullscreen = self.fullscreen_check.value
        self.config.preferred_region = self.region_dropdown.value
        self.config.theme_mode = self.theme_dropdown.value

        primary_color = self.primary_color_input.value.strip()
        if primary_color and primary_color.startswith("#"):
            self.config.primary_color = primary_color
        else:
            self.config.primary_color = None

        client_id = self.igdb_client_id.value.strip()
        client_secret = self.igdb_client_secret.value.strip()
        self.config.igdb_client_id = client_id if client_id else None
        self.config.igdb_client_secret = client_secret if client_secret else None

        sg_key = self.steamgrid_key.value.strip()
        self.config.steamgrid_api_key = sg_key if sg_key else None

        self.config.save()
        self.page.pop_dialog()
        self.on_save()


class InstallConsoleDialog:
    def __init__(
        self, page: ft.Page, library, sources, steamgrid, on_install: Callable
    ) -> None:
        self.page = page
        self.library = library
        self.sources = sources
        self.steamgrid = steamgrid
        self.on_install = on_install

    def create(self) -> ft.AlertDialog:
        self.search_input = ft.TextField(
            label="search",
            hint_text="search consoles...",
            on_change=self._on_search,
        )

        self.console_list = ft.ListView(expand=True, spacing=5)

        self.all_consoles = []
        for code in self.sources.list_consoles():
            vrdb_console = self.sources.vrdb.get_console(code)
            if vrdb_console:
                self.all_consoles.append((code, vrdb_console))

        self.all_consoles.sort(key=lambda x: x[1].console.name)
        self._populate_list()

        return ft.AlertDialog(
            title=ft.Text("install console"),
            content=ft.Container(
                content=ft.Column([self.search_input, self.console_list]),
                width=600,
                height=500,
            ),
            actions=[
                ft.TextButton("cancel", on_click=lambda _: self.page.pop_dialog()),
            ],
        )

    def _populate_list(self, query: str = "") -> None:
        self.console_list.controls.clear()
        query_lower = query.lower()

        for code, vrdb_console in self.all_consoles:
            name = vrdb_console.console.name
            if not query or query_lower in code.lower() or query_lower in name.lower():
                self._add_console_card(code, vrdb_console)

        self.page.update()

    def _add_console_card(self, code: str, vrdb_console) -> None:
        console = vrdb_console.console

        icon_widget = None

        if self.steamgrid and self.steamgrid.api_key:
            games = self.steamgrid.search_game(console.name)
            if games and len(games) > 0:
                game_id = games[0].get("id")
                assets = self.steamgrid.get_assets(game_id, "icons")
                if assets and len(assets) > 0:
                    url = assets[0].get("thumb") or assets[0].get("url")
                    if url:
                        icon_widget = ft.Image(
                            src=url,
                            width=40,
                            height=40,
                            fit=ft.BoxFit.CONTAIN,
                        )

        if not icon_widget:
            icon_widget = ft.Icon(ft.Icons.VIDEOGAME_ASSET, size=40)

        title_text = ft.Text(
            console.name,
            size=16,
            weight=ft.FontWeight.W_500,
        )

        info_text = ft.Text(
            f"{console.manufacturer} • {console.release}",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        self.show_details = False

        details_container = ft.Container(
            visible=False,
            padding=ft.padding.only(top=10),
        )

        def toggle_details(_):
            self.show_details = not self.show_details
            details_container.visible = self.show_details

            if self.show_details and not details_container.content:
                details_container.content = ft.Column(
                    [
                        ft.Text(
                            f"generation: {console.generation or 'n/a'}",
                            size=12,
                        ),
                        ft.Text(
                            f"formats: {', '.join(console.formats)}",
                            size=12,
                        ),
                        ft.Text(
                            f"emulator: {vrdb_console.emulator.name}",
                            size=12,
                        ),
                        ft.Text(
                            f"binary: {vrdb_console.emulator.binary}",
                            size=12,
                        ),
                    ],
                    spacing=5,
                )

            self.page.update()

        install_btn = ft.FilledButton(
            "install",
            icon=ft.Icons.DOWNLOAD,
            on_click=lambda _, c=code: self._install(c),
        )

        info_btn = ft.IconButton(
            icon=ft.Icons.INFO_OUTLINE,
            tooltip="show details",
            on_click=toggle_details,
        )

        card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            icon_widget,
                            ft.Container(
                                content=ft.Column(
                                    [title_text, info_text],
                                    spacing=5,
                                ),
                                expand=True,
                                padding=ft.padding.only(left=10),
                            ),
                            info_btn,
                            install_btn,
                        ],
                        spacing=10,
                    ),
                    details_container,
                ],
                spacing=0,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            padding=10,
        )

        self.console_list.controls.append(card)

    def _on_search(self, e) -> None:
        self._populate_list(e.control.value)

    def _install(self, code: str) -> None:
        self.page.pop_dialog()

        meta = get_console_metadata(code.upper())
        if not meta:
            self._show_error("error", f"unknown console: {code}")
            return

        progress_dialog = ft.AlertDialog(
            title=ft.Text(f"installing {meta.name}"),
            content=ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Text("creating console directories..."),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            modal=True,
        )

        self.page.show_dialog(progress_dialog)

        def install_thread():
            try:
                console_dir = self.library.create_console(code.upper(), meta)

                if self.steamgrid and self.steamgrid.api_key:
                    progress_dialog.content.controls[1].value = "downloading artwork..."
                    self.page.update()

                    graphics_dir = console_dir / "graphics"
                    graphics_dir.mkdir(parents=True, exist_ok=True)

                    games = self.steamgrid.search_game(meta.name)
                    if games and len(games) > 0:
                        game_id = games[0].get("id")

                        for asset_type, file_name in [
                            ("heroes", "hero"),
                            ("logos", "logo"),
                            ("icons", "icon"),
                        ]:
                            assets = self.steamgrid.get_assets(game_id, asset_type)
                            if assets and len(assets) > 0:
                                url = assets[0].get("url")
                                if url:
                                    dest = graphics_dir / f"{file_name}.png"
                                    self.steamgrid.download_asset(url, dest)

                if meta.emulator.download_url:
                    progress_dialog.content.controls[
                        1
                    ].value = "downloading emulator..."
                    self.page.update()

                    emulator_dir = console_dir / "emulator"
                    download_emulator(
                        code,
                        meta.emulator.name,
                        meta.emulator.download_url,
                        emulator_dir,
                    )

                self.page.pop_dialog()

                info_text = f"created console: {code.upper()}\n\n{meta.name}"
                if meta.emulator.requires_bios:
                    info_text += "\n\nrequired bios files:"
                    for bios in meta.emulator.bios_files:
                        info_text += f"\n  • {bios}"

                self._show_info("installation complete", info_text)
                self.on_install()

            except Exception as e:
                self.page.pop_dialog()
                self._show_error("error", f"failed to create console: {e}")

        threading.Thread(target=install_thread, daemon=True).start()

    def _show_error(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _show_info(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)


class InstallGameDialog:
    def __init__(
        self,
        page: ft.Page,
        console: str,
        library,
        sources,
        db,
        steamgrid,
        on_install: Callable,
    ) -> None:
        self.page = page
        self.console = console
        self.library = library
        self.sources = sources
        self.db = db
        self.steamgrid = steamgrid
        self.on_install = on_install
        self.selected_games: Set[str] = set()
        self.game_results = []
        self.installing = False

    def create(self) -> ft.AlertDialog:
        self.search_input = ft.TextField(
            label="search games",
            hint_text="search...",
            on_submit=lambda _: self._on_search(None),
        )

        self.game_list = ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.install_button = ft.FilledButton(
            "install selected",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._install_selected,
            visible=False,
        )

        return ft.AlertDialog(
            title=ft.Text(f"install games - {self.console}"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                self.search_input,
                                ft.IconButton(
                                    icon=ft.Icons.SEARCH,
                                    on_click=self._on_search,
                                ),
                            ]
                        ),
                        self.game_list,
                    ]
                ),
                width=700,
                height=600,
            ),
            actions=[
                self.install_button,
                ft.TextButton("close", on_click=lambda _: self.page.pop_dialog()),
            ],
        )

    def _on_search(self, e) -> None:
        self.game_list.controls.clear()
        self.selected_games.clear()
        self.install_button.visible = False
        query = self.search_input.value

        if not query:
            return

        progress = ft.ProgressRing()
        self.game_list.controls.append(
            ft.Container(content=progress, alignment=ft.Alignment.CENTER)
        )
        self.page.update()

        def search_thread():
            vrdb_games = self.sources.search_games(self.console.upper(), query)
            igdb_games = self.db.search_games(query, self.console)

            igdb_map = {g.name.lower(): g for g in igdb_games}

            self.game_results = []
            for game_name, source in vrdb_games:
                igdb_game = igdb_map.get(game_name.lower())
                self.game_results.append((game_name, source, igdb_game))

            self.game_list.controls.clear()

            if not self.game_results:
                self.game_list.controls.append(
                    ft.Text("no results found", color=ft.Colors.ON_SURFACE_VARIANT)
                )
            else:
                for game_name, source, igdb_game in self.game_results:
                    card = self._create_game_card(game_name, source, igdb_game)
                    self.game_list.controls.append(card)

            self.page.update()

        threading.Thread(target=search_thread, daemon=True).start()

    def _create_game_card(self, game_name: str, source, igdb_game) -> ft.Control:
        is_selected = game_name in self.selected_games

        checkbox = ft.Checkbox(
            value=is_selected,
            on_change=lambda e, gn=game_name: self._toggle_selection(gn),
        )

        cover = None

        if self.steamgrid and self.steamgrid.api_key:
            games = self.steamgrid.search_game(game_name)
            if games and len(games) > 0:
                game_id = games[0].get("id")
                assets = self.steamgrid.get_assets(game_id, "grids")
                if assets and len(assets) > 0:
                    url = assets[0].get("thumb") or assets[0].get("url")
                    if url:
                        cover = ft.Image(
                            src=url,
                            width=80,
                            height=120,
                            fit=ft.BoxFit.COVER,
                            border_radius=4,
                        )

        if not cover and igdb_game and igdb_game.cover_url:
            cover = ft.Image(
                src=igdb_game.cover_url,
                width=80,
                height=120,
                fit=ft.BoxFit.COVER,
                border_radius=4,
            )

        if not cover:
            cover = ft.Container(
                width=80,
                height=120,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=4,
                content=ft.Icon(ft.Icons.VIDEOGAME_ASSET, size=40),
                alignment=ft.Alignment.CENTER,
            )

        title_widget = ft.Text(
            game_name,
            size=16,
            weight=ft.FontWeight.W_500,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        info_widgets = []

        if igdb_game:
            if igdb_game.year:
                info_widgets.append(
                    ft.Text(
                        str(igdb_game.year),
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )
                )

            if igdb_game.publisher:
                info_widgets.append(
                    ft.Text(
                        igdb_game.publisher,
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )
                )

            if igdb_game.genres:
                info_widgets.append(
                    ft.Text(
                        " • ".join(igdb_game.genres[:2]),
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )
                )

        info_column = ft.Column(info_widgets, spacing=4) if info_widgets else None

        summary = None
        if igdb_game and igdb_game.summary:
            summary = ft.Text(
                igdb_game.summary[:200] + "..."
                if len(igdb_game.summary) > 200
                else igdb_game.summary,
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
                max_lines=3,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

        content_column = [title_widget]
        if info_column:
            content_column.append(info_column)
        if summary:
            content_column.append(summary)

        install_btn = ft.IconButton(
            icon=ft.Icons.DOWNLOAD,
            tooltip="install",
            on_click=lambda _,
            gn=game_name,
            s=source,
            ig=igdb_game: self._install_single(gn, s, ig),
        )

        return ft.Container(
            content=ft.Row(
                [
                    checkbox,
                    cover,
                    ft.Container(
                        content=ft.Column(content_column, spacing=8),
                        expand=True,
                        padding=ft.padding.only(left=10),
                    ),
                    install_btn,
                ],
                spacing=10,
            ),
            border=ft.border.all(
                1, ft.Colors.PRIMARY if is_selected else ft.Colors.OUTLINE
            ),
            border_radius=8,
            padding=10,
        )

    def _toggle_selection(self, game_name: str) -> None:
        if game_name in self.selected_games:
            self.selected_games.remove(game_name)
        else:
            self.selected_games.add(game_name)

        self.install_button.visible = len(self.selected_games) > 0
        self.install_button.text = (
            f"install {len(self.selected_games)} selected"
            if len(self.selected_games) > 1
            else "install selected"
        )

        for i, (gn, _, _) in enumerate(self.game_results):
            card = self.game_list.controls[i]
            is_selected = gn in self.selected_games
            card.border = ft.border.all(
                1, ft.Colors.PRIMARY if is_selected else ft.Colors.OUTLINE
            )

        self.page.update()

    def _install_selected(self, e) -> None:
        if self.installing or not self.selected_games:
            return

        self.installing = True
        games_to_install = [
            (gn, s, ig) for gn, s, ig in self.game_results if gn in self.selected_games
        ]

        self.game_list.controls.clear()
        self.install_button.visible = False

        for game_name, source, igdb_game in games_to_install:
            self._add_install_progress(game_name)

        self.page.update()

        def install_thread():
            for i, (game_name, source, igdb_game) in enumerate(games_to_install):
                self._install_game_worker(game_name, source, igdb_game, i)

            self.installing = False
            self.page.pop_dialog()
            self._show_info(
                "installation complete",
                f"installed {len(games_to_install)} games",
            )
            self.on_install()

        threading.Thread(target=install_thread, daemon=True).start()

    def _install_single(self, game_name: str, source, igdb_game) -> None:
        if self.installing:
            return

        self.installing = True
        self.game_list.controls.clear()
        self.install_button.visible = False

        self._add_install_progress(game_name)
        self.page.update()

        def install_thread():
            self._install_game_worker(game_name, source, igdb_game, 0)
            self.installing = False
            self.page.pop_dialog()
            self._show_info("success", f"installed {game_name}")
            self.on_install()

        threading.Thread(target=install_thread, daemon=True).start()

    def _add_install_progress(self, game_name: str) -> None:
        progress_bar = ft.ProgressBar(width=400, value=0)
        status_text = ft.Text("preparing...", size=12)

        container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        game_name,
                        size=16,
                        weight=ft.FontWeight.W_500,
                    ),
                    progress_bar,
                    status_text,
                ],
                spacing=5,
            ),
            padding=10,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )

        self.game_list.controls.append(container)

    def _update_progress(self, idx: int, status: str, value: float) -> None:
        if idx < len(self.game_list.controls):
            container = self.game_list.controls[idx]
            column = container.content
            progress_bar = column.controls[1]
            status_text = column.controls[2]

            progress_bar.value = value
            status_text.value = status
            self.page.update()

    def _install_game_worker(self, game_name: str, source, igdb_game, idx: int) -> None:
        try:
            console_code_upper = self.console.upper()
            console_meta = self.library.get_console_metadata(console_code_upper)

            if not console_meta:
                self._update_progress(idx, "error: console not found", 0)
                return

            console_dir = self.library.console_root / console_meta.name
            games_dir = console_dir / "games"

            game_slug = re.sub(r"[^\w\s-]", "", game_name.lower())
            game_slug = re.sub(r"[-\s]+", "-", game_slug).strip("-")

            game_dir = games_dir / game_slug
            game_dir.mkdir(parents=True, exist_ok=True)
            (game_dir / "resources").mkdir(exist_ok=True)
            (game_dir / "saves").mkdir(exist_ok=True)
            (game_dir / "graphics").mkdir(exist_ok=True)

            download_dir = game_dir / "resources"
            extension = CONSOLE_EXTENSIONS.get(console_code_upper, "bin")
            dest_file = download_dir / f"base.{extension}"

            self._update_progress(idx, "downloading game...", 0.2)

            success = self.sources.download_file(source, dest_file, game_name)

            if not success:
                self._update_progress(idx, "download failed", 0)
                return

            self._update_progress(idx, "creating metadata...", 0.5)

            metadata = GameMetadata(
                code=f"{console_code_upper.lower()}-{game_slug}",
                console=console_code_upper,
                id=0,
                title={"NA": game_name},
                publisher={"NA": "unknown"},
                year=0,
                region="NA",
            )

            if igdb_game:
                metadata.id = igdb_game.id
                metadata.title = {"NA": igdb_game.name}
                metadata.publisher = {"NA": igdb_game.publisher or "unknown"}
                metadata.year = igdb_game.year or 0

            metadata.save(game_dir / "metadata.json")

            if self.steamgrid and self.steamgrid.api_key:
                try:
                    self._update_progress(idx, "downloading artwork...", 0.8)

                    graphics_dir = game_dir / "graphics"
                    graphics_dir.mkdir(parents=True, exist_ok=True)

                    games = self.steamgrid.search_game(game_name)
                    if games and len(games) > 0:
                        game_id = games[0].get("id")

                        for asset_type, file_name in [
                            ("grids", "grid"),
                            ("heroes", "hero"),
                            ("logos", "logo"),
                            ("icons", "icon"),
                        ]:
                            assets = self.steamgrid.get_assets(game_id, asset_type)
                            if assets and len(assets) > 0:
                                url = assets[0].get("url")
                                if url:
                                    dest = graphics_dir / f"{file_name}.png"
                                    self.steamgrid.download_asset(url, dest)
                except Exception:
                    pass

            self._update_progress(idx, "complete", 1.0)

        except Exception as e:
            self._update_progress(idx, f"error: {str(e)}", 0)

    def _show_error(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _show_info(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)


class EditMetadataDialog:
    def __init__(self, page: ft.Page, game, on_save: Callable) -> None:
        self.page = page
        self.game = game
        self.on_save = on_save

    def create(self) -> ft.AlertDialog:
        self.code_input = ft.TextField(label="code", value=self.game.metadata.code)
        self.title_input = ft.TextField(
            label="title", value=self.game.metadata.get_title()
        )
        self.console_input = ft.TextField(
            label="console", value=self.game.metadata.console
        )
        self.year_input = ft.TextField(label="year", value=str(self.game.metadata.year))
        self.region_input = ft.TextField(
            label="region", value=self.game.metadata.region
        )

        publisher = (
            list(self.game.metadata.publisher.values())[0]
            if self.game.metadata.publisher
            else ""
        )
        self.publisher_input = ft.TextField(label="publisher", value=publisher)

        return ft.AlertDialog(
            title=ft.Text("edit metadata"),
            content=ft.Column(
                [
                    self.code_input,
                    self.title_input,
                    self.console_input,
                    self.year_input,
                    self.region_input,
                    self.publisher_input,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("cancel", on_click=lambda _: self.page.pop_dialog()),
                ft.FilledButton("save", on_click=self._on_submit),
            ],
        )

    def _on_submit(self, e) -> None:
        region = self.region_input.value
        new_metadata = GameMetadata(
            code=self.code_input.value,
            console=self.console_input.value,
            id=self.game.metadata.id,
            title={region: self.title_input.value},
            publisher={region: self.publisher_input.value},
            year=int(self.year_input.value),
            region=region,
            has_dlc=self.game.metadata.has_dlc,
            has_updates=self.game.metadata.has_updates,
        )
        new_metadata.save(self.game.path / "metadata.json")
        self.game.metadata = new_metadata

        self.page.pop_dialog()
        self.on_save()


class ArtworkDialog:
    def __init__(self, page: ft.Page, game, steamgrid, on_download: Callable) -> None:
        self.page = page
        self.game = game
        self.steamgrid = steamgrid
        self.on_download = on_download

    def create(self) -> ft.AlertDialog:
        self.search_input = ft.TextField(
            label="search",
            value=self.game.metadata.get_title(),
        )

        self.results_grids = [
            ft.GridView(
                expand=True,
                runs_count=3,
                max_extent=200,
                child_aspect_ratio=1.0,
                spacing=10,
                run_spacing=10,
            )
            for _ in range(4)
        ]

        tabs = ft.Tabs(
            selected_index=0,
            length=4,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="grid"),
                            ft.Tab(label="hero"),
                            ft.Tab(label="logo"),
                            ft.Tab(label="icon"),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=self.results_grids,
                    ),
                ],
            ),
            on_change=lambda _: self._on_search(None),
        )

        self.tabs = tabs

        return ft.AlertDialog(
            title=ft.Text("download artwork"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                self.search_input,
                                ft.IconButton(
                                    icon=ft.Icons.SEARCH,
                                    on_click=self._on_search,
                                ),
                            ]
                        ),
                        tabs,
                        ft.Container(height=10),
                    ]
                ),
                width=700,
                height=600,
            ),
            actions=[
                ft.TextButton("close", on_click=lambda _: self.page.pop_dialog()),
            ],
            on_dismiss=lambda _: self.page.pop_dialog(),
        )

    def _on_search(self, e) -> None:
        selected_index = self.tabs.selected_index
        results = self.results_grids[selected_index]
        results.controls.clear()

        games = self.steamgrid.search_game(self.search_input.value)

        if not games:
            results.controls.append(ft.Text("no results found"))
            self.page.update()
            return

        game_id = games[0].get("id")

        asset_types = ["grids", "heroes", "logos", "icons"]
        file_names = ["grid", "hero", "logo", "icon"]
        asset_type = asset_types[selected_index]
        file_name = file_names[selected_index]

        assets = self.steamgrid.get_assets(game_id, asset_type)

        for asset in assets[:12]:
            url = asset.get("thumb") or asset.get("url")
            if not url:
                continue

            card = ft.Container(
                content=ft.Image(src=url, fit=ft.BoxFit.COVER),
                border_radius=8,
                ink=True,
                on_click=lambda _,
                full_url=asset.get("url"),
                fn=file_name: self._download(full_url, fn),
            )
            results.controls.append(card)

        self.page.update()

    def _download(self, url: str, asset_type: str) -> None:
        graphics_dir = self.game.path / "graphics"
        graphics_dir.mkdir(parents=True, exist_ok=True)
        dest = graphics_dir / f"{asset_type}.png"

        if self.steamgrid.download_asset(url, dest):
            self.page.pop_dialog()
            self._show_info("success", f"downloaded {asset_type}")
            self.on_download()
        else:
            self._show_error("error", "download failed")

    def _show_error(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _show_info(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)


class ConsoleInfoDialog:
    def __init__(self, page: ft.Page, console_meta, library) -> None:
        self.page = page
        self.console_meta = console_meta
        self.library = library

    def create(self) -> ft.AlertDialog:
        if not self.console_meta:
            return None

        console_dir = self.library.console_root / self.console_meta.name
        emulator_dir = console_dir / "emulator"
        status = (
            "installed"
            if emulator_dir.exists() and any(emulator_dir.iterdir())
            else "not installed"
        )

        graphics_dir = console_dir / "graphics"
        hero_path = graphics_dir / "hero.png"
        logo_path = graphics_dir / "logo.png"

        hero_content = []
        if hero_path.exists():
            logo_widget = (
                ft.Image(
                    src=str(logo_path),
                    width=300,
                    fit=ft.BoxFit.CONTAIN,
                )
                if logo_path.exists()
                else ft.Text(
                    self.console_meta.name,
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                )
            )

            hero_stack = ft.Container(
                content=ft.Stack(
                    [
                        ft.Image(
                            src=str(hero_path),
                            width=600,
                            height=300,
                            fit=ft.BoxFit.COVER,
                        ),
                        ft.Container(
                            width=600,
                            height=300,
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment.TOP_CENTER,
                                end=ft.Alignment.BOTTOM_CENTER,
                                colors=["#00000000", "#000000CC"],
                            ),
                        ),
                        ft.Container(
                            content=logo_widget,
                            alignment=ft.Alignment.BOTTOM_LEFT,
                            padding=20,
                            width=600,
                            height=300,
                        ),
                    ],
                    width=600,
                    height=300,
                ),
                width=600,
                height=300,
            )
            hero_content.append(hero_stack)

        content = ft.Column(
            [
                *hero_content,
                ft.Container(height=20),
                ft.Text(f"code: {self.console_meta.code}"),
                ft.Text(f"manufacturer: {self.console_meta.manufacturer}"),
                ft.Text(f"release: {self.console_meta.release}"),
                ft.Text(f"generation: {self.console_meta.generation or 'n/a'}"),
                ft.Text(f"formats: {', '.join(self.console_meta.formats)}"),
                ft.Container(height=20),
                ft.Text("emulator", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"name: {self.console_meta.emulator.name}"),
                ft.Text(f"binary: {self.console_meta.emulator.binary}"),
                ft.Text(f"status: {status}"),
            ],
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        )

        return ft.AlertDialog(
            title=ft.Text(self.console_meta.name) if not hero_content else None,
            content=ft.Container(content=content, width=600),
            actions=[
                ft.TextButton("close", on_click=lambda _: self.page.pop_dialog()),
            ],
        )


class IGDBSearchDialog:
    def __init__(self, page: ft.Page, game, db, on_update: Callable) -> None:
        self.page = page
        self.game = game
        self.db = db
        self.on_update = on_update

    def create(self) -> ft.AlertDialog:
        self.search_input = ft.TextField(
            label="search igdb",
            value=self.game.metadata.get_title(),
        )

        self.results_list = ft.ListView(expand=True, spacing=5)
        self.progress_bar = ft.ProgressRing(visible=False)

        return ft.AlertDialog(
            title=ft.Text("search igdb"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                self.search_input,
                                ft.IconButton(
                                    icon=ft.Icons.SEARCH,
                                    on_click=self._on_search,
                                ),
                            ]
                        ),
                        self.progress_bar,
                        self.results_list,
                    ]
                ),
                width=600,
                height=500,
            ),
            actions=[
                ft.TextButton("cancel", on_click=lambda _: self.page.pop_dialog()),
            ],
        )

    def _on_search(self, e) -> None:
        self.results_list.controls.clear()
        self.progress_bar.visible = True
        query = self.search_input.value
        self.page.update()

        if not query:
            self.progress_bar.visible = False
            self.page.update()
            return

        try:
            games = self.db.search_games(query)

            self.progress_bar.visible = False

            if not games:
                self.results_list.controls.append(
                    ft.Text("no results found", color=ft.Colors.ON_SURFACE_VARIANT)
                )
            else:
                for igdb_game in games[:20]:
                    btn = ft.ListTile(
                        title=ft.Text(igdb_game.name),
                        subtitle=ft.Text(
                            f"{igdb_game.platform} • {igdb_game.year or '?'} • {igdb_game.publisher or 'unknown'}"
                        ),
                        on_click=lambda _, g=igdb_game: self._select_game(g),
                    )
                    self.results_list.controls.append(btn)

            self.page.update()

        except Exception as ex:
            self.progress_bar.visible = False
            self.results_list.controls.append(
                ft.Text(f"error: {str(ex)}", color=ft.Colors.ERROR)
            )
            self.page.update()

    def _select_game(self, igdb_game) -> None:
        self.game.metadata.id = igdb_game.id
        self.game.metadata.title = {"NA": igdb_game.name}
        self.game.metadata.publisher = {"NA": igdb_game.publisher or "unknown"}
        self.game.metadata.year = igdb_game.year or 0

        self.game.metadata.save(self.game.path / "metadata.json")

        self.page.pop_dialog()
        self._show_info("success", f"updated metadata to: {igdb_game.name}")
        self.on_update()

    def _show_info(self, title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("ok", on_click=lambda _: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)
