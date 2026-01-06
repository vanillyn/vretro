import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

from rich.console import Console

term = Console()


def is_compressed(path: Path) -> bool:
    if not path.exists():
        return False

    suffixes = [".7z", ".zip", ".gz", ".xz", ".zst"]
    return any(path.name.endswith(suffix) for suffix in suffixes)


def compress_rom(
    source: Path,
    compression: str = "7z",
    level: int = 9,
    verbose: bool = False,
) -> Optional[Path]:
    if not source.exists():
        if verbose:
            term.print(f"[red]source not found: {source}[/red]")
        return None

    if compression == "7z":
        dest = source.parent / f"{source.stem}.7z"

        if shutil.which("7z"):
            try:
                cmd = ["7z", "a", "-mx=" + str(level), str(dest), str(source)]

                if verbose:
                    term.print(f"[cyan]compressing with 7z...[/cyan]")
                    result = subprocess.run(cmd, check=True)
                else:
                    result = subprocess.run(
                        cmd, check=True, capture_output=True, text=True
                    )

                if result.returncode == 0:
                    source.unlink()
                    if verbose:
                        orig_size = source.stat().st_size if source.exists() else 0
                        comp_size = dest.stat().st_size
                        ratio = (
                            (1 - comp_size / orig_size) * 100 if orig_size > 0 else 0
                        )
                        term.print(
                            f"[green]compressed: {dest.name} ({ratio:.1f}% reduction)[/green]"
                        )
                    return dest
            except subprocess.CalledProcessError as e:
                if verbose:
                    term.print(f"[red]7z compression failed: {e}[/red]")
        else:
            if verbose:
                term.print("[yellow]7z not installed, falling back to zip[/yellow]")
            compression = "zip"

    if compression == "zip":
        dest = source.parent / f"{source.stem}.zip"

        try:
            if verbose:
                term.print("[cyan]compressing with zip...[/cyan]")

            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(source, source.name)

            orig_size = source.stat().st_size
            comp_size = dest.stat().st_size

            source.unlink()

            if verbose:
                ratio = (1 - comp_size / orig_size) * 100 if orig_size > 0 else 0
                term.print(
                    f"[green]compressed: {dest.name} ({ratio:.1f}% reduction)[/green]"
                )

            return dest
        except Exception as e:
            if verbose:
                term.print(f"[red]zip compression failed: {e}[/red]")

    return None


def decompress_rom(source: Path, dest_dir: Optional[Path] = None) -> Optional[Path]:
    if not source.exists():
        return None

    if dest_dir is None:
        dest_dir = source.parent

    if source.suffix == ".7z":
        if not shutil.which("7z"):
            term.print("[red]7z not installed[/red]")
            return None

        try:
            cmd = ["7z", "x", "-o" + str(dest_dir), str(source)]
            subprocess.run(cmd, check=True, capture_output=True)

            extracted = None
            for item in dest_dir.iterdir():
                if item.is_file() and item != source:
                    extracted = item
                    break

            return extracted
        except subprocess.CalledProcessError:
            return None

    elif source.suffix == ".zip":
        try:
            with zipfile.ZipFile(source, "r") as zf:
                names = zf.namelist()
                if len(names) == 0:
                    return None

                zf.extractall(dest_dir)
                return dest_dir / names[0]
        except Exception:
            return None

    return None


def compress_game_directory(
    game_dir: Path,
    compression: str = "7z",
    level: int = 9,
    verbose: bool = False,
) -> bool:
    resources_dir = game_dir / "resources"
    if not resources_dir.exists():
        return False

    base_files = list(resources_dir.glob("base.*"))
    if not base_files:
        return False

    for base_file in base_files:
        if is_compressed(base_file):
            if verbose:
                term.print(f"[dim]already compressed: {base_file.name}[/dim]")
            continue

        result = compress_rom(base_file, compression, level, verbose)
        if not result:
            return False

    return True


def decompress_game_directory(game_dir: Path, verbose: bool = False) -> bool:
    resources_dir = game_dir / "resources"
    if not resources_dir.exists():
        return False

    base_files = list(resources_dir.glob("base.*"))
    if not base_files:
        return False

    for base_file in base_files:
        if not is_compressed(base_file):
            if verbose:
                term.print(f"[dim]not compressed: {base_file.name}[/dim]")
            continue

        result = decompress_rom(base_file)
        if result:
            base_file.unlink()
            if verbose:
                term.print(f"[green]decompressed: {result.name}[/green]")
        else:
            return False

    return True
