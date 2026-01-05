import re
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

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
                self.all_consoles.append((code, vrdb_console.console.name))

        self.all_consoles.sort(key=lambda x: x[1])
        self._populate_list()

        return ft.AlertDialog(
            title=ft.Text("install console"),
            content=ft.Container(
                content=ft.Column([self.search_input, self.console_list]),
                width=500,
                height=500,
            ),
            actions=[
                ft.TextButton("cancel", on_click=lambda _: self.page.pop_dialog()),
            ],
        )

    def _populate_list(self, query: str = "") -> None:
        self.console_list.controls.clear()
        query_lower = query.lower()

        for code, name in self.all_consoles:
            if not query or query_lower in code.lower() or query_lower in name.lower():
                btn = ft.ListTile(
                    title=ft.Text(name),
                    subtitle=ft.Text(code),
                    on_click=lambda _, c=code: self._install(c),
                )
                self.console_list.controls.append(btn)

        self.page.update()

    def _on_search(self, e) -> None:
        self._populate_list(e.control.value)

    def _install(self, code: str) -> None:
        self.page.pop_dialog()

        meta = get_console_metadata(code.upper())
        if not meta:
            self._show_error("error", f"unknown console: {code}")
            return

        try:
            console_dir = self.library.create_console(code.upper(), meta)

            def download_artwork():
                if (
                    hasattr(self, "steamgrid")
                    and self.steamgrid
                    and self.steamgrid.api_key
                ):
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

            import threading

            threading.Thread(target=download_artwork, daemon=True).start()

            self._show_info(
                "success",
                f"created console: {code.upper()}\n\n{meta.name}\n\nemulator: {meta.emulator.name}\n\ndownloading artwork...",
            )
            self.on_install()
        except Exception as e:
            self._show_error("error", f"failed to create console: {e}")

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

    def create(self) -> ft.AlertDialog:
        self.search_input = ft.TextField(
            label="search games",
            hint_text="search...",
        )

        self.game_list = ft.ListView(expand=True, spacing=5)
        self.progress_bar = ft.ProgressRing(visible=False)
        self.progress_text = ft.Text("", visible=False)

        return ft.AlertDialog(
            title=ft.Text(f"install game - {self.console}"),
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
                        self.progress_bar,
                        self.progress_text,
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
        self.game_list.controls.clear()
        query = self.search_input.value

        if not query:
            return

        games = self.sources.search_games(self.console.upper(), query)

        for game_name, source in games:
            btn = ft.ListTile(
                title=ft.Text(game_name),
                subtitle=ft.Text(f"source: {source.scheme}"),
                on_click=lambda _, gn=game_name, s=source: self._install(gn, s),
            )
            self.game_list.controls.append(btn)

        self.page.update()

    def _install(self, game_name: str, source) -> None:
        self.game_list.controls.clear()
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_text.value = "downloading game..."
        self.page.update()

        def download_thread():
            console_code_upper = self.console.upper()
            console_meta = self.library.get_console_metadata(console_code_upper)

            if not console_meta:
                self._show_error(
                    "error", f"console not installed: {console_code_upper}"
                )
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

            success = self.sources.download_file(source, dest_file, game_name)

            if success:
                self.progress_text.value = "fetching metadata..."
                self.page.update()

                igdb_games = self.db.search_games(game_name, self.console)
                if igdb_games:
                    igdb_game = igdb_games[0]
                    metadata = GameMetadata(
                        code=f"{self.console.lower()}-{game_slug}",
                        console=console_code_upper,
                        id=igdb_game.id,
                        title={"NA": igdb_game.name},
                        publisher={"NA": igdb_game.publisher or "unknown"},
                        year=igdb_game.year or 0,
                        region="NA",
                    )
                    metadata.save(game_dir / "metadata.json")

                if self.steamgrid and self.steamgrid.api_key:
                    self.progress_text.value = "downloading artwork..."
                    self.page.update()

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

                self.progress_bar.visible = False
                self.progress_text.visible = False
                self.page.pop_dialog()
                self._show_info("success", f"downloaded {game_name}")
                self.on_install()
            else:
                self.progress_bar.visible = False
                self.progress_text.visible = False
                self._show_error("error", "download failed")

            self.page.update()

        threading.Thread(target=download_thread, daemon=True).start()

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
            hero_stack = ft.Stack(
                [
                    ft.Container(
                        content=ft.Image(
                            src=str(hero_path),
                            fit=ft.BoxFit.COVER,
                        ),
                        width=600,
                        height=300,
                        top=0,
                        left=0,
                    ),
                    ft.Container(
                        width=600,
                        height=300,
                        top=0,
                        left=0,
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment.TOP_CENTER,
                            end=ft.Alignment.BOTTOM_CENTER,
                            colors=["#00000000", "#000000CC"],
                        ),
                    ),
                    ft.Container(
                        content=ft.Image(
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
                        ),
                        bottom=20,
                        left=20,
                    ),
                ],
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
