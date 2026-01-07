import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.data.console import ConsoleMetadata, get_console_metadata


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
    custom_args: str = ""
    emulator: Optional[str] = None
    thumbnail: Optional[str] = None
    favorite: bool = False
    playtime: int = 0

    @classmethod
    def from_json(cls, data: dict) -> "GameMetadata":
        return cls(
            code=str(data.get("code", "")),
            console=str(data.get("console", "")),
            id=int(data.get("id", 0)),
            title=dict(data.get("title", {})),
            publisher=dict(data.get("publisher", {})),
            year=int(data.get("year", 0)),
            region=str(data.get("region", "NA")),
            has_dlc=bool(data.get("has_dlc", False)),
            has_updates=bool(data.get("has_updates", False)),
            custom_args=str(data.get("custom_args", "")),
            emulator=data.get("emulator"),
            thumbnail=data.get("thumbnail"),
            favorite=bool(data.get("favorite", False)),
            playtime=int(data.get("playtime", 0)),
        )

    def to_json(self) -> dict:
        return asdict(self)

    def get_title(self, region: Optional[str] = None) -> str:
        region = region or self.region
        return self.title.get(
            region, list(self.title.values())[0] if self.title else ""
        )

    def update_playtime(self, elapsed_seconds: int) -> None:
        self.playtime += elapsed_seconds

    def save(self, path: Path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=2)


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


CONSOLE_EXTENSIONS: Dict[str, str] = {
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
}


class GameLibrary:
    def __init__(
        self,
        games_root: Path,
        ignored_dirs: Optional[List[str]] = None,
        debug: bool = False,
    ):
        self.games_root = Path(games_root)
        self.console_root = self.games_root / "console"
        self.games: List[GameEntry] = []
        self.consoles: Dict[str, ConsoleMetadata] = {}
        self.ignored_dirs: Set[str] = set(ignored_dirs or [])
        self.debug = debug

        if self.debug:
            print(f"[library] initialized with root: {self.games_root}")

    def scan_consoles(
        self,
        verbose: bool = False,
        generate_metadata: bool = True,
    ) -> Dict[str, ConsoleMetadata]:
        self.consoles = {}

        if not self.console_root.exists():
            if verbose or self.debug:
                print(f"console root not found: {self.console_root}")
            return self.consoles

        for console_dir in sorted(self.console_root.iterdir()):
            if not console_dir.is_dir():
                continue

            if console_dir.name in self.ignored_dirs:
                continue

            metadata = ConsoleMetadata.load(console_dir)

            if not metadata and generate_metadata:
                metadata = get_console_metadata(console_dir.name)
                if metadata:
                    metadata.save(console_dir)

            if metadata:
                self.consoles[metadata.code] = metadata

        return self.consoles

    def scan(
        self,
        verbose: bool = False,
        scan_consoles: bool = True,
        auto_metadata: bool = False,
    ) -> List[GameEntry]:
        self.games = []

        if scan_consoles:
            self.scan_consoles(verbose=verbose)

        if not self.console_root.exists():
            return self.games

        for console_dir in self.console_root.iterdir():
            if not console_dir.is_dir():
                continue

            if console_dir.name in self.ignored_dirs:
                continue

            console_meta = None
            for code, meta in self.consoles.items():
                if meta.name == console_dir.name:
                    console_meta = meta
                    break

            games_dir = console_dir / "games"
            if not games_dir.exists():
                continue

            for game_dir in games_dir.iterdir():
                if not game_dir.is_dir():
                    continue

                metadata_file = game_dir / "metadata.json"
                if not metadata_file.exists():
                    continue

                try:
                    with open(metadata_file, "r") as f:
                        metadata = GameMetadata.from_json(json.load(f))

                    resources_dir = game_dir / "resources"
                    rom_path = self._find_rom(resources_dir, metadata.console)

                    if rom_path:
                        entry = GameEntry(
                            metadata=metadata,
                            path=game_dir,
                            rom_path=rom_path,
                            saves_path=game_dir / "saves",
                            resources_path=resources_dir,
                        )
                        self.games.append(entry)

                except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                    if verbose or self.debug:
                        print(f"error loading {metadata_file}: {e}")

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
        query_lower = query.lower()
        return [
            game
            for game in self.games
            if query_lower in game.metadata.get_title().lower()
            or query_lower in game.metadata.console.lower()
            or query_lower in game.metadata.code.lower()
        ]

    def filter_by_console(self, console: str) -> List[GameEntry]:
        console_upper = console.upper()
        return [game for game in self.games if game.metadata.console == console_upper]

    def get_by_code(self, code: str) -> Optional[GameEntry]:
        for game in self.games:
            if game.metadata.code == code:
                return game
        return None

    def get_consoles(self) -> List[str]:
        return sorted(list(self.consoles.keys()))

    def get_console_metadata(self, code: str) -> Optional[ConsoleMetadata]:
        return self.consoles.get(code.upper())

    def create_game_entry(
        self,
        console: str,
        game_code: str,
        metadata: GameMetadata,
    ) -> GameEntry:
        console_meta = self.get_console_metadata(console)
        if not console_meta:
            raise ValueError(f"unknown console: {console}")

        console_dir = self.console_root / console_meta.name
        games_dir = console_dir / "games"
        game_dir = games_dir / game_code

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
        self,
        code: str,
        metadata: Optional[ConsoleMetadata] = None,
    ) -> Path:
        code_upper = code.upper()

        if metadata is None:
            metadata = get_console_metadata(code_upper)

        if not metadata:
            raise ValueError(f"unknown console: {code}")

        console_dir = self.console_root / metadata.name
        console_dir.mkdir(parents=True, exist_ok=True)
        (console_dir / "games").mkdir(exist_ok=True)
        (console_dir / "emulator").mkdir(exist_ok=True)
        (console_dir / "resources").mkdir(exist_ok=True)

        metadata.save(console_dir)
        self.consoles[code_upper] = metadata

        return console_dir
