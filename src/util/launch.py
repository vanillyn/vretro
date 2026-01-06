import os
import platform
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

    emulator_dir = game.path.parent.parent / "emulator"

    if "mupen64plus" in binary_name.lower():
        return _build_mupen64plus_command(
            emulator_binary, emulator_dir, game, rom_path, use_fullscreen, debug
        )

    elif "yuzu" in binary_name.lower() or "eden" in binary_name.lower():
        return _build_yuzu_command(
            emulator_binary, emulator_dir, game, rom_path, use_fullscreen
        )

    else:
        return _build_generic_command(
            console_meta.emulator.launch_command,
            emulator_binary,
            rom_path,
            use_fullscreen,
        )


def _build_mupen64plus_command(
    binary: Path,
    emulator_dir: Path,
    game: GameEntry,
    rom_path: Path,
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

    cmd.append(str(rom_path))
    return cmd


def _build_yuzu_command(
    binary: Path,
    emulator_dir: Path,
    game: GameEntry,
    rom_path: Path,
    fullscreen: bool = True,
) -> list[str]:
    portable_dir = emulator_dir.parent / "portable"
    portable_dir.mkdir(exist_ok=True)

    keys_dir = portable_dir / "keys"
    keys_dir.mkdir(exist_ok=True)

    resources_dir = emulator_dir.parent / "resources"

    if resources_dir.exists():
        prod_keys = resources_dir / "prod.keys"
        if prod_keys.exists():
            import shutil

            shutil.copy2(prod_keys, keys_dir / "prod.keys")

        firmware_zip = resources_dir / "firmware.zip"
        if firmware_zip.exists():
            firmware_dir = portable_dir / "nand" / "system" / "Contents" / "registered"
            firmware_dir.mkdir(parents=True, exist_ok=True)

            import zipfile

            with zipfile.ZipFile(firmware_zip, "r") as zip_ref:
                zip_ref.extractall(firmware_dir)

    cmd = [str(binary), "-u", str(portable_dir)]

    if fullscreen:
        cmd.append("-f")

    cmd.extend(["-g", str(rom_path)])

    dlc_dir = game.resources_path / "dlc"
    updates_dir = game.resources_path / "updates"

    if dlc_dir.exists():
        for dlc_file in dlc_dir.glob("*.nsp"):
            cmd.extend(["--installnsp", str(dlc_file)])

    if updates_dir.exists():
        for update_file in updates_dir.glob("*.nsp"):
            cmd.extend(["--installnsp", str(update_file)])

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

    setup_library_path(emulator_dir, binary_name)

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
        cmd.extend(game.metadata.custom_args)

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
    except FileNotFoundError:
        term.print(f"[red]emulator binary not found: {emulator_binary}[/red]")
        cleanup_temp(game)
        return False
