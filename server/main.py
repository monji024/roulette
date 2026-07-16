#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import socket
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from game.narrator import line 
from game.revolver import Revolver  
from game.score import LAST_CHANCE_COST, try_last_chance

CHAMBERS = 6
POINTS_PER_SURVIVAL = 5
ROOM_JOIN_TIMEOUT = 300

@dataclass
class Player:
    player_id: int
    name: str = "Player"
    conn: socket.socket | None = None
    file: Any = field(default=None, repr=False)
    score: int = 0
    streak: int = 0
    alive: bool = True
    used_last_chance: bool = False
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    def send(self, message: dict) -> bool:
        if self.conn is None:
            return False
        try:
            payload = (json.dumps(message) + "\n").encode("utf-8")
            with self.send_lock:
                self.conn.sendall(payload)
            return True
        except OSError:
            return False
    def recv_line(self) -> dict | None:
        if self.file is None:
            return None
        try:
            raw = self.file.readline()
        except OSError:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8").strip())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
@dataclass
class Room:
    name: str
    host: Player
    guest: Player | None = None
    ready_event: threading.Event = field(default_factory=threading.Event)
    revolver: Revolver = field(default_factory=lambda: Revolver(chamber_count=CHAMBERS))
    round_number: int = 0

class RoomRegistry:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = threading.Lock()
    def create(self, name: str, host: Player) -> Room | None:
        with self._lock:
            if name in self._rooms:
                return None
            room = Room(name=name, host=host)
            self._rooms[name] = room
            return room
    def attach_guest(self, name: str, guest: Player) -> Room | None:
        with self._lock:
            room = self._rooms.get(name)
            if room is None or room.guest is not None:
                return None
            room.guest = guest
            return room
    def remove(self, name: str) -> None:
        with self._lock:
            self._rooms.pop(name, None)

REGISTRY = RoomRegistry()
def _broadcast(room: Room, message: dict) -> None:
    room.host.send(message)
    if room.guest is not None:
        room.guest.send(message)

def _scores(room: Room) -> dict[str, int]:
    scores = {"1": room.host.score}
    if room.guest is not None:
        scores["2"] = room.guest.score
    return scores

def _handle_turn(room: Room, player: Player) -> bool:
    _broadcast(room, {"type": "turn", "player_id": player.player_id})
    _broadcast(room, {"type": "narration", "text": line("PRE_TRIGGER")})
    action_msg = player.recv_line()
    if action_msg is None or action_msg.get("action") != "pull":
        player.alive = False
        _broadcast(room, {"type": "opponent_left", "player_id": player.player_id})
        return False

    _broadcast(room, {"type": "narration", "text": line("SPIN")})
    is_hit = room.revolver.pull_trigger()
    survived = not is_hit
    saved_by_last_chance = False

    if is_hit:
        eligible, _ = try_last_chance(player.score, player.used_last_chance)
        if eligible:
            offered = player.send(
                {
                    "type": "last_chance_prompt",
                    "cost": LAST_CHANCE_COST,
                    "score": player.score,
                }
            )
            response = player.recv_line() if offered else None
            if response is None:
                player.alive = False
                _broadcast(room, {"type": "opponent_left", "player_id": player.player_id})
                return False
            wants_to_spend = bool(response.get("accept"))
            if wants_to_spend:
                player.score -= LAST_CHANCE_COST
                player.used_last_chance = True
                survived = True
                saved_by_last_chance = True
                _broadcast(
                    room,
                    {
                        "type": "narration",
                        "text": f"{line('LAST_CHANCE')} (-{LAST_CHANCE_COST} pts)",
                    },
                )
    if survived:
        if not saved_by_last_chance:
            player.streak += 1
            player.score += POINTS_PER_SURVIVAL * player.streak
            _broadcast(room, {"type": "narration", "text": line("SURVIVE")})
    else:
        player.alive = False
        player.streak = 0
        _broadcast(room, {"type": "narration", "text": line("DEATH")})
    _broadcast(
        room,
        {
            "type": "result",
            "player_id": player.player_id,
            "name": player.name,
            "survived": survived,
            "last_chance_used": saved_by_last_chance,
            "scores": _scores(room),
        },
    )
    if is_hit:
        room.revolver.spin()
    return player.alive

def _run_match(room: Room) -> None:
    assert room.guest is not None
    room.revolver.spin()
    turn_order = [room.host, room.guest]
    try:
        while True:
            room.round_number += 1
            _broadcast(room, {"type": "round_start", "round": room.round_number})
            for player in turn_order:
                if not player.alive:
                    continue
                still_alive = _handle_turn(room, player)
                if not still_alive:
                    break
            if not room.host.alive or not room.guest.alive:
                break
        _resolve_game_over(room)
    finally:
        REGISTRY.remove(room.name)
        for player in (room.host, room.guest):
            if player.conn:
                try:
                    player.conn.close()
                except OSError:
                    pass
def _resolve_game_over(room: Room) -> None:
    host, guest = room.host, room.guest
    assert guest is not None
    if not host.alive and guest.alive:
        winner_id, reason = 2, "opponent eliminated"
    elif not guest.alive and host.alive:
        winner_id, reason = 1, "opponent eliminated"
    else:
        winner_id, reason = None, "mutual elimination"
    _broadcast(
        room,
        {
            "type": "game_over",
            "winner_id": winner_id,
            "reason": reason,
            "scores": _scores(room),
        },
    )
def _onboard_connection(conn: socket.socket, addr: tuple) -> None:
    file_obj = conn.makefile("rb")
    try:
        raw = file_obj.readline()
        if not raw:
            conn.close()
            return
        hello = json.loads(raw.decode("utf-8").strip())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        conn.close()
        return
    msg_type = hello.get("type")
    room_name = str(hello.get("room") or "").strip()
    player_name = str(hello.get("name") or "Player").strip() or "Player"
    if not room_name:
        conn.sendall((json.dumps({"type": "room_error", "message": "A room name is required."}) + "\n").encode())
        conn.close()
        return
    if msg_type == "host":
        player = Player(player_id=1, name=player_name, conn=conn, file=file_obj)
        room = REGISTRY.create(room_name, player)
        if room is None:
            player.send({"type": "room_error", "message": f"Room '{room_name}' already exists."})
            conn.close()
            return
        player.send({"type": "welcome", "player_id": 1, "room": room_name})
        player.send({"type": "waiting_for_opponent"})
        print(f"[server] Room '{room_name}' created by '{player_name}' ({addr}).")
        if not room.ready_event.wait(timeout=ROOM_JOIN_TIMEOUT):
            player.send({"type": "room_error", "message": "No opponent joined in time."})
            REGISTRY.remove(room_name)
            conn.close()
            return
        return
    if msg_type == "join":
        player = Player(player_id=2, name=player_name, conn=conn, file=file_obj)
        room = REGISTRY.attach_guest(room_name, player)
        if room is None:
            player.send(
                {
                    "type": "room_error",
                    "message": f"Room '{room_name}' was not found or is already full.",
                }
            )
            conn.close()
            return
        player.send({"type": "welcome", "player_id": 2, "room": room_name})
        room.host.send({"type": "opponent_joined", "name": player.name})
        player.send({"type": "opponent_joined", "name": room.host.name})
        print(f"[server] '{player_name}' joined room '{room_name}' ({addr}).")
        room.ready_event.set()
        match_thread = threading.Thread(target=_run_match, args=(room,), daemon=True)
        match_thread.start()
        return
    conn.sendall((json.dumps({"type": "room_error", "message": "Unknown request type."}) + "\n").encode())
    conn.close()
def serve_forever(host: str, port: int) -> None:
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(16)
    print(f"[server] ROULETTE server listening on {host}:{port}")
    try:
        while True:
            conn, addr = server_sock.accept()
            threading.Thread(
                target=_onboard_connection, args=(conn, addr), daemon=True
            ).start()
    finally:
        server_sock.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="ROULETTE multi-room match server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=5555, help="Bind port")
    args = parser.parse_args()
    try:
        serve_forever(args.host, args.port)
    except KeyboardInterrupt:
        print("\n[server] Interrupted. Shutting down.")

if __name__ == "__main__":
    main()
