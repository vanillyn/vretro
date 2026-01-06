import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

from .config import VRetroConfig, get_config_dir


@dataclass
class OnlineGame:
    id: int
    name: str
    platform: str
    year: Optional[int]
    publisher: Optional[str]
    region: str = "NA"
    cover_url: Optional[str] = None
    summary: Optional[str] = None
    genres: List[str] = None

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "year": self.year,
            "publisher": self.publisher,
            "region": self.region,
            "cover_url": self.cover_url,
            "summary": self.summary,
            "genres": self.genres or [],
        }


@dataclass
class GameDetails:
    id: int
    name: str
    summary: Optional[str]
    storyline: Optional[str]
    screenshots: List[str]
    videos: List[Dict]
    genres: List[str]
    release_date: Optional[int]
    rating: Optional[float]


@dataclass
class OnlineEmulator:
    name: str
    platforms: List[str]
    binary: str
    download_url: str
    latest_version: Optional[str]
    requires_bios: bool = False


class DatabaseCache:
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = get_config_dir() / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = 86400

    def get(self, key: str) -> Optional[dict]:
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            if time.time() - data.get("timestamp", 0) > self.ttl:
                cache_file.unlink()
                return None

            return data.get("value")
        except (json.JSONDecodeError, KeyError):
            return None

    def set(self, key: str, value: dict):
        cache_file = self.cache_dir / f"{key}.json"
        data = {"timestamp": time.time(), "value": value}

        with open(cache_file, "w") as f:
            json.dump(data, f)

    def clear(self):
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()


PLATFORM_MAPPING = {
    "NES": 18,
    "SNES": 19,
    "SFC": 19,
    "N64": 4,
    "GB": 33,
    "GBC": 22,
    "GBA": 24,
    "GC": 21,
    "WII": 5,
    "DS": 20,
    "3DS": 37,
    "SWITCH": 130,
    "PS1": 7,
    "PS2": 8,
    "PSP": 38,
    "GENESIS": 29,
    "SMS": 64,
    "GG": 35,
}


class OnlineDatabase:
    def __init__(self, config: Optional[VRetroConfig] = None):
        self.cache = DatabaseCache()
        self.github_api = "https://api.github.com"
        self.config = config or VRetroConfig.load()
        self.igdb_base = "https://api.igdb.com/v4"
        self._igdb_token = None
        self._token_expiry = 0
        self._emulator_database = self._load_emulator_database()

    def _load_emulator_database(self) -> Dict:
        db_path = get_config_dir() / "db" / "emulators.json"
        if not db_path.exists():
            return {}

        try:
            with open(db_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_igdb_token(self) -> Optional[str]:
        if self._igdb_token and time.time() < self._token_expiry:
            return self._igdb_token

        cache_key = "igdb_token"
        cached = self.cache.get(cache_key)
        if cached and time.time() < cached.get("expiry", 0):
            self._igdb_token = cached.get("token")
            self._token_expiry = cached.get("expiry", 0)
            return self._igdb_token

        if not self.config.igdb_client_id or not self.config.igdb_client_secret:
            return None

        try:
            url = "https://id.twitch.tv/oauth2/token"
            params = {
                "client_id": self.config.igdb_client_id,
                "client_secret": self.config.igdb_client_secret,
                "grant_type": "client_credentials",
            }

            response = requests.post(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)

                self._igdb_token = token
                self._token_expiry = time.time() + expires_in - 300

                self.cache.set(
                    cache_key,
                    {
                        "token": token,
                        "expiry": self._token_expiry,
                    },
                )

                return token
        except Exception:
            pass

        return None

    def _igdb_request(self, endpoint: str, query: str) -> Optional[List]:
        token = self._get_igdb_token()
        if not token:
            return None

        try:
            headers = {
                "Client-ID": self.config.igdb_client_id,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }

            response = requests.post(
                f"{self.igdb_base}/{endpoint}",
                headers=headers,
                data=query,
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
        except Exception:
            pass

        return None

    def search_games(
        self, query: str, platform: Optional[str] = None
    ) -> List[OnlineGame]:
        platform_filter = ""
        if platform:
            platform_id = PLATFORM_MAPPING.get(platform.upper())
            if platform_id:
                platform_filter = f" & platforms = [{platform_id}]"

        igdb_query = f'fields name, first_release_date, involved_companies.company.name, platforms.name, cover.url, summary, genres.name; search "{query}"; where category = 0{platform_filter}; limit 50;'

        data = self._igdb_request("games", igdb_query)
        if not data:
            return []

        results = []
        for game in data:
            if not isinstance(game, dict):
                continue

            year = None
            if game.get("first_release_date"):
                try:
                    year = time.gmtime(game["first_release_date"]).tm_year
                except:
                    pass

            publisher = None
            if game.get("involved_companies"):
                companies = game["involved_companies"]
                if companies and isinstance(companies, list) and len(companies) > 0:
                    if isinstance(companies[0], dict) and companies[0].get("company"):
                        company_data = companies[0]["company"]
                        if isinstance(company_data, dict):
                            publisher = company_data.get("name")

            platform_name = platform or "Unknown"
            if game.get("platforms"):
                platforms_list = game["platforms"]
                if (
                    platforms_list
                    and isinstance(platforms_list, list)
                    and len(platforms_list) > 0
                ):
                    if isinstance(platforms_list[0], dict):
                        platform_name = platforms_list[0].get("name", platform_name)

            cover_url = None
            if game.get("cover"):
                cover_data = game["cover"]
                if isinstance(cover_data, dict):
                    cover_url = cover_data.get("url", "")
                    if cover_url:
                        cover_url = cover_url.replace("t_thumb", "t_cover_big")
                        if not cover_url.startswith("http"):
                            cover_url = f"https:{cover_url}"

            genres = []
            if game.get("genres"):
                for genre in game["genres"]:
                    if isinstance(genre, dict) and genre.get("name"):
                        genres.append(genre["name"])

            summary = game.get("summary")

            results.append(
                OnlineGame(
                    id=game.get("id", 0),
                    name=game.get("name", "Unknown"),
                    platform=platform_name,
                    year=year,
                    publisher=publisher,
                    cover_url=cover_url,
                    summary=summary,
                    genres=genres,
                )
            )

        return results

    def get_game_details(self, game_id: int) -> Optional[GameDetails]:
        game_query = f"fields name, summary, storyline, screenshots.url, videos.video_id, genres.name, first_release_date, rating; where id = {game_id};"

        data = self._igdb_request("games", game_query)
        if not data or len(data) == 0:
            return None

        game = data[0]

        screenshots = []
        if game.get("screenshots"):
            for ss in game["screenshots"]:
                url = ss.get("url", "")
                if url:
                    url = url.replace("t_thumb", "t_screenshot_huge")
                    if not url.startswith("http"):
                        url = f"https:{url}"
                    screenshots.append(url)

        videos = []
        if game.get("videos"):
            for video in game["videos"]:
                video_id = video.get("video_id")
                if video_id:
                    videos.append(
                        {
                            "id": video_id,
                            "url": f"https://youtube.com/watch?v={video_id}",
                        }
                    )

        genres = []
        if game.get("genres"):
            for genre in game["genres"]:
                if isinstance(genre, dict) and genre.get("name"):
                    genres.append(genre["name"])

        return GameDetails(
            id=game.get("id", 0),
            name=game.get("name", ""),
            summary=game.get("summary"),
            storyline=game.get("storyline"),
            screenshots=screenshots,
            videos=videos,
            genres=genres,
            release_date=game.get("first_release_date"),
            rating=game.get("rating"),
        )

    def get_emulator_info(self, emulator_key: str) -> Optional[OnlineEmulator]:
        if emulator_key not in self._emulator_database:
            return None

        cache_key = f"emulator_{emulator_key}"
        cached = self.cache.get(cache_key)
        if cached:
            return OnlineEmulator(**cached)

        emu_data = self._emulator_database[emulator_key]

        if emu_data.get("repo"):
            try:
                latest = self._get_latest_release(emu_data["repo"])
            except Exception:
                latest = None
        else:
            latest = None

        emulator = OnlineEmulator(
            name=emu_data["name"],
            platforms=emu_data["platforms"],
            binary=emu_data["binary"],
            download_url=f"https://github.com/{emu_data['repo']}/releases"
            if emu_data.get("repo")
            else "",
            latest_version=latest,
            requires_bios=emu_data.get("requires_bios", False),
        )

        self.cache.set(
            cache_key,
            {
                "name": emulator.name,
                "platforms": emulator.platforms,
                "binary": emulator.binary,
                "download_url": emulator.download_url,
                "latest_version": emulator.latest_version,
                "requires_bios": emulator.requires_bios,
            },
        )

        return emulator

    def _get_latest_release(self, repo: str) -> Optional[str]:
        url = f"{self.github_api}/repos/{repo}/releases/latest"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("tag_name")
        except Exception:
            pass
        return None

    def list_emulators(self, platform: Optional[str] = None) -> List[str]:
        if platform:
            return [
                key
                for key, data in self._emulator_database.items()
                if platform.upper() in data["platforms"]
            ]
        return list(self._emulator_database.keys())

    def get_download_url(self, emulator_key: str) -> Optional[str]:
        if emulator_key not in self._emulator_database:
            return None

        emu_data = self._emulator_database[emulator_key]
        repo = emu_data.get("repo")

        if not repo:
            return None

        return f"https://github.com/{repo}/releases/latest"
