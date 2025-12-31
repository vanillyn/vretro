import os
import platform
import subprocess
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


def build_launch_command(
    game: GameEntry,
    library: GameLibrary,
    emulator_binary: Path,
    binary_name: str,
    use_fullscreen: bool,
    debug: bool = False,
) -> list[str]:
    console_meta = library.get_console_metadata(game.metadata.console)
    if not console_meta:
        return []

    emulator_dir = game.path.parent.parent / "emulator"

    if "mupen64plus" in binary_name.lower():
        return _build_mupen64plus_command(
            emulator_binary, emulator_dir, game, use_fullscreen, debug
        )

    elif "ryujinx" in binary_name.lower():
        return _build_ryujinx_command(emulator_binary, emulator_dir, game)

    else:
        return _build_generic_command(
            console_meta.emulator.launch_command,
            emulator_binary,
            game.rom_path,
            use_fullscreen,
        )


def _build_mupen64plus_command(
    binary: Path,
    emulator_dir: Path,
    game: GameEntry,
    fullscreen: bool,
    debug: bool,
) -> list[str]:
    portable_config = emulator_dir.parent / "config"
    portable_config.mkdir(exist_ok=True)

    cmd = [str(binary)]

    if fullscreen:
        cmd.append("--fullscreen")

    if debug:
        cmd.extend(["--debug", "--emumode", "0"])

    cmd.extend(["--configdir", str(portable_config)])

    if game.metadata.has_dlc or game.metadata.has_updates:
        dlc_dir = game.resources_path / "dlc"
        if dlc_dir.exists():
            cmd.extend(["--plugindir", str(dlc_dir)])

    cmd.append(str(game.rom_path))
    return cmd


def _build_ryujinx_command(
    binary: Path, emulator_dir: Path, game: GameEntry
) -> list[str]:
    import shutil

    portable_dir = emulator_dir.parent / "portable"
    portable_dir.mkdir(exist_ok=True)

    cmd = [str(binary), "-r", str(portable_dir)]

    dlc_dir = game.resources_path / "dlc"
    updates_dir = game.resources_path / "updates"

    if dlc_dir.exists() or updates_dir.exists():
        patches_dir = portable_dir / "patchesAndDlc"
        patches_dir.mkdir(parents=True, exist_ok=True)

        if dlc_dir.exists():
            for dlc_file in dlc_dir.glob("*.nsp"):
                shutil.copy2(dlc_file, patches_dir / dlc_file.name)

        if updates_dir.exists():
            for update_file in updates_dir.glob("*.nsp"):
                shutil.copy2(update_file, patches_dir / update_file.name)

    cmd.append(str(game.rom_path))
    return cmd


def _build_generic_command(
    launch_template: str,
    binary: Path,
    rom_path: Path,
    fullscreen: bool,
) -> list[str]:
    launch_cmd = launch_template.replace("{binary}", str(binary))
    launch_cmd = launch_cmd.replace("{rom}", str(rom_path))

    if fullscreen and "{fullscreen}" in launch_cmd:
        launch_cmd = launch_cmd.replace("{fullscreen}", "--fullscreen")
    elif "{fullscreen}" in launch_cmd:
        launch_cmd = launch_cmd.replace("{fullscreen}", "")

    return launch_cmd.split()


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

    use_fullscreen = fullscreen if fullscreen is not None else config.fullscreen

    cmd = build_launch_command(
        game, library, emulator_binary, binary_name, use_fullscreen, debug
    )

    if not cmd:
        term.print("[red]failed to build launch command[/red]")
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

    if extra_args:
        cmd.extend(extra_args)

    if verbose:
        term.print(f"[dim]command: {' '.join(cmd)}[/dim]")

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        term.print(f"[red]launch failed: {e}[/red]")
        return False
    except FileNotFoundError:
        term.print(f"[red]emulator binary not found: {emulator_binary}[/red]")
        return False
