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
@click.option("-S", "--sync", "sync_flag", is_flag=True, help="install console/game")
@click.option("-s", "--search", "search_flag", is_flag=True, help="search databases")
@click.option("-i", "--info", is_flag=True, help="show detailed info")
@click.option("-u", "--sysupgrade", is_flag=True, help="upgrade emulators")
@click.option("-y", "--refresh", is_flag=True, help="refresh databases")
@click.option("-Q", "--query", "query_flag", is_flag=True, help="query installed")
@click.option("-c", "--console", "console_filter", help="console filter")
@click.option("-F", "--favorite", is_flag=True, help="mark as favorite")
@click.option("-R", "--remove", "remove_flag", help="remove game/console")
@click.option("-C", "--config", "config_flag", is_flag=True, help="config mode")
@click.option("--set", "config_set", nargs=2, help="set config key value")
@click.option("-f", "--fullscreen", is_flag=True, help="launch fullscreen")
@click.option("-d", "--directory", help="directory for operations")
@click.option("--strict", is_flag=True, help="strict mode (requires metadata)")
@click.option("-V", "--verbose", is_flag=True, help="verbose output")
@click.option("--debug", is_flag=True, help="debug mode")
@click.argument("args", nargs=-1)
@click.version_option(version="0.1.0", prog_name="vretro")
def cli(
    sync_flag,
    search_flag,
    info,
    sysupgrade,
    refresh,
    query_flag,
    console_filter,
    favorite,
    remove_flag,
    config_flag,
    config_set,
    fullscreen,
    directory,
    strict,
    verbose,
    debug,
    args,
):
    """vretro - downloader and library manager for abandonware"""

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

    if config_flag:
        if config_set:
            key, value = config_set

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

        steamgriddb_status = (
            "configured" if config.steamgrid_api_key else "not configured"
        )
        term.print(f"[bold]steamgriddb api:[/bold] {steamgriddb_status}")

        if config.download_sources:
            term.print(
                f"[bold]download sources:[/bold] {', '.join(config.download_sources)}"
            )

        term.print(f"\n[dim]config file: {get_config_path()}[/dim]")
        term.print(f"[dim]platform: {'windows' if IS_WINDOWS else 'linux'}[/dim]")
        return

    if sync_flag and sysupgrade:
        term.print("[cyan]checking for emulator updates...[/cyan]")
        library.scan_consoles(verbose=verbose)

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
        return

    if sync_flag and search_flag:
        if not args:
            term.print("[red]specify search query[/red]")
            return

        query = args[0]
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
                term.print(f"  {i}. {name}")

        if games:
            term.print("\n[bold]games:[/bold]")
            for i, (_, code, name) in enumerate(games, len(consoles) + 1):
                term.print(f"  {i}. {name}")
        return

    if sync_flag and info:
        if not args:
            term.print("[red]specify search query[/red]")
            return

        query = args[0]

        if console_filter:
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

        library.scan(verbose=verbose)
        library.scan_consoles(verbose=verbose)

        results = fuzzy_search_all(query, library, sources)

        if not results:
            term.print(f"[yellow]no results found for: {query}[/yellow]")
            return

        for result_type, code, name in results[:10]:
            if result_type == "console":
                meta = library.get_console_metadata(code.upper())
                if meta:
                    term.print(f"\n[bold cyan]{meta.name}[/bold cyan]")
                    term.print(f"  code: {meta.code}")
                    term.print(f"  manufacturer: {meta.manufacturer}")
                    term.print(f"  release: {meta.release}")
                    term.print(f"  emulator: {meta.emulator.name}")
            else:
                term.print(f"\n[bold cyan]{name}[/bold cyan]")
                term.print(f"  code: {code}")
        return

    if sync_flag:
        if not args:
            term.print("[red]specify what to install[/red]")
            term.print("[dim]usage: vretro -S <query>[/dim]")
            return

        query = args[0]

        library.scan(verbose=verbose)
        library.scan_consoles(verbose=verbose)

        results = fuzzy_search_all(query, library, sources)

        if not results:
            term.print(f"[yellow]no results found for: {query}[/yellow]")
            return

        if len(results) == 1:
            result_type, code, name = results[0]
        else:
            term.print(f"[cyan]search results for '{query}':[/cyan]\n")

            consoles = [r for r in results if r[0] == "console"]
            games = [r for r in results if r[0] == "game"]

            display_order = consoles + games

            if consoles:
                term.print("[bold]consoles:[/bold]")
                for i, (_, code, name) in enumerate(consoles, 1):
                    term.print(f"  {i}. {name}")

            if games:
                term.print("\n[bold]games:[/bold]")
                for i, (_, code, name) in enumerate(games, len(consoles) + 1):
                    term.print(f"  {i}. {name}")

            try:
                choice = input("\nselect number (or press enter to cancel): ")
                if not choice:
                    return

                idx = int(choice) - 1
                if idx < 0 or idx >= len(display_order):
                    term.print("[red]invalid selection[/red]")
                    return

                result_type, code, name = display_order[idx]

            except (ValueError, KeyboardInterrupt):
                term.print("\n[yellow]cancelled[/yellow]")
                return

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
            if not console_filter:
                parts = name.split("/")
                if len(parts) == 2:
                    console_filter = parts[0]
                    game_name = parts[1]
                else:
                    term.print("[red]specify console with -c[/red]")
                    return
            else:
                game_name = name.split("/")[-1] if "/" in name else name

            console_code_upper = console_filter.upper()
            games = sources.search_games(console_code_upper, game_name)

            if not games:
                term.print("[yellow]no games found[/yellow]")
                return

            if len(games) > 1:
                term.print(f"[green]found {len(games)} games:[/green]\n")
                for i, (gname, source) in enumerate(games, 1):
                    term.print(f"  {i}. {gname} [{source.scheme}]")

                try:
                    choice = input("\ngame number: ")
                    idx = int(choice) - 1

                    if idx < 0 or idx >= len(games):
                        term.print("[red]invalid selection[/red]")
                        return

                    game_name, source = games[idx]
                except (ValueError, KeyboardInterrupt):
                    term.print("\n[yellow]cancelled[/yellow]")
                    return
            else:
                game_name, source = games[0]

            library.scan_consoles(verbose=verbose)
            console_meta = library.get_console_metadata(console_code_upper)
            if not console_meta:
                term.print(f"[red]console not installed: {console_code_upper}[/red]")
                term.print(f"[yellow]run: vretro -S {console_code_upper}[/yellow]")
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
                    term.print(f"[green]created game: {game_slug}[/green]")
                else:
                    term.print(
                        "[yellow]no igdb metadata found, create metadata.json manually[/yellow]"
                    )
            else:
                term.print("[red]download failed[/red]")
        return

    if query_flag:
        library.scan(verbose=verbose)

        if favorite:
            games = [g for g in library.games if g.metadata.favorite]
            if not games:
                term.print("[yellow]no favorites[/yellow]")
                return
            term.print(f"[cyan]favorites ({len(games)})[/cyan]\n")
        else:
            games = library.games

        if console_filter:
            games = [g for g in games if g.metadata.console == console_filter.upper()]

        if not games:
            term.print("[yellow]no games found[/yellow]")
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

                term.print(f"[bold]console:[/bold] {m.console}")
                term.print(f"[bold]year:[/bold] {m.year}")
                term.print(f"[bold]region:[/bold] {m.region}")

                if m.favorite:
                    term.print("[bold]favorite:[/bold] [yellow]★[/yellow]")

                if m.playtime > 0:
                    hours = m.playtime // 3600
                    minutes = (m.playtime % 3600) // 60
                    term.print(f"[bold]playtime:[/bold] {hours}h {minutes}m")

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

        consoles = library.get_consoles()
        term.print(f"[cyan]consoles: {', '.join(consoles)}[/cyan]")
        term.print(f"[cyan]games: {len(games)}[/cyan]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("title")
        table.add_column("console")
        table.add_column("year")
        table.add_column("playtime")
        table.add_column("fav")

        for game in sorted(
            games, key=lambda g: (g.metadata.console, g.metadata.get_title())
        ):
            hours = game.metadata.playtime // 3600
            minutes = (game.metadata.playtime % 3600) // 60
            playtime_str = f"{hours}h {minutes}m" if game.metadata.playtime > 0 else "-"
            fav_str = "[yellow]★[/yellow]" if game.metadata.favorite else ""

            table.add_row(
                game.metadata.get_title(),
                game.metadata.console,
                str(game.metadata.year),
                playtime_str,
                fav_str,
            )

        term.print(table)
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
                    for match in matches[:10]:
                        term.print(f"  {match.metadata.get_title()}")
                    return

        if not game:
            term.print(f"[red]game not found: {game_query}[/red]")
            return

        if favorite:
            game.metadata.favorite = not game.metadata.favorite
            game.metadata.save(game.path / "metadata.json")
            status = "added to" if game.metadata.favorite else "removed from"
            term.print(f"[green]{status} favorites[/green]")
            return

        term.print(f"[cyan]launching {game.metadata.get_title()}...[/cyan]")
        import time

        start_time = time.time()
        success = launch_game(
            game, config, library, fullscreen=fullscreen, verbose=verbose, debug=debug
        )
        if success:
            elapsed = int(time.time() - start_time)
            game.metadata.playtime += elapsed
            game.metadata.save(game.path / "metadata.json")
        return

    ctx = click.get_current_context()
    click.echo(ctx.get_help())


if __name__ == "__main__":
    cli()
