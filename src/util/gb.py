import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class GameBananaMod:
    id: int
    name: str
    description: str
    author: str
    downloads: int
    likes: int
    views: int
    download_url: str
    thumbnail_url: Optional[str] = None
    version: str = "1.0"


class GameBananaAPI:
    def __init__(self):
        self.api_base = "https://gamebanana.com/apiv11"

    def get_game_id(self, game_name: str) -> Optional[int]:
        logger.info(f"searching gamebanana for game: {game_name}")

        try:
            url = f"{self.api_base}/Util/Game/NameMatch"
            params = {"_sName": game_name}

            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                logger.error(f"gamebanana api returned {response.status_code}")
                return None

            data = response.json()

            if not data or not isinstance(data, list) or len(data) == 0:
                logger.warning(f"no game found for '{game_name}'")
                return None

            game_id = data[0].get("_idRow")
            game_title = data[0].get("_sName", "")
            logger.info(f"found game: {game_title} (id: {game_id})")

            return game_id

        except Exception as e:
            logger.error(f"failed to search for game: {e}")
            return None

    def search_mods(
        self, game_id: int, query: str = "", page: int = 1
    ) -> List[GameBananaMod]:
        logger.info(f"searching mods for game {game_id}, query: '{query}'")

        try:
            url = f"{self.api_base}/Mod/Index"
            params = {
                "_aFilters[Generic_Game]": game_id,
                "_sSort": "downloads",
                "_nPage": page,
                "_nPerpage": 20,
            }

            if query:
                params["_sName"] = query

            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                logger.error(f"gamebanana api returned {response.status_code}")
                return []

            data = response.json()

            if not data or "_aRecords" not in data:
                logger.warning(f"no mods found for game {game_id}")
                return []

            mods = []
            for item in data["_aRecords"]:
                download_url = ""
                if item.get("_aFiles") and len(item["_aFiles"]) > 0:
                    download_url = item["_aFiles"][0].get("_sDownloadUrl", "")

                thumbnail_url = None
                if item.get("_aPreviewMedia", {}).get("_aImages"):
                    images = item["_aPreviewMedia"]["_aImages"]
                    if images and len(images) > 0:
                        thumbnail_url = images[0].get("_sFile100", "") or images[0].get(
                            "_sFile", ""
                        )

                mod = GameBananaMod(
                    id=item.get("_idRow", 0),
                    name=item.get("_sName", ""),
                    description=item.get("_sText", "")[:500],
                    author=item.get("_aSubmitter", {}).get("_sName", "unknown"),
                    downloads=item.get("_nDownloadCount", 0),
                    likes=item.get("_nLikeCount", 0),
                    views=item.get("_nViewCount", 0),
                    download_url=download_url,
                    thumbnail_url=thumbnail_url,
                )

                mods.append(mod)

            logger.info(f"found {len(mods)} mods for game {game_id}")
            return mods

        except Exception as e:
            logger.error(f"failed to search mods: {e}")
            return []

    def get_mod_details(self, mod_id: int) -> Optional[GameBananaMod]:
        logger.info(f"fetching mod details for {mod_id}")

        try:
            url = f"{self.api_base}/Mod/{mod_id}/ProfilePage"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                logger.error(f"gamebanana api returned {response.status_code}")
                return None

            item = response.json()

            download_url = ""
            if item.get("_aFiles") and len(item["_aFiles"]) > 0:
                download_url = item["_aFiles"][0].get("_sDownloadUrl", "")

            thumbnail_url = None
            if item.get("_aPreviewMedia", {}).get("_aImages"):
                images = item["_aPreviewMedia"]["_aImages"]
                if images and len(images) > 0:
                    thumbnail_url = images[0].get("_sFile100", "") or images[0].get(
                        "_sFile", ""
                    )

            return GameBananaMod(
                id=item.get("_idRow", 0),
                name=item.get("_sName", ""),
                description=item.get("_sText", ""),
                author=item.get("_aSubmitter", {}).get("_sName", "unknown"),
                downloads=item.get("_nDownloadCount", 0),
                likes=item.get("_nLikeCount", 0),
                views=item.get("_nViewCount", 0),
                download_url=download_url,
                thumbnail_url=thumbnail_url,
            )

        except Exception as e:
            logger.error(f"failed to fetch mod details: {e}")
            return None

    def download_mod(self, download_url: str, dest_path: Path) -> bool:
        logger.info(f"downloading mod to {dest_path}")

        try:
            response = requests.get(download_url, stream=True, timeout=60)

            if response.status_code != 200:
                logger.error(f"download failed with status {response.status_code}")
                return False

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            logger.info(f"successfully downloaded {downloaded} bytes")
            return True

        except Exception as e:
            logger.error(f"failed to download mod: {e}")
            return False
