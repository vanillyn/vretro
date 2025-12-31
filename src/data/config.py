import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class VRetroConfig:
    games_directory: str
    search_directories: List[str]
    ignored_directories: List[str]
    fullscreen: bool = False
    use_gamescope: bool = False
    gamescope_width: int = 1920
    gamescope_height: int = 1080
    show_thumbnails: bool = True
    thumbnail_width: int = 320
    preferred_region: str = "NA"
    igdb_client_id: Optional[str] = None
    igdb_client_secret: Optional[str] = None
    download_sources: List[str] = None

    @classmethod
    def default(cls):
        return cls(
            games_directory=str(Path.home() / "games"),
            search_directories=[],
            ignored_directories=["vretro"],
            fullscreen=False,
            use_gamescope=False,
            gamescope_width=1920,
            gamescope_height=1080,
            show_thumbnails=True,
            thumbnail_width=320,
            preferred_region="NA",
        )

    @classmethod
    def load(cls, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_config_path()

        if not config_path.exists():
            config = cls.default()
            config.save(config_path)
            return config

        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            if "ignored_directories" not in data:
                data["ignored_directories"] = ["vretro"]

            return cls(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return cls.default()

    def save(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_config_path()

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    def get_games_root(self) -> Path:
        return Path(self.games_directory).expanduser()


def get_config_dir() -> Path:
    config_home = Path.home() / ".config"
    return config_home / "vretro"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"
