from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import tomli as tomllib
except ImportError:
    import tomllib

from ..data.config import get_config_dir


@dataclass
class GameSource:
    scheme: str
    identifier: str
    original_uri: str

    @classmethod
    def from_uri(cls, uri: str) -> Optional["GameSource"]:
        if "://" not in uri:
            return None

        scheme, identifier = uri.split("://", 1)
        return cls(scheme=scheme.lower(), identifier=identifier, original_uri=uri)

    def get_download_url(self) -> str:
        if self.scheme == "arv":
            return f"https://arweave.net/{self.identifier}"
        elif self.scheme == "switch":
            return f"https://dl.romheaven.com/{self.identifier}.zip"
        elif self.scheme in ["http", "https"]:
            return self.original_uri
        return ""


@dataclass
class EmulatorInfo:
    name: str
    binary: str
    url: str
    requires_bios: bool = False
    bios_files: List[str] = field(default_factory=list)
    launch_command: str = "{binary} {rom}"


@dataclass
class ConsoleInfo:
    code: str
    name: str
    release: str
    manufacturer: str
    formats: List[str]
    generation: Optional[int] = None


@dataclass
class VRDBConsole:
    emulator: EmulatorInfo
    console: ConsoleInfo
    games: Dict[str, GameSource]

    @classmethod
    def from_file(cls, path: Path) -> Optional["VRDBConsole"]:
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            if "Console" not in data or "Emulator" not in data:
                return None

            emulator_data = data.get("Emulator", {})
            emulator = EmulatorInfo(
                name=emulator_data.get("Name", ""),
                binary=emulator_data.get("Binary", ""),
                url=emulator_data.get("URL", ""),
                requires_bios=emulator_data.get("RequiresBios", False),
                bios_files=emulator_data.get("BiosFiles", []),
                launch_command=emulator_data.get("LaunchCommand", "{binary} {rom}"),
            )

            console_data = data.get("Console", {})
            console = ConsoleInfo(
                code=console_data.get("Code", ""),
                name=console_data.get("Name", ""),
                release=console_data.get("Release", ""),
                manufacturer=console_data.get("Manufacturer", ""),
                formats=console_data.get("Formats", []),
                generation=console_data.get("Generation"),
            )

            games = {}
            games_data = data.get("Games", {})
            for game_name, uri in games_data.items():
                if isinstance(uri, str):
                    source = GameSource.from_uri(uri)
                    if source:
                        games[game_name] = source

            return cls(emulator=emulator, console=console, games=games)

        except Exception:
            return None


class VRDBDatabase:
    def __init__(self, db_dir: Optional[Path] = None):
        if db_dir is None:
            db_dir = get_config_dir() / "db"

        self.db_dir = db_dir
        self.consoles: Dict[str, VRDBConsole] = {}
        self.romheaven_consoles: List[str] = []

        self._load_database()

    def _load_database(self):
        if not self.db_dir.exists():
            self.db_dir.mkdir(parents=True, exist_ok=True)
            return

        romheaven_file = self.db_dir / "romheaven.vrdb"
        if romheaven_file.exists():
            try:
                with open(romheaven_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            self.romheaven_consoles.append(line)
            except Exception:
                pass

        for vrdb_file in self.db_dir.glob("*.vrdb"):
            if vrdb_file.name == "romheaven.vrdb":
                continue

            console = VRDBConsole.from_file(vrdb_file)
            if console and console.console.code:
                self.consoles[console.console.code] = console

    def get_console(self, code: str) -> Optional[VRDBConsole]:
        return self.consoles.get(code.upper())

    def get_console_by_name(self, name: str) -> Optional[VRDBConsole]:
        for console in self.consoles.values():
            if console.console.name == name:
                return console
        return None

    def list_consoles(self) -> List[str]:
        return list(self.consoles.keys())

    def search_games(
        self, console_code: str, query: str
    ) -> List[Tuple[str, GameSource]]:
        console = self.get_console(console_code)
        if not console:
            return []

        query_lower = query.lower()
        results = []

        for game_name, source in console.games.items():
            if query_lower in game_name.lower():
                results.append((game_name, source))

        return results

    def get_game(self, console_code: str, game_name: str) -> Optional[GameSource]:
        console = self.get_console(console_code)
        if not console:
            return None

        return console.games.get(game_name)

    def is_romheaven_compatible(self, console_name: str) -> bool:
        return console_name in self.romheaven_consoles


_vrdb = None


def get_vrdb() -> VRDBDatabase:
    global _vrdb
    if _vrdb is None:
        _vrdb = VRDBDatabase()
    return _vrdb
