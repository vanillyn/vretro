#!/usr/bin/env python3
import os
import platform
from pathlib import Path
from typing import List, Tuple

import click
from rich.console import Console
from rich.table import Table

try:
    from PIL import Image
    from sixel import SixelWriter

    SIXEL_AVAILABLE = True
except ImportError:
    SIXEL_AVAILABLE = False

from src.data.config import VRetroConfig, get_config_path
from src.data.console import get_console_metadata
from src.data.database import OnlineDatabase
from src.data.library import CONSOLE_EXTENSIONS, GameLibrary, GameMetadata
from src.util.download import download_emulator
from src.util.launch import launch_game
from src.util.sources import SourceManager

term = Console()

IS_WINDOWS = platform.system() == "Windows"


def supports_sixel() -> bool:
    env_term = os.environ.get("TERM", "")
    return "sixel" in env_term.lower() or os.environ.get("TERM_PROGRAM") == "mlterm"


def display_thumbnail(image_path: Path, width: int = 320):
    if not SIXEL_AVAILABLE or not supports_sixel():
        return

    try:
        img = Image.open(image_path)
        aspect_ratio = img.height / img.width
        new_height = int(width * aspect_ratio)
        img = img.resize((width, new_height), Image.Resampling.LANCZOS)
        writer = SixelWriter()
        img_bytes = img.tobytes()
        writer.draw(img_bytes, width, new_height, img.mode)
    except Exception:
        pass


def fuzzy_search_all(
    query: str, library: GameLibrary, sources: SourceManager
) -> List[Tuple[str, str, str]]:
    query_lower = query.lower()
    results = []

    for code in sources.list_consoles():
        vrdb_console = sources.vrdb.get_console(code)
        if vrdb_console:
            if (
                query_lower in vrdb_console.console.name.lower()
                or query_lower in code.lower()
            ):
                results.append(("console", code, vrdb_console.console.name))

            for game_name in vrdb_console.games.keys():
                if query_lower in game_name.lower():
                    results.append(("game", game_name, f"{code}/{game_name}"))

    for game in library.games:
        if query_lower in game.metadata.get_title().lower():
            console_meta = library.get_console_metadata(game.metadata.console)
            console_name = console_meta.name if console_meta else game.metadata.console
            results.append(
                (
                    "game",
                    game.metadata.code,
                    f"{console_name}/{game.metadata.get_title()}",
                )
            )

    return results[:50]


@click.command()
@click.option("-S", "--scan", "scan_flag", is_flag=True, help="scan library")
@click.option("-s", "--strict", is_flag=True, help="strict mode (requires metadata)")
@click.option("-d", "--directory", help="scan specific directory")
@click.option(
    "--dd", "--default-directory", "set_default", help="scan and set as default"
)
@click.option("-I", "--install", "install_flag", help="install console/game")
@click.option("-o", "--online", is_flag=True, help="online mode")
@click.option("-u", "--upgrade", is_flag=True, help="upgrade/update")
@click.option("-i", "--info", is_flag=True, help="show detailed info")
@click.option("-f", "--file", "file_path", help="local file path")
@click.option("-F", "--fullscreen", is_flag=True, help="launch in fullscreen")
@click.option("-Q", "--query", "query_flag", is_flag=True, help="query/list mode")
@click.option("-L", "--list", "list_flag", is_flag=True, help="list consoles or games")
@click.option("-c", "--console", "console_filter", help="console filter")
@click.option("--cc", "--console-code", "console_code", help="console code filter")
@click.option(
    "-D", "--database", "database_flag", is_flag=True, help="database/source mode"
)
@click.option("-r", "--remove", help="remove database/source")
@click.option("-C", "--config", "config_flag", is_flag=True, help="config mode")
@click.option("-e", "--edit", is_flag=True, help="edit config")
@click.option("-M", "--manage", help="manage saves/metadata")
@click.option("-V", "--verbose", is_flag=True, help="verbose output")
@click.option("--debug", is_flag=True, help="debug mode with detailed logging")
@click.option("--favorite", is_flag=True, help="toggle favorite status")
@click.option("--args", "custom_args", help="custom launch arguments")
@click.argument("args", nargs=-1)
@click.version_option(version="0.1.0", prog_name="vretro")
def cli(
    scan_flag,
    strict,
    directory,
    set_default,
    install_flag,
    online,
    upgrade,
    info,
    file_path,
    fullscreen,
    query_flag,
    list_flag,
    console_filter,
    console_code,
    database_flag,
    remove,
    config_flag,
    edit,
    manage,
    verbose,
    debug,
    favorite,
    custom_args,
    args,
):
    """vretro - downloader and library management for abandonware"""

    if debug:
        import logging

        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
        term.print("[dim]debug mode enabled[/dim]\n")
        verbose = True

    config = VRetroConfig.load()
    if debug:
        term.print(f"[dim]config loaded from: {get_config_path()}[/dim]")
        term.print(f"[dim]games root: {config.get_games_root()}[/dim]\n")

    library = GameLibrary(
        config.get_games_root(), config.ignored_directories, debug=debug
    )
    db = OnlineDatabase(config)
    sources = SourceManager(debug=debug)

    if manage:
        library.scan(verbose=verbose)
        game = library.get_by_code(manage)

        if not game:
            matches = library.search(manage)
            if matches:
                if len(matches) == 1:
                    game = matches[0]
                else:
                    term.print(f"[yellow]multiple matches for '{manage}':[/yellow]\n")
                    for match in matches[:10]:
                        term.print(
                            f"  {match.metadata.code}: {match.metadata.get_title()}"
                        )
                    return

        if not game:
            term.print(f"[red]game not found: {manage}[/red]")
            return

        term.print(f"[bold cyan]managing {game.metadata.get_title()}[/bold cyan]\n")

        saves = game.get_saves()
        if saves:
            term.print("[bold]saves:[/bold]")
            for save in saves:
                size = save.stat().st_size / 1024
                term.print(f"  {save.name} ({size:.1f} kb)")
        else:
            term.print("[dim]no saves found[/dim]")

        term.print(f"\n[bold]playtime:[/bold] {game.metadata.playtime // 60}m")

        if game.metadata.last_played:
            import time

            played = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(game.metadata.last_played)
            )
            term.print(f"[bold]last played:[/bold] {played}")

        term.print(
            f"[bold]favorite:[/bold] {'yes' if game.metadata.is_favorite else 'no'}"
        )

        if game.metadata.custom_args:
            term.print(
                f"[bold]custom args:[/bold] {' '.join(game.metadata.custom_args)}"
            )

        term.print("\n[dim]actions: backup-save, set-args, toggle-favorite[/dim]")
        try:
            action = input("action: ").lower()

            if action == "backup-save":
                backup_dir = config.get_games_root() / "backups"
                if game.backup_save(backup_dir):
                    term.print("[green]save backed up[/green]")
                else:
                    term.print("[red]backup failed[/red]")

            elif action == "set-args":
                args_input = input("arguments: ")
                game.metadata.custom_args = args_input.split() if args_input else []
                game.metadata.save(game.path / "metadata.json")
                term.print("[green]arguments saved[/green]")

            elif action == "toggle-favorite":
                game.metadata.is_favorite = not game.metadata.is_favorite
                game.metadata.save(game.path / "metadata.json")
                status = "added to" if game.metadata.is_favorite else "removed from"
                term.print(f"[green]{status} favorites[/green]")

        except KeyboardInterrupt:
            term.print("\n[yellow]cancelled[/yellow]")

        return

    if favorite and args:
        library.scan(verbose=verbose)
        game = library.get_by_code(args[0])

        if not game:
            matches = library.search(args[0])
            if matches:
                game = matches[0]

        if game:
            game.metadata.is_favorite = not game.metadata.is_favorite
            game.metadata.save(game.path / "metadata.json")
            status = "favorited" if game.metadata.is_favorite else "unfavorited"
            term.print(f"[green]{status} {game.metadata.get_title()}[/green]")
        else:
            term.print(f"[red]game not found: {args[0]}[/red]")

        return

    if scan_flag:
        scan_dir = None
        if set_default:
            scan_dir = Path(set_default).expanduser()
            config.games_directory = str(scan_dir)
            config.save()
            term.print(f"[green]set default directory: {scan_dir}[/green]")
        elif directory:
            scan_dir = Path(directory).expanduser()

        if scan_dir:
            library = GameLibrary(scan_dir, config.ignored_directories)

        if console_filter or console_code:
            library.scan_consoles(verbose=verbose, generate_metadata=not strict)
            console_dirs = library.list_console_dirs()

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("code", style="dim")
            table.add_column("name")
            table.add_column("status")
            table.add_column("emulator")

            for code, has_metadata in console_dirs:
                if strict and not has_metadata:
                    continue
                meta = library.get_console_metadata(code.upper())
                if meta:
                    table.add_row(
                        code, meta.name, "[green]ok[/green]", meta.emulator.name
                    )
                else:
                    table.add_row(
                        code,
                        "[dim]unknown[/dim]",
                        "[yellow]needs setup[/yellow]",
                        "[dim]none[/dim]",
                    )

            term.print(table)
        else:
            games = library.scan(verbose=verbose)

            if strict:
                games = [g for g in games if (g.path / "metadata.json").exists()]

            if not games:
                term.print("[yellow]no games found[/yellow]")
                return

            term.print(f"[green]found {len(games)} games[/green]\n")

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("code", style="dim")
            table.add_column("title")
            table.add_column("console")
            table.add_column("year")
            table.add_column("favorite", style="yellow")

            for game in sorted(
                games, key=lambda g: (g.metadata.console, g.metadata.get_title())
            ):
                fav = "★" if game.metadata.is_favorite else ""
                table.add_row(
                    game.metadata.code,
                    game.metadata.get_title(),
                    game.metadata.console,
                    str(game.metadata.year),
                    fav,
                )

            term.print(table)
        return

    if install_flag:
        query = (
            install_flag if isinstance(install_flag, str) else args[0] if args else None
        )

        if not query:
            term.print("[red]specify what to install[/red]")
            term.print(
                "[dim]usage: vretro -I <console> or vretro -I <game> -c <console>[/dim]"
            )
            return

        if console_filter:
            if online and info:
                games = db.search_games(query, console_filter)

                if not games:
                    term.print("[yellow]no results found[/yellow]")
                    return

                for game in games[:10]:
                    term.print(f"\n[bold cyan]{game.name}[/bold cyan]")
                    term.print(f"  platform: {game.platform}")
                    term.print(f"  year: {game.year or '?'}")
                    term.print(f"  publisher: {game.publisher or '?'}")
                    if game.cover_url:
                        term.print(f"  cover: {game.cover_url}")
                return

            console_code_upper = console_filter.upper()
            games = sources.search_games(console_code_upper, query)

            if not games:
                term.print(f"[yellow]no games found for {console_code_upper}[/yellow]")
                return

            term.print(f"[green]found {len(games)} games:[/green]\n")
            for i, (game_name, source) in enumerate(games, 1):
                term.print(f"  {i}. {game_name} [{source.scheme}]")

            try:
                choice = input("\ngame number: ")
                idx = int(choice) - 1

                if idx < 0 or idx >= len(games):
                    term.print("[red]invalid selection[/red]")
                    return

                game_name, source = games[idx]

                if directory or file_path:
                    download_dir = Path(directory or ".").expanduser()
                    download_dir.mkdir(parents=True, exist_ok=True)

                    if source.scheme == "switch":
                        dest_file = download_dir / f"{game_name}.zip"
                    elif source.scheme == "arv":
                        dest_file = download_dir / f"{game_name}.zip"
                    else:
                        filename = source.identifier.split("/")[-1]
                        dest_file = download_dir / filename
                else:
                    library.scan_consoles(verbose=verbose)
                    console_meta = library.get_console_metadata(console_code_upper)
                    if not console_meta:
                        term.print(
                            f"[red]console not installed: {console_code_upper}[/red]"
                        )
                        term.print(
                            f"[yellow]run: vretro -I {console_code_upper}[/yellow]"
                        )
                        return

                    console_dir = library.console_root / console_meta.name
                    games_dir = console_dir / "games"

                    import re

                    game_slug = re.sub(r"[^\w\s-]", "", game_name.lower())
                    game_slug = re.sub(r"[-\s]+", "-", game_slug).strip("-")

                    game_dir = games_dir / game_slug
                    game_dir.mkdir(parents=True, exist_ok=True)
                    (game_dir / "resources").mkdir(exist_ok=True)
                    (game_dir / "saves").mkdir(exist_ok=True)

                    download_dir = game_dir / "resources"

                    extension = CONSOLE_EXTENSIONS.get(console_code_upper, "bin")
                    dest_file = download_dir / f"base.{extension}"

                term.print(f"\n[cyan]downloading {game_name}...[/cyan]")

                success = sources.download_file(source, dest_file, game_name)

                if success:
                    term.print(f"[green]downloaded to: {dest_file}[/green]")

                    if not (directory or file_path):
                        term.print("\n[cyan]fetching metadata from igdb...[/cyan]")

                        igdb_games = db.search_games(game_name, console_filter)
                        if igdb_games:
                            igdb_game = igdb_games[0]

                            metadata = GameMetadata(
                                code=f"{console_filter.lower()}-{game_slug}",
                                console=console_code_upper,
                                id=igdb_game.id,
                                title={"NA": igdb_game.name},
                                publisher={"NA": igdb_game.publisher or "unknown"},
                                year=igdb_game.year or 0,
                                region="NA",
                            )
                            metadata.save(game_dir / "metadata.json")

                            launch_cmd = console_meta.emulator.launch_command
                            launch_cmd = launch_cmd.replace(
                                "{binary}", console_meta.emulator.binary
                            )
                            launch_cmd = launch_cmd.replace("{rom}", str(dest_file))

                            launch_script = game_dir / "launch.sh"
                            with open(launch_script, "w") as f:
                                f.write(
                                    "#!/bin/bash\n" if not IS_WINDOWS else "@echo off\n"
                                )
                                f.write(f"{launch_cmd}\n")
                            if not IS_WINDOWS:
                                launch_script.chmod(0o755)

                            term.print(f"[green]created game: {game_slug}[/green]")
                        else:
                            term.print(
                                "[yellow]no igdb metadata found, create metadata.json manually[/yellow]"
                            )
                else:
                    term.print("[red]download failed[/red]")
            except (ValueError, KeyboardInterrupt):
                term.print("\n[yellow]cancelled[/yellow]")
            return

        if online and upgrade:
            term.print("[cyan]checking for emulator updates...[/cyan]")
            library.scan_consoles(verbose=verbose)

            updates_found = False
            for code, console_meta in library.consoles.items():
                console_dir = library.console_root / console_meta.name
                emulator_dir = console_dir / "emulator"

                if console_meta.emulator.download_url:
                    term.print(f"\n[bold]{console_meta.name}[/bold]")
                    term.print(f"  emulator: {console_meta.emulator.name}")

                    if emulator_dir.exists() and any(emulator_dir.iterdir()):
                        term.print("  [green]installed[/green]")

                        try:
                            choice = input("  download latest? [y/N]: ").lower()
                            if choice == "y":
                                if download_emulator(
                                    code,
                                    console_meta.emulator.name,
                                    console_meta.emulator.download_url,
                                    emulator_dir,
                                ):
                                    term.print("  [green]updated[/green]")
                        except KeyboardInterrupt:
                            term.print("\n[yellow]cancelled[/yellow]")
                            break
                    else:
                        term.print("  [yellow]not installed[/yellow]")
                        updates_found = True

                        try:
                            choice = input("  download? [y/N]: ").lower()
                            if choice == "y":
                                if download_emulator(
                                    code,
                                    console_meta.emulator.name,
                                    console_meta.emulator.download_url,
                                    emulator_dir,
                                ):
                                    term.print("  [green]installed[/green]")
                        except KeyboardInterrupt:
                            term.print("\n[yellow]cancelled[/yellow]")
                            break

            if not updates_found and not any(
                c.emulator.download_url for c in library.consoles.values()
            ):
                term.print("[green]all emulators installed[/green]")
            return

        library.scan(verbose=verbose)
        library.scan_consoles(verbose=verbose)

        results = fuzzy_search_all(query, library, sources)

        if not results:
            term.print(f"[yellow]no results found for: {query}[/yellow]")
            return

        term.print(f"[cyan]search results for '{query}':[/cyan]\n")

        consoles = [r for r in results if r[0] == "console"]
        games = [r for r in results if r[0] == "game"]

        if consoles:
            term.print("[bold]consoles:[/bold]")
            for i, (_, code, name) in enumerate(consoles, 1):
                term.print(f"  {i}. console/{name}")

        if games:
            term.print("\n[bold]games:[/bold]")
            for i, (_, code, name) in enumerate(games, len(consoles) + 1):
                term.print(f"  {i}. {name}")

        try:
            choice = input("\nselect number to install (or press enter to cancel): ")
            if not choice:
                return

            idx = int(choice) - 1
            if idx < 0 or idx >= len(results):
                term.print("[red]invalid selection[/red]")
                return

            result_type, code, name = results[idx]

            if result_type == "console":
                meta = get_console_metadata(code.upper())
                if meta:
                    console_dir = library.create_console(code.upper(), meta)
                    term.print(f"[green]created console: {code.upper()}[/green]")
                    term.print(f"  {meta.name}")
                    term.print(f"  path: {console_dir}")
                    term.print(f"  emulator: {meta.emulator.name}")

                    if meta.emulator.requires_bios:
                        term.print("\n[yellow]requires bios files:[/yellow]")
                        for bios in meta.emulator.bios_files:
                            term.print(f"  {bios}")

                        resources_dir = console_dir / "resources"
                        term.print(f"\n[dim]place bios files in: {resources_dir}[/dim]")
                        if code.upper() == "SWITCH":
                            term.print(
                                "[dim]for switch: prod.keys and firmware.zip from your console[/dim]"
                            )

                    if meta.emulator.download_url:
                        term.print("\n[yellow]download emulator?[/yellow]")
                        try:
                            dl_choice = input("  [y/N]: ").lower()
                            if dl_choice == "y":
                                emulator_dir = console_dir / "emulator"
                                download_emulator(
                                    code,
                                    meta.emulator.name,
                                    meta.emulator.download_url,
                                    emulator_dir,
                                )
                        except KeyboardInterrupt:
                            term.print("\n[yellow]skipped emulator download[/yellow]")
                else:
                    term.print(f"[red]unknown console: {code}[/red]")
            else:
                term.print(
                    "[yellow]to download games, use: vretro -I <game name> -c <console>[/yellow]"
                )
                parts = name.split("/")
                if len(parts) == 2:
                    term.print(
                        f'[dim]example: vretro -I "{parts[1]}" -c {parts[0]}[/dim]'
                    )

        except (ValueError, KeyboardInterrupt):
            term.print("\n[yellow]cancelled[/yellow]")
        return

    if list_flag or query_flag:
        library.scan(verbose=verbose)

        if console_code:
            games = library.filter_by_console(console_code.upper())

            if not games:
                term.print(f"[yellow]no games found for: {console_code}[/yellow]")
                return

            term.print(f"[green]found {len(games)} games for {console_code}[/green]\n")

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("code", style="dim")
            table.add_column("title")
            table.add_column("year")
            table.add_column("playtime", style="dim")

            for game in sorted(games, key=lambda g: g.metadata.get_title()):
                playtime = (
                    f"{game.metadata.playtime // 60}m"
                    if game.metadata.playtime
                    else "-"
                )
                table.add_row(
                    game.metadata.code,
                    game.metadata.get_title(),
                    str(game.metadata.year),
                    playtime,
                )

            term.print(table)
            return

        if console_filter:
            library.scan_consoles(verbose=verbose)
            console_dirs = library.list_console_dirs()

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("code", style="dim")
            table.add_column("name")
            table.add_column("games")

            for code, has_metadata in console_dirs:
                meta = library.get_console_metadata(code.upper())
                games = library.filter_by_console(code.upper())
                game_count = len(games)
                if meta:
                    table.add_row(code, meta.name, str(game_count))

            term.print(table)
            return

        if info and args:
            query = args[0]

            game = library.get_by_code(query)
            if game:
                m = game.metadata

                if config.show_thumbnails and SIXEL_AVAILABLE:
                    thumb_path = game.get_thumbnail_path()
                    if thumb_path:
                        display_thumbnail(thumb_path, config.thumbnail_width)
                        term.print()

                term.print(f"[bold cyan]{m.get_title()}[/bold cyan]")
                term.print(f"[dim]{'-' * len(m.get_title())}[/dim]\n")

                term.print(f"[bold]code:[/bold] {m.code}")
                term.print(f"[bold]console:[/bold] {m.console}")
                term.print(f"[bold]year:[/bold] {m.year}")
                term.print(f"[bold]region:[/bold] {m.region}")

                if m.playtime:
                    hours = m.playtime // 3600
                    minutes = (m.playtime % 3600) // 60
                    if hours:
                        term.print(f"[bold]playtime:[/bold] {hours}h {minutes}m")
                    else:
                        term.print(f"[bold]playtime:[/bold] {minutes}m")

                if m.is_favorite:
                    term.print("[bold]favorite:[/bold] ★")

                term.print("\n[bold]publishers:[/bold]")
                for region, pub in m.publisher.items():
                    term.print(f"  {region}: {pub}")

                term.print("\n[bold]titles:[/bold]")
                for region, title in m.title.items():
                    term.print(f"  {region}: {title}")

                term.print("\n[bold]paths:[/bold]")
                term.print(f"  game: {game.path}")
                term.print(f"  rom: {game.rom_path}")
                term.print(f"  saves: {game.saves_path}")
                return

            library.scan_consoles(verbose=verbose)
            meta = library.get_console_metadata(query.upper())
            if meta:
                term.print(f"[bold cyan]{meta.name}[/bold cyan]")
                term.print(f"[dim]{'-' * len(meta.name)}[/dim]\n")

                term.print(f"[bold]code:[/bold] {meta.code}")
                term.print(f"[bold]manufacturer:[/bold] {meta.manufacturer}")
                term.print(f"[bold]release:[/bold] {meta.release}")
                if meta.generation:
                    term.print(f"[bold]generation:[/bold] {meta.generation}")

                term.print(f"\n[bold]formats:[/bold] {', '.join(meta.formats)}")

                term.print("\n[bold]emulator:[/bold]")
                term.print(f"  name: {meta.emulator.name}")
                term.print(f"  binary: {meta.emulator.binary}")

                if meta.emulator.requires_bios:
                    term.print("\n[bold]required bios:[/bold]")
                    for bios in meta.emulator.bios_files:
                        term.print(f"  {bios}")
                return

            term.print(f"[red]not found: {query}[/red]")
            return

        if args and args[0] == "favorites":
            favorites = library.get_favorites()

            if not favorites:
                term.print("[yellow]no favorites[/yellow]")
                return

            term.print(f"[green]found {len(favorites)} favorites[/green]\n")

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("code", style="dim")
            table.add_column("title")
            table.add_column("console")
            table.add_column("playtime", style="dim")

            for game in sorted(favorites, key=lambda g: g.metadata.get_title()):
                playtime = (
                    f"{game.metadata.playtime // 60}m"
                    if game.metadata.playtime
                    else "-"
                )
                table.add_row(
                    game.metadata.code,
                    game.metadata.get_title(),
                    game.metadata.console,
                    playtime,
                )

            term.print(table)
            return

        if args and args[0] == "recent":
            recent = library.get_recently_played()

            if not recent:
                term.print("[yellow]no recently played games[/yellow]")
                return

            term.print("[cyan]recently played:[/cyan]\n")

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("code", style="dim")
            table.add_column("title")
            table.add_column("console")
            table.add_column("playtime", style="dim")

            for game in recent:
                playtime = (
                    f"{game.metadata.playtime // 60}m"
                    if game.metadata.playtime
                    else "-"
                )
                table.add_row(
                    game.metadata.code,
                    game.metadata.get_title(),
                    game.metadata.console,
                    playtime,
                )

            term.print(table)
            return

        games = library.games
        consoles = library.get_consoles()

        term.print(f"[cyan]consoles: {', '.join(consoles)}[/cyan]\n")
        term.print(f"[green]found {len(games)} games[/green]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("code", style="dim")
        table.add_column("title")
        table.add_column("console")
        table.add_column("year")

        for game in sorted(
            games, key=lambda g: (g.metadata.console, g.metadata.get_title())
        ):
            table.add_row(
                game.metadata.code,
                game.metadata.get_title(),
                game.metadata.console,
                str(game.metadata.year),
            )

        term.print(table)
        return

    if database_flag:
        if remove:
            term.print("[yellow]remove not yet implemented[/yellow]")
            return

        if info and file_path:
            term.print("[yellow]add database from file not yet implemented[/yellow]")
            return

        if directory:
            term.print("[cyan]databases:[/cyan]\n")
            term.print("  igdb - internet game database")
            term.print("  vrdb - vretro console databases")
            return

        if online:
            consoles = sources.list_consoles()

            if not consoles:
                term.print("[yellow]no console databases found[/yellow]")
                term.print(f"[dim]looking in: {sources.vrdb.db_dir}[/dim]")
                return

            term.print("[cyan]vrdb consoles:[/cyan]\n")

            for code in consoles:
                vrdb_console = sources.vrdb.get_console(code)
                if vrdb_console:
                    game_count = len(vrdb_console.games)
                    term.print(f"  [bold]{code}[/bold] - {vrdb_console.console.name}")
                    term.print(f"    games: {game_count}")
                    term.print(f"    emulator: {vrdb_console.emulator.name}\n")
            return

        term.print("[cyan]databases:[/cyan]")
        term.print("  igdb - game metadata")
        term.print("  vrdb - console and game databases\n")

        term.print("[cyan]vrdb consoles:[/cyan]")
        for code in sources.list_consoles():
            term.print(f"  {code}")
        return

    if config_flag:
        if edit and len(args) >= 2:
            key, value = args[0], args[1]

            bool_keys = ["fullscreen", "use_gamescope", "show_thumbnails"]
            int_keys = ["gamescope_width", "gamescope_height", "thumbnail_width"]
            list_keys = ["download_sources", "ignored_directories"]

            if key in bool_keys:
                value = value.lower() in ["true", "1", "yes", "on"]
            elif key in int_keys:
                value = int(value)
            elif key in list_keys:
                value = [s.strip() for s in value.split(",")]

            if hasattr(config, key):
                setattr(config, key, value)
                config.save()
                term.print(f"[green]set {key} = {value}[/green]")
            else:
                term.print(f"[red]unknown key: {key}[/red]")
            return

        term.print("[bold cyan]vretro configuration[/bold cyan]\n")
        term.print(f"[bold]games directory:[/bold] {config.games_directory}")
        term.print(
            f"[bold]ignored directories:[/bold] {', '.join(config.ignored_directories)}"
        )
        term.print(f"[bold]fullscreen:[/bold] {str(config.fullscreen).lower()}")
        term.print(f"[bold]use gamescope:[/bold] {str(config.use_gamescope).lower()}")
        term.print(
            f"[bold]gamescope resolution:[/bold] {config.gamescope_width}x{config.gamescope_height}"
        )
        term.print(
            f"[bold]show thumbnails:[/bold] {str(config.show_thumbnails).lower()}"
        )
        term.print(f"[bold]thumbnail width:[/bold] {config.thumbnail_width}px")
        term.print(f"[bold]preferred region:[/bold] {config.preferred_region}")

        igdb_status = "configured" if config.igdb_client_id else "not configured"
        term.print(f"[bold]igdb api:[/bold] {igdb_status}")

        if config.download_sources:
            term.print(
                f"[bold]download sources:[/bold] {', '.join(config.download_sources)}"
            )

        term.print(f"\n[dim]config file: {get_config_path()}[/dim]")
        term.print(f"[dim]platform: {'windows' if IS_WINDOWS else 'linux'}[/dim]")
        return

    if args:
        game_query = args[0]
        library.scan(verbose=verbose)

        game = library.get_by_code(game_query)

        if not game:
            matches = library.search(game_query)
            if matches:
                if len(matches) == 1:
                    game = matches[0]
                else:
                    term.print(
                        f"[yellow]multiple matches for '{game_query}':[/yellow]\n"
                    )
                    for i, match in enumerate(matches[:10], 1):
                        fav = "★" if match.metadata.is_favorite else " "
                        term.print(
                            f"  {i}. {fav} {match.metadata.code}: {match.metadata.get_title()}"
                        )

                    try:
                        choice = input("\nselect number: ")
                        idx = int(choice) - 1
                        if 0 <= idx < len(matches):
                            game = matches[idx]
                    except (ValueError, KeyboardInterrupt):
                        term.print("\n[yellow]cancelled[/yellow]")
                        return

        if not game:
            term.print(f"[red]game not found: {game_query}[/red]")
            return

        extra_args = None
        if custom_args:
            extra_args = custom_args.split()

        term.print(f"[cyan]launching {game.metadata.get_title()}...[/cyan]")
        launch_game(
            game,
            config,
            library,
            fullscreen=fullscreen,
            extra_args=extra_args,
            verbose=verbose,
            debug=debug,
        )
        return

    ctx = click.get_current_context()
    click.echo(ctx.get_help())


if __name__ == "__main__":
    cli()
