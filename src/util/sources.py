from pathlib import Path
from typing import List, Optional, Tuple

import requests

from .vrdb import GameSource, get_vrdb


class SourceManager:
    def __init__(self, debug: bool = False):
        self.vrdb = get_vrdb()
        self.debug = debug

        if self.debug:
            print("[sources] initialized")
            print(f"[sources] loaded {len(self.vrdb.consoles)} consoles")

    def search_games(self, console: str, query: str) -> List[Tuple[str, GameSource]]:
        if self.debug:
            print(f"[sources.search_games] console: {console}, query: {query}")

        results = self.vrdb.search_games(console, query)

        if self.debug:
            print(f"[sources.search_games] found {len(results)} results")

        return results

    def get_game(self, console: str, game_name: str) -> Optional[GameSource]:
        if self.debug:
            print(f"[sources.get_game] console: {console}, game: {game_name}")

        return self.vrdb.get_game(console, game_name)

    def download_file(
        self, source: GameSource, dest: Path, game_name: str = ""
    ) -> bool:
        if self.debug:
            print(f"[sources.download_file] scheme: {source.scheme}, dest: {dest}")

        try:
            file_url = source.get_download_url()

            if not file_url:
                if self.debug:
                    print("[sources.download_file] failed to get download url")
                return False

            if self.debug:
                print(f"[sources.download_file] url: {file_url}")

            if source.scheme == "switch" and game_name:
                file_url = f"{file_url}?filename={game_name}.zip"

            response = requests.get(file_url, stream=True, timeout=30)
            if response.status_code != 200:
                if self.debug:
                    print(f"[sources.download_file] http error: {response.status_code}")
                return False

            dest.parent.mkdir(parents=True, exist_ok=True)

            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            if self.debug:
                print("[sources.download_file] download complete")

            return True

        except Exception as e:
            if self.debug:
                print(f"[sources.download_file] error: {e}")
            return False

    def list_consoles(self) -> List[str]:
        return self.vrdb.list_consoles()
