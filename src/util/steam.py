import json
import logging
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

from src.data.config import get_config_dir

logger = logging.getLogger(__name__)


@dataclass
class SteamGame:
    app_id: int
    name: str
    type: str
    short_description: str = ""
    header_image: str = ""
    publishers: List[str] = None
    developers: List[str] = None
    release_date: str = ""


class SteamDatabase:
    def __init__(self):
        self.cache_dir = get_config_dir() / "cache" / "steam"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "applist.json"
        self.cache_ttl = 86400 * 7
        self.apps: Dict[int, str] = {}

    def update_cache(self) -> bool:
        logger.info("updating steam app list cache")
        try:
            response = requests.get(
                "https://api.steampowered.com/ISteamApps/GetAppList/v2/", timeout=30
            )

            if response.status_code != 200:
                logger.error(f"failed to fetch steam app list: {response.status_code}")
                return False

            data = response.json()
            apps = data.get("applist", {}).get("apps", [])

            self.apps = {app["appid"]: app["name"] for app in apps if app.get("name")}

            with open(self.cache_file, "w") as f:
                json.dump(
                    {"timestamp": int(__import__("time").time()), "apps": self.apps}, f
                )

            logger.info(f"cached {len(self.apps)} steam apps")
            return True

        except Exception as e:
            logger.error(f"failed to update steam cache: {e}")
            return False

    def load_cache(self) -> bool:
        if not self.cache_file.exists():
            logger.info("steam cache does not exist, updating")
            return self.update_cache()

        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)

            timestamp = data.get("timestamp", 0)
            if __import__("time").time() - timestamp > self.cache_ttl:
                logger.info("steam cache expired, updating")
                return self.update_cache()

            self.apps = {int(k): v for k, v in data.get("apps", {}).items()}
            logger.info(f"loaded {len(self.apps)} steam apps from cache")
            return True

        except Exception as e:
            logger.error(f"failed to load steam cache: {e}")
            return self.update_cache()

    def search_games(self, query: str) -> List[tuple[int, str]]:
        if not self.apps:
            self.load_cache()

        query_lower = query.lower()
        results = []

        for app_id, name in self.apps.items():
            if query_lower in name.lower():
                results.append((app_id, name))

        logger.info(f"found {len(results)} results for '{query}'")
        return sorted(results, key=lambda x: x[1])[:50]

    def get_game_name(self, app_id: int) -> Optional[str]:
        if not self.apps:
            self.load_cache()
        return self.apps.get(app_id)


class SteamManager:
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.is_windows = platform.system() == "Windows"
        self.steam_path = self._find_steam()
        self.steamcmd_path = self._find_steamcmd()
        self.database = SteamDatabase()

    def _find_steam(self) -> Optional[Path]:
        if self.is_windows:
            paths = [
                Path("C:/Program Files (x86)/Steam"),
                Path("C:/Program Files/Steam"),
            ]
        else:
            paths = [
                Path.home() / ".steam" / "steam",
                Path.home() / ".local" / "share" / "Steam",
            ]

        for path in paths:
            if path.exists():
                logger.info(f"found steam at {path}")
                return path

        logger.warning("steam installation not found")
        return None

    def _find_steamcmd(self) -> Optional[Path]:
        steamcmd = shutil.which("steamcmd")
        if steamcmd:
            logger.info(f"found steamcmd at {steamcmd}")
            return Path(steamcmd)

        if not self.is_windows:
            local_steamcmd = Path.home() / ".local" / "bin" / "steamcmd"
            if local_steamcmd.exists():
                logger.info(f"found steamcmd at {local_steamcmd}")
                return local_steamcmd

        logger.warning("steamcmd not found")
        return None

    def is_game_installed(self, app_id: int) -> bool:
        if not self.steam_path:
            return False

        manifest_path = self.steam_path / "steamapps" / f"appmanifest_{app_id}.acf"
        return manifest_path.exists()

    def install_game(self, app_id: int) -> bool:
        if not self.steamcmd_path:
            logger.error("steamcmd not found, cannot install game")
            return False

        logger.info(f"installing steam game {app_id} via steamcmd")

        try:
            cmd = [
                str(self.steamcmd_path),
                "+login",
                "anonymous",
                "+app_update",
                str(app_id),
                "validate",
                "+quit",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                logger.info(f"successfully installed steam game {app_id}")
                return True
            else:
                logger.error(
                    f"steamcmd failed with code {result.returncode}: {result.stderr}"
                )
                return False

        except subprocess.TimeoutExpired:
            logger.error("steamcmd timed out")
            return False
        except Exception as e:
            logger.error(f"failed to install steam game: {e}")
            return False

    def launch_game(self, app_id: int, proton_version: Optional[str] = None) -> bool:
        logger.info(f"launching steam game {app_id}")

        if self.is_windows:
            return self._launch_windows(app_id)
        else:
            return self._launch_linux(app_id, proton_version)

    def _launch_windows(self, app_id: int) -> bool:
        try:
            subprocess.Popen(["steam", f"steam://rungameid/{app_id}"])
            logger.info(f"launched steam game {app_id}")
            return True
        except Exception as e:
            logger.error(f"failed to launch steam game: {e}")
            return False

    def _launch_linux(self, app_id: int, proton_version: Optional[str] = None) -> bool:
        try:
            cmd = ["steam", f"steam://rungameid/{app_id}"]

            env = {}
            if proton_version:
                compat_data = (
                    Path.home()
                    / ".steam"
                    / "steam"
                    / "steamapps"
                    / "compatdata"
                    / str(app_id)
                )
                env["STEAM_COMPAT_DATA_PATH"] = str(compat_data)
                logger.info(f"using proton version: {proton_version}")

            subprocess.Popen(cmd, env={**__import__("os").environ, **env})
            logger.info(f"launched steam game {app_id}")
            return True

        except Exception as e:
            logger.error(f"failed to launch steam game: {e}")
            return False

    def get_proton_versions(self) -> List[str]:
        if not self.steam_path:
            logger.warning("cannot get proton versions without steam installation")
            return []

        compattools_path = self.steam_path / "steamapps" / "common"
        if not compattools_path.exists():
            return []

        versions = []
        for item in compattools_path.iterdir():
            if item.is_dir() and "proton" in item.name.lower():
                versions.append(item.name)

        logger.info(f"found {len(versions)} proton versions")
        return sorted(versions, reverse=True)

    def get_game_info(self, app_id: int) -> Optional[SteamGame]:
        logger.info(f"fetching steam game info for {app_id}")

        try:
            url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                logger.error(f"steam api returned {response.status_code}")
                return None

            data = response.json()

            if str(app_id) not in data or not data[str(app_id)].get("success"):
                logger.warning(f"no data found for steam app {app_id}")
                return None

            game_data = data[str(app_id)]["data"]

            return SteamGame(
                app_id=app_id,
                name=game_data.get("name", ""),
                type=game_data.get("type", ""),
                short_description=game_data.get("short_description", ""),
                header_image=game_data.get("header_image", ""),
                publishers=game_data.get("publishers", []),
                developers=game_data.get("developers", []),
                release_date=game_data.get("release_date", {}).get("date", ""),
            )

        except Exception as e:
            logger.error(f"failed to fetch steam game info: {e}")
            return None
