from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.data.config import VRetroConfig
from src.data.library import GameLibrary
from src.util.compression import (
    compress_game_directory,
    decompress_game_directory,
    is_compressed,
)

term = Console()


@click.command()
@click.option("-C", "--compress", is_flag=True, help="compress rom files")
@click.option("-D", "--decompress", is_flag=True, help="decompress rom files")
@click.option(
    "-t",
    "--type",
    "compression_type",
    default="7z",
    help="compression type (7z, zip)",
)
@click.option("-l", "--level", default=9, help="compression level (1-9)")
@click.option("-V", "--verbose", is_flag=True, help="verbose output")
@click.argument("args", nargs=-1)
def compress_cli(compress, decompress, compression_type, level, verbose, args):
    """compress or decompress game roms"""

    config = VRetroConfig.load()
    library = GameLibrary(config.get_games_root(), config.ignored_directories)

    if compress and decompress:
        term.print("[red]cannot compress and decompress at the same time[/red]")
        return

    if not compress and not decompress:
        library.scan(verbose=False)

        compressed_games = []
        uncompressed_games = []

        for game in library.games:
            resources_dir = game.path / "resources"
            if not resources_dir.exists():
                continue

            base_files = list(resources_dir.glob("base.*"))
            if not base_files:
                continue

            if any(is_compressed(f) for f in base_files):
                compressed_games.append(game)
            else:
                uncompressed_games.append(game)

        term.print(f"[cyan]compression status:[/cyan]\n")
        term.print(f"compressed:   {len(compressed_games)} games")
        term.print(f"uncompressed: {len(uncompressed_games)} games")

        if verbose:
            if compressed_games:
                term.print("\n[bold]compressed games:[/bold]")
                for game in compressed_games:
                    term.print(f"  {game.metadata.get_title()}")

            if uncompressed_games:
                term.print("\n[bold]uncompressed games:[/bold]")
                for game in uncompressed_games:
                    term.print(f"  {game.metadata.get_title()}")
        return

    library.scan(verbose=False)

    if args:
        game_query = args[0]
        game = library.get_by_code(game_query)

        if not game:
            matches = library.search(game_query)
            if matches and len(matches) == 1:
                game = matches[0]
            else:
                term.print(f"[red]game not found: {game_query}[/red]")
                return

        if compress:
            term.print(f"[cyan]compressing {game.metadata.get_title()}...[/cyan]")
            success = compress_game_directory(
                game.path, compression_type, level, verbose
            )
            if success:
                term.print("[green]compression complete[/green]")
            else:
                term.print("[red]compression failed[/red]")
        elif decompress:
            term.print(f"[cyan]decompressing {game.metadata.get_title()}...[/cyan]")
            success = decompress_game_directory(game.path, verbose)
            if success:
                term.print("[green]decompression complete[/green]")
            else:
                term.print("[red]decompression failed[/red]")
    else:
        if compress:
            term.print("[cyan]compressing all uncompressed games...[/cyan]\n")
            success_count = 0
            for game in library.games:
                resources_dir = game.path / "resources"
                if not resources_dir.exists():
                    continue

                base_files = list(resources_dir.glob("base.*"))
                if not base_files:
                    continue

                if any(is_compressed(f) for f in base_files):
                    continue

                term.print(f"compressing {game.metadata.get_title()}...")
                success = compress_game_directory(
                    game.path, compression_type, level, verbose
                )
                if success:
                    success_count += 1

            term.print(f"\n[green]compressed {success_count} games[/green]")

        elif decompress:
            term.print("[cyan]decompressing all compressed games...[/cyan]\n")
            success_count = 0
            for game in library.games:
                resources_dir = game.path / "resources"
                if not resources_dir.exists():
                    continue

                base_files = list(resources_dir.glob("base.*"))
                if not base_files:
                    continue

                if not any(is_compressed(f) for f in base_files):
                    continue

                term.print(f"decompressing {game.metadata.get_title()}...")
                success = decompress_game_directory(game.path, verbose)
                if success:
                    success_count += 1

            term.print(f"\n[green]decompressed {success_count} games[/green]")


if __name__ == "__main__":
    compress_cli()
