import os
import platform
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from ..data.config import VRetroConfig
from ..data.library import GameEntry, GameLibrary

term = Console()
IS_WINDOWS = platform.system() == "Windows"


def find_emulator_binary(emulator_dir: Path, binary_name: str) -> Optional[Path]:
    if IS_WINDOWS and not binary_name.endswith(".exe"):
        binary_name += ".exe"

    for file in emulator_dir.rglob(binary_name):
        return file

    emulator_binary = emulator_dir / binary_name
    return emulator_binary if emulator_binary.exists() else None


def setup_library_path(emulator_dir: Path, binary_name: str):
    lib_dirs = []

    emulator_lib = emulator_dir / "lib"
    if emulator_lib.exists():
        lib_dirs.append(str(emulator_lib))

    parent_lib = emulator_dir.parent / "lib"
    if parent_lib.exists():
        lib_dirs.append(str(parent_lib))

    if lib_dirs:
        current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        if current_ld_path:
            lib_dirs.append(current_ld_path)
        os.environ["LD_LIBRARY_PATH"] = ":".join(lib_dirs)


def prepare_rom(game: GameEntry, verbose: bool = False) -> Optional[Path]:
    from .compression import decompress_rom, is_compressed

    resources_dir = game.path / "resources"
    if not resources_dir.exists():
        return None

    base_files = list(resources_dir.glob("base.*"))
    if not base_files:
        return None

    base_file = base_files[0]

    if is_compressed(base_file):
        if verbose:
            term.print(f"[dim]decompressing {base_file.name}...[/dim]")

        temp_dir = game.path / ".temp"
        temp_dir.mkdir(exist_ok=True)

        decompressed = decompress_rom(base_file, temp_dir)
        if not decompressed:
            term.print("[red]failed to decompress rom[/red]")
            return None

        return decompressed

    return base_file


def cleanup_temp(game: GameEntry):
    temp_dir = game.path / ".temp"
    if temp_dir.exists():
        import shutil

        shutil.rmtree(temp_dir)


def apply_mods(game: GameEntry, verbose: bool = False) -> bool:
    from .mods import ModManager

    mod_manager = ModManager(game.path)
    enabled_mods = [m for m in mod_manager.mods if m.enabled]

    if not enabled_mods:
        return True

    if verbose:
        term.print(f"[cyan]applying {len(enabled_mods)} mods...[/cyan]")

    for mod in enabled_mods:
        mod_dir = game.path / "mods" / mod.name
        if not mod_dir.exists():
            if verbose:
                term.print(f"[yellow]mod not found: {mod.name}[/yellow]")
            continue

        if mod.install_path:
            install_path = Path(mod.install_path).expanduser() / mod.name
        else:
            install_path = game.path / "active_mods" / mod.name

        install_path.mkdir(parents=True, exist_ok=True)

        if verbose:
            term.print(f"[dim]copying {mod.name} to {install_path}[/dim]")

        try:
            if install_path.exists():
                shutil.rmtree(install_path)

            shutil.copytree(
                mod_dir, install_path, ignore=shutil.ignore_patterns("mod.json")
            )
        except Exception as e:
            if verbose:
                term.print(f"[red]failed to copy {mod.name}: {e}[/red]")
            return False

    return True


def build_launch_command(
    game: GameEntry,
    library: GameLibrary,
    emulator_binary: Path,
    binary_name: str,
    rom_path: Path,
    use_fullscreen: bool,
    debug: bool = False,
) -> list[str]:
    console_meta = library.get_console_metadata(game.metadata.console)
    if not console_meta:
        return []

    launch_template = console_meta.emulator.launch_command

    launch_cmd = launch_template.replace("{binary}", f'"{emulator_binary}"')
    launch_cmd = launch_cmd.replace("{rom}", f'"{rom_path}"')

    if use_fullscreen and "{fullscreen}" in launch_cmd:
        launch_cmd = launch_cmd.replace("{fullscreen}", "--fullscreen")
    elif "{fullscreen}" in launch_cmd:
        launch_cmd = launch_cmd.replace("{fullscreen}", "")

    if "{saves}" in launch_cmd:
        launch_cmd = launch_cmd.replace("{saves}", f'"{game.saves_path}"')

    if "{config}" in launch_cmd:
        config_dir = game.path.parent.parent / "config"
        config_dir.mkdir(exist_ok=True)
        launch_cmd = launch_cmd.replace("{config}", f'"{config_dir}"')

    if "{portable}" in launch_cmd:
        portable_dir = game.path.parent.parent / "portable"
        portable_dir.mkdir(exist_ok=True)
        launch_cmd = launch_cmd.replace("{portable}", f'"{portable_dir}"')

    return shlex.split(launch_cmd)


def launch_game(
    game: GameEntry,
    config: VRetroConfig,
    library: GameLibrary,
    fullscreen: Optional[bool] = None,
    save_path: Optional[Path] = None,
    emulator: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
    verbose: bool = False,
    debug: bool = False,
) -> bool:
    game.saves_path.mkdir(parents=True, exist_ok=True)

    console_meta = library.get_console_metadata(game.metadata.console)
    if not console_meta:
        term.print("[red]console metadata not found[/red]")
        return False

    emulator_dir = game.path.parent.parent / "emulator"
    binary_name = emulator or console_meta.emulator.binary

    emulator_binary = find_emulator_binary(emulator_dir, binary_name)
    if not emulator_binary:
        term.print(f"[red]emulator not found: {binary_name}[/red]")
        term.print(f"[yellow]install emulator to: {emulator_dir}[/yellow]")
        return False

    setup_library_path(emulator_dir, binary_name)

    if not apply_mods(game, verbose):
        term.print("[yellow]warning: failed to apply some mods[/yellow]")

    rom_path = prepare_rom(game, verbose)
    if not rom_path:
        term.print("[red]rom file not found[/red]")
        return False

    use_fullscreen = fullscreen if fullscreen is not None else config.fullscreen

    cmd = build_launch_command(
        game, library, emulator_binary, binary_name, rom_path, use_fullscreen, debug
    )

    if not cmd:
        term.print("[red]failed to build launch command[/red]")
        cleanup_temp(game)
        return False

    if save_path:
        if verbose:
            term.print(f"[dim]using save: {save_path}[/dim]")
        os.environ["VRETRO_SAVE"] = str(save_path)

    if config.use_gamescope and not IS_WINDOWS:
        cmd = [
            "gamescope",
            "-w",
            str(config.gamescope_width),
            "-h",
            str(config.gamescope_height),
            "-f" if use_fullscreen else "-b",
            "--",
        ] + cmd

    if game.metadata.custom_args:
        cmd.extend(game.metadata.custom_args.split())

    if extra_args:
        cmd.extend(extra_args)

    if verbose:
        term.print(f"[dim]command: {' '.join(cmd)}[/dim]")

    start_time = time.time()

    try:
        subprocess.run(cmd, check=True)

        elapsed = int(time.time() - start_time)
        game.metadata.update_playtime(elapsed)

        metadata_file = game.path / "metadata.json"
        game.metadata.save(metadata_file)

        if verbose:
            term.print(f"[dim]played for {elapsed // 60}m {elapsed % 60}s[/dim]")

        cleanup_temp(game)
        return True
    except subprocess.CalledProcessError as e:
        term.print(f"[red]launch failed: {e}[/red]")
        cleanup_temp(game)
        return False
    except FileNotFoundError as e:
        term.print(f"[red]emulator binary not found: {emulator_binary} ({e})[/red]")
        cleanup_temp(game)
        return False
