#!/usr/bin/env python3
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402
from game.narrator import ascii_banner, line, ruby_available, type_effect  # noqa: E402
from game.online import DEFAULT_PORT, host_game, join_game  # noqa: E402
from game.score import DATA_DIR, PROJECT_ROOT, ScoreManager  # noqa: E402

MENU_ITEMS = [
    ("1", "Host a room"),
    ("2", "Join a room"),
    ("3", "Rules"),
    ("4", "Statistics"),
    ("5", "Quit"),
]
def check_permissions(console: Console) -> bool:
    for target_dir in (PROJECT_ROOT, DATA_DIR):
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target_dir, delete=True):
                pass
        except OSError:
            console.print(
                Panel(
                    f"[bold red]ROULETTE cannot write to:[/bold red]\n{target_dir}\n\n"
                    "The game needs permission to write its save data "
                    "(scores.json, deaths.log) and death records (rolet.txt) "
                    "in its own project folder.\n\n"
                    "Please run the game from a location you have write "
                    "access to, or adjust the folder's permissions, then "
                    "try again.",
                    title="Permission Required",
                    border_style="red",
                ))
            return False
    return True
def show_title(console: Console) -> None:
    console.clear()
    banner = ascii_banner("TITLE")
    if banner:
        console.print(Text(banner, style="bold red"))
    else:
        console.print(Panel("ROULETTE", style="bold red", border_style="red"))

    if not ruby_available():
        console.print(
            "[yellow]Note: Ruby was not found on PATH — narrative text will use "
            "built-in fallback lines instead of the full Ruby narrative engine.[/yellow]"
        )
def show_rules(console: Console, require_ack: bool = True) -> None:
    console.clear()
    banner = ascii_banner("REVOLVER")
    if banner:
        console.print(Text(banner, style="bold red"))
    rules_table = Table.grid(padding=(0, 2))
    rules_table.add_column(style="bold red")
    rules_table.add_column(style="white")
    rules = [
        ("6", "chambers. 1 bullet. Turns alternate, no exceptions."),
        ("PULL", "is the only move. There is no walking away from the table."),
        ("SCORE", "climbs slowly with every pull you survive, faster the longer your streak."),
        ("LAST CHANCE", "if a shot lands and you can afford it, you'll be asked to spend score to survive. Once, ever."),
        ("END", "the moment one player is truly out of chances — no Last Chance left, no luck left."),
    ]
    for label, desc in rules:
        rules_table.add_row(f"[{label}]", desc)
    console.print(Panel(rules_table, title="The Rules", border_style="grey50", padding=(1, 2)))
    type_effect(line("RULES"), 0.012)

    if require_ack:
        console.input("\n[dim]Press Enter to continue...[/dim]")
def show_menu(console: Console) -> str:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold red")
    table.add_column(style="white")
    for key, label in MENU_ITEMS:
        table.add_row(f"[{key}]", label)
    console.print(Panel(table, title="Main Menu", border_style="grey50", padding=(1, 2)))
    valid_keys = {key for key, _ in MENU_ITEMS}
    while True:
        choice = console.input("[bold red]> [/bold red]").strip()
        if choice in valid_keys:
            return choice
        console.print("[red]Invalid selection.[/red]")

def prompt_name(console: Console) -> str:
    name = console.input("[bold cyan]Enter your name: [/bold cyan]").strip()
    return name or "Player"

def prompt_room(console: Console) -> str:
    room = console.input("[bold cyan]Room name: [/bold cyan]").strip()
    return room or "default"

def show_statistics(console: Console) -> None:
    console.clear()
    stats = ScoreManager().summary()
    table = Table(title="Statistics", border_style="cyan", show_lines=False)
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="cyan")
    table.add_row("Total games played", str(stats["total_games"]))
    table.add_row("Wins", str(stats["wins"]))
    table.add_row("Losses", str(stats["losses"]))
    table.add_row("Best score", str(stats["best_score"]))
    table.add_row("Current streak", str(stats["current_streak"]))
    table.add_row("Best streak", str(stats["best_streak"]))
    console.print(table)
    recent = stats["history"][-8:][::-1]
    if recent:
        history_table = Table(title="Recent Matches", border_style="grey50")
        history_table.add_column("Result")
        history_table.add_column("Score")
        history_table.add_column("Room")
        history_table.add_column("Opponent")
        history_table.add_column("Last Chance")
        history_table.add_column("Timestamp (UTC)")
        for entry in recent:
            result_style = "green" if entry["result"] == "win" else "red"
            history_table.add_row(
                f"[{result_style}]{entry['result'].upper()}[/{result_style}]",
                str(entry["score"]),
                entry.get("room_name", "-"),
                entry.get("opponent_name", "-"),
                "yes" if entry.get("used_last_chance") else "no",
                entry["timestamp"],
            )
        console.print(history_table)
    console.input("\n[dim]Press Enter to return to the main menu...[/dim]")

def run_host(console: Console) -> None:
    name = prompt_name(console)
    room = prompt_room(console)
    use_remote = console.input(
        "[bold cyan]Host on an existing server instead of starting one locally? "
        "[y/N]: [/bold cyan]"
    ).strip().lower()
    if use_remote in ("y", "yes"):
        address = console.input("[bold cyan]Server address: [/bold cyan]").strip()
        port_raw = console.input(
            f"[bold cyan]Port (default {DEFAULT_PORT}): [/bold cyan]"
        ).strip()
        port = int(port_raw) if port_raw.isdigit() else DEFAULT_PORT
        if not address:
            console.print("[red]A server address is required.[/red]")
            console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
            return
        host_game(console, name, room, server_address=address, port=port)
    else:
        port_raw = console.input(
            f"[bold cyan]Local port to use (default {DEFAULT_PORT}): [/bold cyan]"
        ).strip()
        port = int(port_raw) if port_raw.isdigit() else DEFAULT_PORT
        host_game(console, name, room, server_address=None, port=port)

def run_join(console: Console) -> None:
    name = prompt_name(console)
    room = prompt_room(console)
    address = console.input("[bold cyan]Server address (e.g. 192.168.1.5): [/bold cyan]").strip()
    port_raw = console.input(
        f"[bold cyan]Port (default {DEFAULT_PORT}): [/bold cyan]"
    ).strip()
    port = int(port_raw) if port_raw.isdigit() else DEFAULT_PORT
    if not address:
        console.print("[red]A server address is required.[/red]")
        console.input("\n[dim]Press Enter to return to the main menu...[/dim]")
        return
    join_game(console, name, room, address, port=port)

def main() -> None:
    console = Console()
    if not check_permissions(console):
        sys.exit(1)
    show_title(console)
    show_rules(console)
    try:
        while True:
            show_title(console)
            choice = show_menu(console)
            if choice == "1":
                run_host(console)
            elif choice == "2":
                run_join(console)
            elif choice == "3":
                show_rules(console)
            elif choice == "4":
                show_statistics(console)
            elif choice == "5":
                console.clear()
                console.print("[bold red]The chamber closes. Until next time.[/bold red]")
                break
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted. The chamber closes.[/bold red]")

if __name__ == "__main__":
    main()
