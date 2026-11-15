"""Authoritative match state for rooms hosted by Zero."""

import secrets

from game import BLACK, WHITE, FOULS, Game


class RoomError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Room:
    def __init__(self, size, renju, host_first, undo):
        self.game = Game(size, FOULS if renju else ())
        self.host_color = BLACK if host_first else WHITE
        self.undo = undo
        self.revision = 0
        self.players = {}
        self.closed = False

    def snapshot(self):
        game = self.game
        return {
            "size": game.size, "renju": bool(game.bans), "moves": game.history.copy(),
            "ready": len(self.players) == 2, "turn": game.turn,
            "ended": game.ended, "winner": game.result.winner,
            "line": game.result.line, "foul": game.result.foul,
            "undo": self.undo, "revision": self.revision,
        }

    def add_player(self):
        color = self.host_color if not self.players else 3 - self.host_color
        token = secrets.token_hex(24)
        self.players[token] = color
        return {"token": token, "color": color, "state": self.snapshot()}

    def call(self, action, body, token):
        if self.closed:
            raise RoomError("room_closed")
        color = self.players[token]
        if action == "join":
            return {"color": color, "state": self.snapshot()}
        if action == "leave":
            self.closed = True
            return {}
        if action == "state":
            return self.snapshot()
        if action not in ("move", "undo"):
            raise RoomError("invalid_request")
        game = self.game
        if len(self.players) != 2 or game.turn != color or game.ended:
            raise RoomError("not_turn")
        if type(body.get("revision")) is not int or body["revision"] != self.revision:
            raise RoomError("stale_move")
        if action == "undo":
            if not self.undo or len(game.history) < 2:
                raise RoomError("cannot_undo")
            game.undo(2)
        else:
            if type(body.get("ply")) is not int or body["ply"] != len(game.history):
                raise RoomError("stale_move")
            x, y = body.get("x"), body.get("y")
            if type(x) is not int or type(y) is not int or not game.play((x, y)):
                raise RoomError("occupied")
        self.revision += 1
        return self.snapshot()
