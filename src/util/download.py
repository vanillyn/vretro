import platform
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console

term = Console()
IS_WINDOWS = platform.system() == "Windows"


def _get_linux_distro() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.split("=")[1].strip().strip('"')
    except Exception:
        pass
    return "unknown"


def download_emulator(
    console_code: str,
    emulator_name: str,
    download_url: str,
    install_dir: Path,
) -> bool:
    term.print(f"[cyan]downloading {emulator_name}...[/cyan]")

    try:
        download_url, filename = _resolve_github_release(download_url)

        if not download_url:
            term.print("[red]failed to resolve download url[/red]")
            return False

        if filename and filename.endswith(".appimage"):
            existing_appimage = _find_appimage(install_dir)
            if existing_appimage:
                zsync_url = download_url.replace(
                    ".AppImage", ".AppImage.zsync"
                ).replace(".appimage", ".appimage.zsync")
                if _try_zsync_update(existing_appimage, zsync_url):
                    term.print(f"[green]updated via zsync: {install_dir}[/green]")
                    return True
                else:
                    term.print("[dim]zsync failed, downloading full appimage...[/dim]")

        term.print(f"[dim]downloading {filename}...[/dim]")

        response = requests.get(download_url, stream=True, timeout=60)
        if response.status_code != 200:
            term.print(f"[red]download failed: http {response.status_code}[/red]")
            return False

        tmp_path = _save_temp_file(response)

        install_dir.mkdir(parents=True, exist_ok=True)

        if not _extract_archive(tmp_path, filename, install_dir):
            term.print("[red]failed to extract archive[/red]")
            return False

        tmp_path.unlink()

        term.print(f"[green]installed to: {install_dir}[/green]")
        return True

    except requests.RequestException as e:
        term.print(f"[red]download failed: {e}[/red]")
        return False
    except Exception as e:
        term.print(f"[red]installation failed: {e}[/red]")
        return False


def _resolve_github_release(url: str) -> tuple[Optional[str], Optional[str]]:
    if "github.com" not in url or "/releases" not in url:
        filename = url.split("/")[-1]
        return url, filename

    api_url = url.replace("github.com", "api.github.com/repos")
    if api_url.endswith("/releases"):
        api_url += "/latest"
    elif not api_url.endswith("/latest"):
        api_url = api_url.rstrip("/") + "/latest"

    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code != 200:
            return None, None

        release_data = response.json()
        assets = release_data.get("assets", [])

        if not assets:
            return None, None

        asset = _select_platform_asset(assets)
        if not asset:
            asset = assets[0]

        return asset["browser_download_url"], asset["name"]

    except Exception:
        return None, None


def _select_platform_asset(assets: list[dict]) -> Optional[dict]:
    if IS_WINDOWS:
        keywords = ["win", "windows", "win64", "x64"]
        exclude = ["linux", "macos", "osx", "darwin"]
    else:
        distro = _get_linux_distro()

        if distro in ["arch", "manjaro", "endeavouros"]:
            for asset in assets:
                name = asset["name"].lower()
                if name.endswith(".appimage"):
                    return asset

        keywords = ["linux", "x86_64", "amd64"]
        exclude = ["win", "windows", "macos", "osx", "darwin", "bsd", "openbsd"]

    for asset in assets:
        name = asset["name"].lower()

        has_exclude = any(ex in name for ex in exclude)
        if has_exclude:
            continue

        has_keyword = any(kw in name for kw in keywords)
        if has_keyword:
            return asset

    if not IS_WINDOWS:
        for asset in assets:
            name = asset["name"].lower()
            if name.endswith((".tar.gz", ".tgz", ".tar.xz")) and not any(
                ex in name for ex in exclude
            ):
                return asset

    return None


def _save_temp_file(response: requests.Response) -> Path:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                tmp_file.write(chunk)
        return Path(tmp_file.name)


def _extract_archive(archive_path: Path, filename: str, dest_dir: Path) -> bool:
    try:
        if filename.endswith(".appimage"):
            filename_lower = filename.lower()
            binary_name = filename_lower.replace(".appimage", "")

            binary_name = binary_name.split("-")[0]
            binary_name = binary_name.split("_")[0]

            for char in "0123456789.v":
                binary_name = binary_name.rstrip(char)

            dest_file = dest_dir / binary_name
            dest_file.write_bytes(archive_path.read_bytes())
            dest_file.chmod(0o755)
        elif filename.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(dest_dir)
                _flatten_if_single_dir(dest_dir)
        elif filename.endswith((".tar.xz", ".tar.bz2")):
            mode = "r:xz" if filename.endswith(".xz") else "r:bz2"
            with tarfile.open(archive_path, mode) as tar:
                tar.extractall(dest_dir)
                _flatten_if_single_dir(dest_dir)
        elif filename.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(dest_dir)
                _flatten_if_single_dir(dest_dir)
        else:
            dest_file = dest_dir / filename
            dest_file.write_bytes(archive_path.read_bytes())
            if not IS_WINDOWS:
                dest_file.chmod(0o755)
        return True
    except Exception:
        return False


def _flatten_if_single_dir(dest_dir: Path):
    contents = list(dest_dir.iterdir())

    if len(contents) == 1 and contents[0].is_dir():
        nested_dir = contents[0]

        temp_dir = dest_dir.parent / f"{dest_dir.name}_temp"
        nested_dir.rename(temp_dir)

        for item in temp_dir.iterdir():
            item.rename(dest_dir / item.name)

        temp_dir.rmdir()


def _find_appimage(install_dir: Path) -> Optional[Path]:
    if not install_dir.exists():
        return None

    for file in install_dir.iterdir():
        if file.is_file() and not file.name.endswith(".zsync"):
            return file

    return None


def _try_zsync_update(appimage_path: Path, zsync_url: str) -> bool:
    import shutil
    import subprocess

    if not shutil.which("zsync"):
        return False

    try:
        response = requests.head(zsync_url, timeout=10)
        if response.status_code != 200:
            return False

        result = subprocess.run(
            ["zsync", "-o", str(appimage_path), zsync_url],
            capture_output=True,
            timeout=300,
            cwd=str(appimage_path.parent),
        )

        if result.returncode == 0:
            appimage_path.chmod(0o755)
            return True

    except Exception:
        pass

    return False


def download_game_file(
    download_url: str,
    dest_file: Path,
    game_name: str = "",
) -> bool:
    try:
        if "?" not in download_url and game_name:
            download_url = f"{download_url}?filename={game_name}.zip"

        response = requests.get(download_url, stream=True, timeout=60)
        if response.status_code != 200:
            return False

        dest_file.parent.mkdir(parents=True, exist_ok=True)

        with open(dest_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return True

    except Exception:
        return False
