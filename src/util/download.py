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
    else:
        keywords = ["linux", "tar", "ubuntu"]

    for asset in assets:
        name = asset["name"].lower()
        if any(kw in name for kw in keywords):
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
        if filename.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(dest_dir)
        elif filename.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(dest_dir)
        else:
            dest_file = dest_dir / filename
            dest_file.write_bytes(archive_path.read_bytes())
            if not IS_WINDOWS:
                dest_file.chmod(0o755)
        return True
    except Exception:
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
