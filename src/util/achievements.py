import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import requests

from src.data.config import get_config_dir

logger = logging.getLogger(__name__)


@dataclass
class Achievement:
    id: int
    title: str
    description: str
    points: int
    badge_url: str
    unlocked: bool = False
    unlock_time: Optional[int] = None


@dataclass
class UserProgress:
    earned_hardcore: int
    earned_softcore: int
    total_achievements: int
    total_points: int
    earned_points: int


class RetroAchievementsAPI:
    def __init__(self, api_key: Optional[str] = None, username: Optional[str] = None):
        self.api_base = "https://retroachievements.org/API"
        self.api_key = api_key
        self.username = username
        self.cache_dir = get_config_dir() / "cache" / "retroachievements"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 3600

    def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.api_key:
            logger.warning("retroachievements api key not configured")
            return None

        try:
            url = f"{self.api_base}/{endpoint}"
            request_params = {"y": self.api_key, "z": self.username or ""}
            if params:
                request_params.update(params)

            logger.debug(
                f"retroachievements api request: {endpoint} with params {request_params}"
            )

            response = requests.get(url, params=request_params, timeout=10)

            if response.status_code != 200:
                logger.error(f"retroachievements api error: {response.status_code}")
                return None

            data = response.json()
            logger.debug(f"retroachievements api response: {len(str(data))} bytes")
            return data

        except requests.RequestException as e:
            logger.error(f"retroachievements api request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"retroachievements api error: {e}")
            return None

    def get_game_info(self, game_id: int) -> Optional[dict]:
        logger.info(f"fetching retroachievements game info for id {game_id}")
        return self._request("API_GetGame.php", {"i": game_id})

    def get_game_achievements(
        self, game_id: int, hardcore: bool = False
    ) -> List[Achievement]:
        logger.info(f"fetching achievements for game id {game_id}")

        if not self.username:
            logger.warning(
                "retroachievements username not configured, fetching basic achievement list"
            )
            data = self._request("API_GetGameExtended.php", {"i": game_id})
        else:
            data = self._request(
                "API_GetGameInfoAndUserProgress.php",
                {"g": game_id, "u": self.username},
            )

        if not data:
            logger.error(f"failed to fetch achievements for game {game_id}")
            return []

        if "Achievements" not in data:
            logger.warning(f"no achievements found for game {game_id}")
            return []

        achievements = []
        for ach_id, ach_data in data["Achievements"].items():
            unlocked = (
                ach_data.get("DateEarned") is not None
                or ach_data.get("DateEarnedHardcore") is not None
            )
            unlock_time = None

            if unlocked:
                date_str = ach_data.get("DateEarnedHardcore") or ach_data.get(
                    "DateEarned"
                )
                if date_str:
                    try:
                        unlock_time = int(
                            time.mktime(time.strptime(date_str, "%Y-%m-%d %H:%M:%S"))
                        )
                    except:
                        pass

            badge_name = ach_data.get("BadgeName", "")
            badge_url = f"https://media.retroachievements.org/Badge/{badge_name}.png"

            achievements.append(
                Achievement(
                    id=int(ach_id),
                    title=ach_data.get("Title", ""),
                    description=ach_data.get("Description", ""),
                    points=int(ach_data.get("Points", 0)),
                    badge_url=badge_url,
                    unlocked=unlocked,
                    unlock_time=unlock_time,
                )
            )

        logger.info(f"loaded {len(achievements)} achievements for game {game_id}")
        return achievements

    def get_user_progress(self, game_id: int) -> Optional[UserProgress]:
        if not self.username:
            logger.warning("cannot get user progress without username")
            return None

        logger.info(f"fetching user progress for game {game_id}")

        data = self._request(
            "API_GetGameInfoAndUserProgress.php", {"g": game_id, "u": self.username}
        )

        if not data or "Achievements" not in data:
            logger.error(f"failed to fetch user progress for game {game_id}")
            return None

        total_achievements = len(data.get("Achievements", {}))
        total_points = sum(
            int(ach.get("Points", 0)) for ach in data.get("Achievements", {}).values()
        )

        earned_hardcore = 0
        earned_softcore = 0
        earned_points = 0

        for ach in data.get("Achievements", {}).values():
            if ach.get("DateEarnedHardcore"):
                earned_hardcore += 1
                earned_points += int(ach.get("Points", 0))
            elif ach.get("DateEarned"):
                earned_softcore += 1
                earned_points += int(ach.get("Points", 0))

        progress = UserProgress(
            earned_hardcore=earned_hardcore,
            earned_softcore=earned_softcore,
            total_achievements=total_achievements,
            total_points=total_points,
            earned_points=earned_points,
        )

        logger.info(
            f"user progress: {earned_hardcore + earned_softcore}/{total_achievements} achievements"
        )
        return progress

    def search_game(self, console_id: int, game_name: str) -> Optional[int]:
        logger.info(
            f"searching retroachievements for '{game_name}' on console {console_id}"
        )

        data = self._request("API_GetGameList.php", {"i": console_id})

        if not data:
            logger.error(f"failed to fetch game list for console {console_id}")
            return None

        game_name_lower = game_name.lower().strip()
        game_name_clean = game_name_lower.replace(":", "").replace("-", " ")

        best_match = None
        best_score = 0

        for game in data:
            title = game.get("Title", "").lower().strip()
            title_clean = title.replace(":", "").replace("-", " ")

            if title == game_name_lower or title_clean == game_name_clean:
                logger.info(
                    f"exact match found: {game.get('Title')} (id: {game.get('ID')})"
                )
                return int(game.get("ID"))

            if game_name_lower in title or title in game_name_lower:
                score = len(game_name_lower) / max(len(title), 1)
                if score > best_score:
                    best_score = score
                    best_match = game

            if game_name_clean in title_clean or title_clean in game_name_clean:
                score = len(game_name_clean) / max(len(title_clean), 1)
                if score > best_score:
                    best_score = score
                    best_match = game

        if best_match and best_score > 0.5:
            logger.info(
                f"fuzzy match found: {best_match.get('Title')} (id: {best_match.get('ID')}, score: {best_score:.2f})"
            )
            return int(best_match.get("ID"))

        logger.warning(f"no match found for '{game_name}' on console {console_id}")
        return None
