import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .console import ConsoleMetadata, get_console_metadata


@dataclass
class GameMetadata:
    code: str
    console: str
    id: int
    title: Dict[str, str]
    publisher: Dict[str, str]
    year: int
    region: str
    has_dlc: bool = False
    has_updates: bool = False
    emulator: Optional[str] = None
    thumbnail: Optional[str] = None
    playtime: int = 0
    last_played: Optional[float] = None
    is_favorite: bool = False
    version: str = "1.0"
    custom_args: List[str] = None

    def __post_init__(self):
        if self.custom_args is None:
            self.custom_args = []

    @classmethod
    def from_json(cls, data: dict):
        return cls(**data)

    def to_json(self) -> dict:
        return asdict(self)

    def get_title(self, region: Optional[str] = None) -> str:
        region = region or self.region
        return self.title.get(region, list(self.title.values())[0])

    def save(self, path: Path):
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=2)

    def update_playtime(self, seconds: int):
        self.playtime += seconds
        self.last_played = time.time()


@dataclass
class GameEntry:
    metadata: GameMetadata
    path: Path
    rom_path: Path
    saves_path: Path
    resources_path: Path

    def exists(self) -> bool:
        return self.rom_path.exists()

    def has_launch_script(self) -> bool:
        return (self.path / "launch.sh").exists()

    def get_thumbnail_path(self) -> Optional[Path]:
        if self.metadata.thumbnail:
            thumb_path = self.path / self.metadata.thumbnail
            if thumb_path.exists():
                return thumb_path

        default_thumb = self.path / "thumbnail.png"
        if default_thumb.exists():
            return default_thumb

        return None

    def get_saves(self) -> List[Path]:
        if not self.saves_path.exists():
            return []
        return list(self.saves_path.glob("*"))

    def backup_save(self, backup_dir: Path) -> bool:
        if not self.saves_path.exists():
            return False

        backup_name = f"{self.metadata.code}_{int(time.time())}"
        backup_path = backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)

        import shutil

        shutil.copytree(self.saves_path, backup_path, dirs_exist_ok=True)
        return True


CONSOLE_EXTENSIONS = {
    "SFC": "sfc",
    "SNES": "sfc",
    "NES": "nes",
    "GB": "gb",
    "GBC": "gbc",
    "GBA": "gba",
    "N64": "z64",
    "GC": "iso",
    "WII": "iso",
    "DS": "nds",
    "3DS": "3ds",
    "SWITCH": "nsp",
    "PS1": "bin",
    "PS2": "iso",
    "PSP": "iso",
    "GENESIS": "bin",
    "SMS": "sms",
    "GG": "gg",
    "ARCADE": "zip",
    "DOS": "zip",
    "WIIU": "wux",
    "NATIVE": "sh",
    "WINE": "exe",
}


class GameLibrary:
    def __init__(
        self, games_root: Path, ignored_dirs: List[str] = None, debug: bool = False
    ):
        self.games_root = games_root
        self.console_root = games_root / "console"
        self.games: List[GameEntry] = []
        self.consoles: Dict[str, ConsoleMetadata] = {}
        self.ignored_dirs = set(ignored_dirs or [])
        self.debug = debug

        if self.debug:
            print(f"[library] initialized with root: {self.games_root}")
            print(f"[library] console root: {self.console_root}")

    def scan_consoles(
        self, verbose: bool = False, generate_metadata: bool = True
    ) -> Dict[str, ConsoleMetadata]:
        self.consoles = {}

        if self.debug:
            print("[library.scan_consoles] starting scan")

        if not self.console_root.exists():
            if verbose or self.debug:
                print(f"console root not found: {self.console_root}")
            return self.consoles

        for console_dir in sorted(self.console_root.iterdir()):
            if not console_dir.is_dir():
                continue

            if console_dir.name in self.ignored_dirs:
                if verbose or self.debug:
                    print(f"skipping ignored directory: {console_dir.name}")
                continue

            if self.debug:
                print(f"[library.scan_consoles] checking: {console_dir}")

            metadata = ConsoleMetadata.load(console_dir)

            if not metadata and generate_metadata:
                if verbose or self.debug:
                    print(f"generating metadata for {console_dir.name}...")

                metadata = get_console_metadata(console_dir.name)

                if metadata:
                    metadata.save(console_dir)
                    if verbose or self.debug:
                        print(f"  saved: {console_dir / 'console.json'}")
                else:
                    if verbose or self.debug:
                        print(f"  unknown console: {console_dir.name}")
                    continue

            if metadata:
                self.consoles[metadata.code] = metadata
                if verbose or self.debug:
                    print(f"loaded: {metadata.name} ({metadata.code})")
            else:
                if verbose or self.debug:
                    print(f"no metadata found for: {console_dir.name}")

        return self.consoles

    def list_console_dirs(self) -> List[tuple[str, bool]]:
        if not self.console_root.exists():
            return []

        dirs = []
        for console_dir in sorted(self.console_root.iterdir()):
            if not console_dir.is_dir():
                continue

            if console_dir.name in self.ignored_dirs:
                continue

            has_metadata = (console_dir / "console.json").exists()
            dirs.append((console_dir.name, has_metadata))

        return dirs

    def scan(
        self,
        verbose: bool = False,
        scan_consoles: bool = True,
        auto_metadata: bool = True,
    ) -> List[GameEntry]:
        self.games = []

        if self.debug:
            print("[library.scan] starting game scan")

        if scan_consoles:
            self.scan_consoles(verbose=verbose)

        if not self.console_root.exists():
            if verbose or self.debug:
                print(f"console root not found: {self.console_root}")
            return self.games

        for console_dir in self.console_root.iterdir():
            if not console_dir.is_dir():
                continue

            if console_dir.name in self.ignored_dirs:
                continue

            if self.debug:
                print(f"[library.scan] scanning console: {console_dir.name}")

            console_meta = None
            for code, meta in self.consoles.items():
                if meta.name == console_dir.name:
                    console_meta = meta
                    break

            games_dir = console_dir / "games"

            if not games_dir.exists():
                if verbose or self.debug:
                    print(f"no games directory: {games_dir}")
                continue

            if self.debug:
                print(f"[library.scan] games directory exists: {games_dir}")

            for game_dir in games_dir.iterdir():
                if not game_dir.is_dir():
                    continue

                if self.debug:
                    print(f"[library.scan] checking game dir: {game_dir.name}")

                metadata_file = game_dir / "metadata.json"

                if not metadata_file.exists() and auto_metadata and console_meta:
                    if verbose or self.debug:
                        print(
                            f"[library.scan] no metadata, attempting auto-generate: {game_dir.name}"
                        )

                    try:
                        from .config import VRetroConfig
                        from .database import OnlineDatabase

                        db = OnlineDatabase(VRetroConfig.load())
                        game_name = game_dir.name.replace("-", " ").title()

                        igdb_games = db.search_games(game_name, console_meta.code)

                        if igdb_games:
                            igdb_game = igdb_games[0]

                            metadata = GameMetadata(
                                code=f"{console_meta.code.lower()}-{game_dir.name}",
                                console=console_meta.code,
                                id=igdb_game.id,
                                title={"NA": igdb_game.name},
                                publisher={"NA": igdb_game.publisher or "Unknown"},
                                year=igdb_game.year or 0,
                                region="NA",
                            )
                            metadata.save(metadata_file)

                            resources_dir = game_dir / "resources"
                            rom_files = (
                                list(resources_dir.glob("base.*"))
                                if resources_dir.exists()
                                else []
                            )

                            if rom_files and console_meta:
                                launch_cmd = console_meta.emulator.launch_command
                                launch_cmd = launch_cmd.replace(
                                    "{binary}", console_meta.emulator.binary
                                )
                                launch_cmd = launch_cmd.replace(
                                    "{rom}", str(rom_files[0])
                                )

                                launch_script = game_dir / "launch.sh"
                                with open(launch_script, "w") as f:
                                    f.write("#!/bin/bash\n")
                                    f.write(f"{launch_cmd}\n")
                                launch_script.chmod(0o755)

                            if verbose or self.debug:
                                print(
                                    f"[library.scan] auto-generated metadata: {igdb_game.name}"
                                )
                        else:
                            if verbose or self.debug:
                                print(
                                    f"[library.scan] no igdb results for: {game_name}"
                                )
                            continue

                    except Exception as e:
                        if verbose or self.debug:
                            print(f"[library.scan] auto-metadata failed: {e}")
                        continue

                if not metadata_file.exists():
                    if verbose or self.debug:
                        print(f"no metadata: {game_dir}")
                    continue

                try:
                    with open(metadata_file, "r") as f:
                        metadata = GameMetadata.from_json(json.load(f))

                    if self.debug:
                        print(f"[library.scan] loaded metadata: {metadata.get_title()}")

                    resources_dir = game_dir / "resources"
                    rom_path = self._find_rom(resources_dir, metadata.console)

                    if rom_path:
                        if self.debug:
                            print(f"[library.scan] found rom: {rom_path}")

                        entry = GameEntry(
                            metadata=metadata,
                            path=game_dir,
                            rom_path=rom_path,
                            saves_path=game_dir / "saves",
                            resources_path=resources_dir,
                        )
                        self.games.append(entry)
                        if verbose or self.debug:
                            print(f"loaded: {metadata.get_title()}")
                    elif verbose or self.debug:
                        print(f"no rom found: {game_dir}")

                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    if verbose or self.debug:
                        print(f"error loading {metadata_file}: {e}")
                    continue

        if self.debug:
            print(f"[library.scan] found {len(self.games)} games total")

        return self.games

    def _find_rom(self, resources_dir: Path, console: str) -> Optional[Path]:
        if not resources_dir.exists():
            return None

        base_dir = resources_dir / "base"
        if base_dir.is_dir():
            return base_dir

        for file in resources_dir.glob("base.*"):
            return file

        return None

    def search(self, query: str) -> List[GameEntry]:
        query = query.lower()
        results = []

        for game in self.games:
            title_match = query in game.metadata.get_title().lower()
            console_match = query in game.metadata.console.lower()
            code_match = query in game.metadata.code.lower()

            if title_match or console_match or code_match:
                score = 0
                if title_match:
                    score += 10
                if game.metadata.get_title().lower().startswith(query):
                    score += 5
                if console_match:
                    score += 2
                if code_match:
                    score += 1

                results.append((score, game))

        results.sort(key=lambda x: x[0], reverse=True)
        return [game for score, game in results]

    def filter_by_console(self, console: str) -> List[GameEntry]:
        console = console.upper()
        return [game for game in self.games if game.metadata.console == console]

    def get_by_code(self, code: str) -> Optional[GameEntry]:
        for game in self.games:
            if game.metadata.code == code:
                return game
        return None

    def get_favorites(self) -> List[GameEntry]:
        return [game for game in self.games if game.metadata.is_favorite]

    def get_recently_played(self, limit: int = 10) -> List[GameEntry]:
        played = [g for g in self.games if g.metadata.last_played]
        played.sort(key=lambda g: g.metadata.last_played, reverse=True)
        return played[:limit]

    def get_consoles(self) -> List[str]:
        return sorted(set(game.metadata.console for game in self.games))

    def get_console_metadata(self, code: str) -> Optional[ConsoleMetadata]:
        return self.consoles.get(code.upper())

    def create_game_entry(
        self, console: str, game_code: str, metadata: GameMetadata
    ) -> GameEntry:
        console_meta = self.get_console_metadata(console)
        if not console_meta:
            raise ValueError(f"unknown console: {console}")

        console_dir = self.console_root / console_meta.name
        games_dir = console_dir / "games"
        game_dir = games_dir / game_code

        if self.debug:
            print(f"[library.create_game_entry] creating game: {game_code}")
            print(f"[library.create_game_entry] console dir: {console_dir}")
            print(f"[library.create_game_entry] game dir: {game_dir}")

        game_dir.mkdir(parents=True, exist_ok=True)
        (game_dir / "resources").mkdir(exist_ok=True)
        (game_dir / "saves").mkdir(exist_ok=True)

        metadata.save(game_dir / "metadata.json")

        resources_dir = game_dir / "resources"
        rom_path = resources_dir / f"base.{CONSOLE_EXTENSIONS.get(console, 'bin')}"

        entry = GameEntry(
            metadata=metadata,
            path=game_dir,
            rom_path=rom_path,
            saves_path=game_dir / "saves",
            resources_path=resources_dir,
        )

        self.games.append(entry)
        return entry

    def create_console(
        self, code: str, metadata: Optional[ConsoleMetadata] = None
    ) -> Path:
        code = code.upper()

        if metadata is None:
            metadata = get_console_metadata(code)

        if not metadata:
            raise ValueError(f"unknown console: {code}")

        console_dir = self.console_root / metadata.name

        if self.debug:
            print(f"[library.create_console] creating console: {code}")
            print(f"[library.create_console] console name: {metadata.name}")
            print(f"[library.create_console] console dir: {console_dir}")

        console_dir.mkdir(parents=True, exist_ok=True)
        (console_dir / "games").mkdir(exist_ok=True)
        (console_dir / "emulator").mkdir(exist_ok=True)
        (console_dir / "resources").mkdir(exist_ok=True)

        metadata.save(console_dir)
        self.consoles[code] = metadata

        return console_dir
