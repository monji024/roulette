from __future__ import annotations
import json
import queue
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from game.narrator import ascii_banner, type_effect
from game.score import ScoreManager, GameResult, append_death_log, delete_everything
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = PROJECT_ROOT / "server" / "main.py"

CONNECT_TIMEOUT = 10
DEFAULT_PORT = 5555

class OnlineSession:

    def __init__(self, console: Console, name: str, room: str, mode: str) -> None:
        self.console = console
        self.name = name
        self.room = room
        self.mode = mode 
        self.sock: socket.socket | None = None
        self.player_id: int | None = None
        self.opponent_name: str = "Opponent"
        self.scores: dict[str, int] = {"1": 0, "2": 0}
        self.rounds_seen = 0
        self._events: "queue.Queue[dict]" = queue.Queue()
        self._reader_thread: threading.Thread | None = None
    def connect(self, host: str, port: int) -> None:
        try:
            self.sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
        except OSError as exc:
            raise ConnectionFailed(f"Could not reach {host}:{port} ({exc})") from exc
        self.sock.settimeout(None)
        request_type = "host" if self.mode == "online-host" else "join"
        self._send({"type": request_type, "room": self.room, "name": self.name})
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
    def _send(self, message: dict) -> None:
        if self.sock is None:
            return
        try:
            self.sock.sendall((json.dumps(message) + "\n").encode("utf-8"))
        except OSError:
            pass
    def _read_loop(self) -> None:
        assert self.sock is not None
        file_obj = self.sock.makefile("rb")
        while True:
            try:
                raw = file_obj.readline()
            except OSError:
                break
            if not raw:
                break
            try:
                message = json.loads(raw.decode("utf-8").strip())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            self._events.put(message)
        self._events.put({"type": "_disconnected"})
    def _next_event(self, timeout: float = 320.0) -> dict | None:
        try:
            return self._events.get(timeout=timeout)
        except queue.Empty:
            return None
    def _status_panel(self, phase: str) -> Panel:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold white")
        table.add_column(style="cyan")
        table.add_row("Room", self.room)
        table.add_row("You", self.name)
        table.add_row("Opponent", self.opponent_name)
        table.add_row("Your score", str(self.scores.get(str(self.player_id), 0)))
        opp_id = 2 if self.player_id == 1 else 1
        table.add_row("Opponent score", str(self.scores.get(str(opp_id), 0)))
        return Panel(
            table,
            title=f"[bold red]ROULETTE[/bold red] — Online — {phase}",
            border_style="red",
            padding=(1, 2),
        )
    def _render(self, phase: str, body: str = "") -> None:
        self.console.clear()
        self.console.print(self._status_panel(phase))
        if body:
            self.console.print(Panel(Text(body, style="italic grey78"), border_style="grey42"))
    def run(self) -> None:
        self._render("Connecting", "Waiting for the room to be ready...")

        while True:
            event = self._next_event()
            if event is None:
                self._render("Timeout", "No response from the server. Connection lost.")
                self.console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
                return
            if not self._process_event(event):
                return
    def _process_event(self, event: dict) -> bool:
        etype = event.get("type")
        if etype == "welcome":
            self.player_id = event.get("player_id")
            self._render("Waiting", f"Connected to room '{self.room}'.")
        elif etype == "room_error":
            self._render("Room Error", str(event.get("message", "The room could not be joined.")))
            self.console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
            return False
        elif etype == "waiting_for_opponent":
            self._render("Waiting", "You created this room. Waiting for a challenger to join...")
        elif etype == "opponent_joined":
            self.opponent_name = str(event.get("name") or "Opponent")
            banner = ascii_banner("REVOLVER")
            self._render("Match Found", f"{self.opponent_name} has joined the table.")
            if banner:
                self.console.print(Text(banner, style="bold red"))
            time.sleep(1.2)
        elif etype == "round_start":
            self.rounds_seen = event.get("round", self.rounds_seen + 1)
            self._render("Round", f"Round {self.rounds_seen} begins.")
            time.sleep(0.8)
        elif etype == "narration":
            text = str(event.get("text", ""))
            self._render("...", "")
            type_effect(text, 0.012)
            time.sleep(0.25)
        elif etype == "turn":
            if event.get("player_id") == self.player_id:
                if not self._handle_my_turn():
                    return False
            else:
                self._render("Opponent's Turn", f"{self.opponent_name} is at the table.")
                time.sleep(0.8)
        elif etype == "last_chance_prompt":
            self._handle_last_chance_prompt(event)
        elif etype == "result":
            self.scores = event.get("scores", self.scores)
            name = event.get("name", "?")
            survived = event.get("survived")
            saved = event.get("last_chance_used")
            if saved:
                outcome = "used their Last Chance to survive"
            elif survived:
                outcome = "survived that pull"
            else:
                outcome = "did not survive"
            self._render("Result", f"{name} {outcome}.")
            time.sleep(1.1)
        elif etype == "opponent_left":
            self._render("Disconnected", "Your opponent disconnected. The match has ended.")
            self.console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
            return False
        elif etype == "game_over":
            self._show_game_over(event)
            return False
        elif etype == "_disconnected":
            self._render("Connection Lost", "The connection to the server was lost.")
            self.console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
            return False
        elif etype == "error":
            self._render("Error", str(event.get("message", "Unknown error.")))
            time.sleep(2)
        return True
    def _handle_my_turn(self) -> bool:
        self._render("Your Turn", "One decision remains.")
        self.console.print(
            Panel(
                "[bold]The revolver is yours. There is no walking away from this table.[/bold]",
                border_style="yellow",
            ))
        self.console.input("[bold red]Press Enter to pull the trigger...[/bold red]")
        self._send({"type": "action", "action": "pull"})
        return True
    def _handle_last_chance_prompt(self, event: dict) -> None:
        cost = event.get("cost", 0)
        score = event.get("score", 0)
        self._render("The Chamber Was Not Empty", "")
        self.console.print(
            Panel(
                f"[bold red]The shot landed.[/bold red] You are carrying "
                f"[bold]{score}[/bold] points — enough for your one-time "
                f"Last Chance.\n\n"
                f"Spend [bold]{cost}[/bold] points to survive this shot? "
                f"This can only be used once, ever.",
                title="Last Chance",
                border_style="yellow",
            ))
        while True:
            choice = self.console.input(
                "[bold red]Spend your score and survive? [y/n]: [/bold red]"
            ).strip().lower()
            if choice in ("y", "yes"):
                self._send({"type": "last_chance_response", "accept": True})
                return
            if choice in ("n", "no"):
                self._send({"type": "last_chance_response", "accept": False})
                return
            self.console.print("[red]Please answer y or n.[/red]")
    def _show_game_over(self, event: dict) -> None:
        self.scores = event.get("scores", self.scores)
        winner_id = event.get("winner_id")
        reason = event.get("reason", "")
        my_score = self.scores.get(str(self.player_id), 0)
        opp_id = 2 if self.player_id == 1 else 1
        opp_score = self.scores.get(str(opp_id), 0)
        won = winner_id == self.player_id
        result = GameResult(won=won,rounds_survived=self.rounds_seen,score=my_score,mode=self.mode,player_name=self.name,room_name=self.room,opponent_name=self.opponent_name)
        ScoreManager().record(result)
        self.console.clear()
        if winner_id is None:
            banner = ascii_banner("SKULL")
            title, style = "MUTUAL ELIMINATION", "yellow"
        elif won:
            banner = ascii_banner("SURVIVE")
            title, style = "VICTORY", "green"
        else:
            banner = ascii_banner("DEATH")
            title, style = "DEFEAT", "red"
        if banner:
            self.console.print(Text(banner, style=f"bold {style}"))
        self.console.print(
            Panel(
                f"[bold {style}]{title}[/bold {style}] — {reason}\n\n"
                f"Your score: [bold]{my_score}[/bold]\n"
                f"{self.opponent_name}'s score: [bold]{opp_score}[/bold]",
                border_style=style,
            ))
        if not won:
            append_death_log(result)
            from pathlib import Path
            log_path = Path(__file__).parent.parent / "data" / "deaths.log"
            self.console.print(f"\n[dim]A record was written to {log_path}[/dim]")
            self.console.print("[red]You'd better not back down; everything comes at a price:([/red]")
            delete_everything(result)
        self.console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass

def host_game(
    console: Console,
    name: str,
    room: str,
    server_address: str | None = None,
    port: int = DEFAULT_PORT,
) -> None:
    local_process = None
    if server_address is None:
        console.clear()
        console.print(
            Panel(
                f"Starting a local server on port {port} and creating room "
                f"'{room}'...",
                border_style="red",
            ))
        local_process = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT), "--host", "0.0.0.0", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)
        connect_address = "127.0.0.1"
    else:
        connect_address = server_address

    session = OnlineSession(console, name, room, mode="online-host")
    try:
        session.connect(connect_address, port)
        session.run()
    except ConnectionFailed as exc:
        console.print(f"[red]Failed to host the room: {exc}[/red]")
        console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
    finally:
        session.close()
        if local_process is not None and local_process.poll() is None:
            local_process.terminate()
            try:
                local_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                local_process.kill()

def join_game(
    console: Console, name: str, room: str, server_address: str, port: int = DEFAULT_PORT) -> None:
    session = OnlineSession(console, name, room, mode="online-join")
    try:
        session.connect(server_address, port)
        session.run()
    except ConnectionFailed as exc:
        console.print(f"[red]Connection failed: {exc}[/red]")
        console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
    finally:
        session.close()
