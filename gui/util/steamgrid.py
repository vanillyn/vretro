import json
import time
from pathlib import Path
from typing import Optional

import requests

from src.data.config import get_config_dir


class SteamGridDB:
    def __init__(self) -> None:
        self.api_base = "https://www.steamgriddb.com/api/v2"
        self.api_key: Optional[str] = None
        self.cache_dir = get_config_dir() / "cache" / "steamgrid"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 86400 * 7

    def _get_cache(self, key: str) -> Optional[dict]:
        safe_key = key.replace("/", "_").replace(":", "_")
        cache_file = self.cache_dir / f"{safe_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            if time.time() - data.get("timestamp", 0) > self.cache_ttl:
                cache_file.unlink()
                return None

            return data.get("value")
        except:
            return None

    def _set_cache(self, key: str, value: dict) -> None:
        safe_key = key.replace("/", "_").replace(":", "_")
        cache_file = self.cache_dir / f"{safe_key}.json"

        data = {"timestamp": time.time(), "value": value}

        with open(cache_file, "w") as f:
            json.dump(data, f)

    def search_game(self, title: str) -> list:
        if not self.api_key:
            return []

        cache_key = f"search_{title}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                f"{self.api_base}/search/autocomplete/{title}",
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                result = data.get("data", [])
                self._set_cache(cache_key, result)
                return result
        except Exception:
            pass

        return []

    def get_assets(self, game_id: int, asset_type: str = "grids") -> list:
        if not self.api_key:
            return []

        cache_key = f"assets_{game_id}_{asset_type}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                f"{self.api_base}/{asset_type}/game/{game_id}",
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                result = data.get("data", [])
                self._set_cache(cache_key, result)
                return result
        except Exception:
            pass

        return []

    def download_asset(self, url: str, dest_path: Path) -> bool:
        try:
            response = requests.get(url, stream=True, timeout=30)
            if response.status_code == 200:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
        except Exception:
            pass

        return False
