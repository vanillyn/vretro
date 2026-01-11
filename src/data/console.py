import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class EmulatorConfig:
    name: str
    binary: str
    download_url: Optional[str] = None
    args: List[str] = field(default_factory=list)
    requires_bios: bool = False
    bios_files: List[str] = field(default_factory=list)
    launch_command: str = "{binary} {rom}"


@dataclass
class ConsoleMetadata:
    code: str
    name: str
    release: str
    manufacturer: str
    formats: List[str]
    emulator: EmulatorConfig
    generation: Optional[int] = None
    retroachievements_console_id: Optional[int] = None

    @classmethod
    def from_json(cls, data: dict, manufacturer: str = "unknown"):
        emulator_data = data.get("emulator", {})
        emulator = EmulatorConfig(
            name=emulator_data.get("name", ""),
            binary=emulator_data.get("binary", ""),
            download_url=emulator_data.get("download_url"),
            args=emulator_data.get("args", []),
            requires_bios=emulator_data.get("requires_bios", False),
            bios_files=emulator_data.get("bios_files", []),
            launch_command=emulator_data.get("launch_command", "{binary} {rom}"),
        )

        return cls(
            code=data["code"],
            name=data["name"],
            release=data["release"],
            manufacturer=manufacturer,
            formats=data["formats"],
            emulator=emulator,
            generation=data.get("generation"),
            retroachievements_console_id=data.get("retroachievements_console_id"),
        )

    @classmethod
    def from_vrdb(cls, vrdb_console):
        emulator = EmulatorConfig(
            name=vrdb_console.emulator.name,
            binary=vrdb_console.emulator.binary,
            download_url=vrdb_console.emulator.url,
            args=[],
            requires_bios=vrdb_console.emulator.requires_bios,
            bios_files=vrdb_console.emulator.bios_files,
            launch_command=vrdb_console.emulator.launch_command,
        )

        return cls(
            code=vrdb_console.console.code,
            name=vrdb_console.console.name,
            release=vrdb_console.console.release,
            manufacturer=vrdb_console.console.manufacturer,
            formats=vrdb_console.console.formats,
            emulator=emulator,
            generation=vrdb_console.console.generation,
            retroachievements_console_id=vrdb_console.console.retroachievements_console_id,
        )

    def to_json(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "release": self.release,
            "manufacturer": self.manufacturer,
            "formats": self.formats,
            "generation": self.generation,
            "retroachievements_console_id": self.retroachievements_console_id,
            "emulator": {
                "name": self.emulator.name,
                "binary": self.emulator.binary,
                "download_url": self.emulator.download_url,
                "args": self.emulator.args,
                "requires_bios": self.emulator.requires_bios,
                "bios_files": self.emulator.bios_files,
                "launch_command": self.emulator.launch_command,
            },
        }

    @classmethod
    def load(cls, console_dir: Path) -> Optional["ConsoleMetadata"]:
        metadata_file = console_dir / "console.json"
        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)
                return cls.from_json(data, data.get("manufacturer", "unknown"))
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def save(self, console_dir: Path):
        metadata_file = console_dir / "console.json"

        with open(metadata_file, "w") as f:
            json.dump(self.to_json(), f, indent=2)


def get_console_metadata(code: str) -> Optional[ConsoleMetadata]:
    from ..util.vrdb import get_vrdb

    vrdb = get_vrdb()
    vrdb_console = vrdb.get_console(code)

    if vrdb_console:
        return ConsoleMetadata.from_vrdb(vrdb_console)

    vrdb_console = vrdb.get_console_by_name(code)
    if vrdb_console:
        return ConsoleMetadata.from_vrdb(vrdb_console)

    return None
