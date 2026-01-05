import re
import sys
from pathlib import Path
from typing import Callable, Optional

import flet as ft

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.data.config import VRetroConfig
from src.data.console import get_console_metadata
from src.data.library import CONSOLE_EXTENSIONS, GameMetadata


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
        if steamgrid_key:
            config.__dict__["steamgrid_api_key"] = steamgrid_key
        config.save()

        self.page.pop_dialog()
        self.on_complete()


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
            value=getattr(self.config, "steamgrid_api_key", None) or "",
            password=True,
            can_reveal_password=True,
        )

        tabs = ft.Tabs(
            selected_index=0,
            length=3,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="general"),
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

        client_id = self.igdb_client_id.value.strip()
        client_secret = self.igdb_client_secret.value.strip()
        self.config.igdb_client_id = client_id if client_id else None
        self.config.igdb_client_secret = client_secret if client_secret else None

        sg_key = self.steamgrid_key.value.strip()
        if sg_key:
            self.config.__dict__["steamgrid_api_key"] = sg_key

        self.config.save()
        self.page.pop_dialog()
        self.on_save()


class InstallConsoleDialog:
    def __init__(self, page: ft.Page, library, sources, on_install: Callable) -> None:
        self.page = page
        self.library = library
        self.sources = sources
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
            self._show_info(
                "success",
                f"created console: {code.upper()}\n\n{meta.name}\n\nemulator: {meta.emulator.name}",
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
        on_install: Callable,
    ) -> None:
        self.page = page
        self.console = console
        self.library = library
        self.sources = sources
        self.db = db
        self.on_install = on_install

    def create(self) -> ft.AlertDialog:
        self.search_input = ft.TextField(
            label="search games",
            hint_text="search...",
        )

        self.game_list = ft.ListView(expand=True, spacing=5)

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
        self.page.pop_dialog()

        console_code_upper = self.console.upper()
        console_meta = self.library.get_console_metadata(console_code_upper)

        if not console_meta:
            self._show_error("error", f"console not installed: {console_code_upper}")
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

            self._show_info("success", f"downloaded {game_name}")
            self.on_install()
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
                    ft.TabBarView(expand=True, controls=self.results_grids),
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
                content=ft.Image(src=url, fit=ft.ImageFit.COVER),
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
                    ft.Image(
                        src=str(hero_path),
                        width=600,
                        height=300,
                        fit=ft.ImageFit.COVER,
                    ),
                    ft.Container(
                        width=600,
                        height=300,
                        gradient=ft.LinearGradient(
                            begin=ft.alignment.top_center,
                            end=ft.alignment.bottom_center,
                            colors=["#00000000", "#000000CC"],
                        ),
                    ),
                    ft.Container(
                        content=ft.Image(
                            src=str(logo_path),
                            width=300,
                            fit=ft.ImageFit.CONTAIN,
                        )
                        if logo_path.exists()
                        else ft.Text(
                            self.console_meta.name,
                            size=32,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        alignment=ft.alignment.bottom_left,
                        padding=20,
                    ),
                ]
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
