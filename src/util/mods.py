import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ModInfo:
    name: str
    description: str
    version: str
    author: str
    enabled: bool = False
    install_path: str = ""

    @classmethod
    def from_json(cls, data: dict) -> "ModInfo":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            author=data.get("author", "unknown"),
            enabled=data.get("enabled", False),
            install_path=data.get("install_path", ""),
        )

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "enabled": self.enabled,
            "install_path": self.install_path,
        }


class ModManager:
    def __init__(self, game_path: Path):
        self.game_path = game_path
        self.mods_dir = game_path / "mods"
        self.active_mods_dir = game_path / "active_mods"
        self.mods_config = game_path / "mods.json"

        self.mods_dir.mkdir(exist_ok=True)
        self.active_mods_dir.mkdir(exist_ok=True)

        self.mods: List[ModInfo] = []
        self._load_mods()

    def _load_mods(self) -> None:
        self.mods = []

        if self.mods_config.exists():
            try:
                with open(self.mods_config, "r") as f:
                    data = json.load(f)
                    self.mods = [ModInfo.from_json(m) for m in data.get("mods", [])]
            except (json.JSONDecodeError, KeyError):
                pass

        for mod_dir in self.mods_dir.iterdir():
            if not mod_dir.is_dir():
                continue

            if not any(m.name == mod_dir.name for m in self.mods):
                mod_info_file = mod_dir / "mod.json"
                if mod_info_file.exists():
                    try:
                        with open(mod_info_file, "r") as f:
                            mod_data = json.load(f)
                            mod = ModInfo.from_json(mod_data)
                            mod.name = mod_dir.name
                            self.mods.append(mod)
                    except (json.JSONDecodeError, KeyError):
                        self.mods.append(
                            ModInfo(
                                name=mod_dir.name,
                                description="",
                                version="1.0",
                                author="unknown",
                            )
                        )
                else:
                    self.mods.append(
                        ModInfo(
                            name=mod_dir.name,
                            description="",
                            version="1.0",
                            author="unknown",
                        )
                    )

    def save_config(self) -> None:
        data = {"mods": [m.to_json() for m in self.mods]}
        with open(self.mods_config, "w") as f:
            json.dump(data, f, indent=2)

    def get_mod(self, name: str) -> Optional[ModInfo]:
        for mod in self.mods:
            if mod.name == name:
                return mod
        return None

    def enable_mod(self, name: str, install_path: str = "") -> bool:
        mod = self.get_mod(name)
        if not mod:
            return False

        mod.enabled = True
        mod.install_path = install_path
        self.save_config()
        return True

    def disable_mod(self, name: str) -> bool:
        mod = self.get_mod(name)
        if not mod:
            return False

        mod.enabled = False
        self.save_config()
        return True

    def apply_mods(self, target_dir: Path) -> bool:
        try:
            if self.active_mods_dir.exists():
                shutil.rmtree(self.active_mods_dir)
            self.active_mods_dir.mkdir(exist_ok=True)

            for mod in self.mods:
                if not mod.enabled:
                    continue

                mod_dir = self.mods_dir / mod.name
                if not mod_dir.exists():
                    continue

                if mod.install_path:
                    dest = target_dir / mod.install_path
                else:
                    dest = self.active_mods_dir

                dest.mkdir(parents=True, exist_ok=True)

                for item in mod_dir.iterdir():
                    if item.name == "mod.json":
                        continue

                    if item.is_dir():
                        shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest / item.name)

            return True
        except Exception:
            return False

    def add_mod(self, source_path: Path, name: Optional[str] = None) -> bool:
        try:
            if not source_path.exists():
                return False

            mod_name = name or source_path.stem
            dest = self.mods_dir / mod_name

            if source_path.is_dir():
                shutil.copytree(source_path, dest, dirs_exist_ok=True)
            else:
                dest.mkdir(exist_ok=True)
                shutil.copy2(source_path, dest / source_path.name)

            self._load_mods()
            return True
        except Exception:
            return False

    def remove_mod(self, name: str) -> bool:
        try:
            mod_dir = self.mods_dir / name
            if mod_dir.exists():
                shutil.rmtree(mod_dir)

            self.mods = [m for m in self.mods if m.name != name]
            self.save_config()
            return True
        except Exception:
            return False
