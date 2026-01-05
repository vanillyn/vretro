from pathlib import Path
from typing import Optional

import requests


class SteamGridDB:
    def __init__(self) -> None:
        self.api_base = "https://www.steamgriddb.com/api/v2"
        self.api_key: Optional[str] = None

    def search_game(self, title: str) -> list:
        if not self.api_key:
            return []

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                f"{self.api_base}/search/autocomplete/{title}",
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
        except Exception:
            pass

        return []

    def get_assets(self, game_id: int, asset_type: str = "grids") -> list:
        if not self.api_key:
            return []

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                f"{self.api_base}/{asset_type}/game/{game_id}",
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
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
