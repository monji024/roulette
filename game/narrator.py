from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TEXTS_SCRIPT = SCRIPTS_DIR / "texts.rb"
EFFECTS_SCRIPT = SCRIPTS_DIR / "effects.rb"
_RUBY_AVAILABLE: bool | None = None
_FALLBACK_LINES = {
    "INTRO": "The chamber waits.",
    "SPIN": "The chamber rotates.",
    "PRE_TRIGGER": "One decision remains.",
    "SURVIVE": "Luck has not abandoned you. Yet.",
    "DEATH": "The chamber was not empty.",
    "AMBIENT": "Something changed.",
    "GLITCH": "[SYSTEM] An unrecognized process is observing this session.",
    "OPPONENT_TURN": "Across the table, your opponent's hand moves toward the revolver.",
    "VICTORY": "You did not just survive. You outlasted the math itself.",
    "FAREWELL": "The terminal closes. The odds remain.",
    "LAST_CHANCE": "Your score was enough. Something was traded so you could keep breathing.",
    "RULES": "Two players. One revolver. Six chambers. One bullet.",
    "ROOM": "The room waits for a second name to appear beside yours."}

def ruby_available() -> bool:
    global _RUBY_AVAILABLE
    if _RUBY_AVAILABLE is None:
        _RUBY_AVAILABLE = shutil.which("ruby") is not None
    return _RUBY_AVAILABLE

def line(category: str) -> str:
    if ruby_available():
        try:
            result = subprocess.run(
                ["ruby", str(TEXTS_SCRIPT), category],
                capture_output=True,
                text=True,
                timeout=5,
                check=True)
            text = result.stdout.strip()
            if text:
                return text
        except (subprocess.SubprocessError, OSError):
            pass
    return _FALLBACK_LINES.get(category.upper(), "...")
def type_effect(text: str, delay: float = 0.02) -> None:
    if ruby_available():
        try:
            subprocess.run(
                ["ruby", str(EFFECTS_SCRIPT), "type", text, str(delay)],
                stdout=sys.stdout,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False)
            return
        except (subprocess.SubprocessError, OSError):
            pass
    print(text)
def glitch_effect(text: str) -> None:
    if ruby_available():
        try:
            subprocess.run(
                ["ruby", str(EFFECTS_SCRIPT), "glitch", text],
                stdout=sys.stdout,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False)
            return
        except (subprocess.SubprocessError, OSError):
            pass
    print(text)
def ascii_banner(name: str) -> str:
    if ruby_available():
        try:
            result = subprocess.run(
                ["ruby", str(EFFECTS_SCRIPT), "ascii", name],
                capture_output=True,
                text=True,
                timeout=5,
                check=True)
            return result.stdout
        except (subprocess.SubprocessError, OSError):
            pass
    return ""
