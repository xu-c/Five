"""Keep Zero's LAN traffic off the display and keyboard loop."""

from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from game import FOULS, Game
from lan import RoomError


class LanSession:
    def __init__(self, transport, code=None):
        self.code = code
        self.transport = transport
        self.hosting = code is None
        self.token = None
        self.color = 0
        self.game = None
        self.ready = False
        self.allow_undo = False
        self.revision = 0
        self.error = ""
        self.disconnected = False
        self.closed = False
        self.next_poll = 0
        self.pending_action = None
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.action = "create" if self.hosting else "join"
        self.job = self.worker.submit(self.transport, self.action, code=code)

    @property
    def can_play(self):
        return (self.ready and not self.closed and not self.disconnected
                and self.pending_action is None and (self.job is None or self.action == "state")
                and not self.game.ended and self.game.turn == self.color)

    def move(self, point):
        if self.can_play:
            self.pending_action = ("move", self.revision, {"x": point[0], "y": point[1],
                                                          "ply": len(self.game.history)})

    def undo(self):
        if self.can_play and self.allow_undo and len(self.game.history) >= 2:
            self.pending_action = ("undo", self.revision, {})

    def tick(self):
        changed = False
        if self.job is not None and self.job.done():
            job, action = self.job, self.action
            self.job = None
            was_disconnected = self.disconnected
            starting = action in ("create", "join")
            try:
                state = job.result()
                if starting:
                    token, color = state["token"], state["color"]
                    self.code = state.get("code", self.code)
                    state = state["state"]
                size, renju, moves = state["size"], state["renju"], state["moves"]
                if size not in (13, 15) or type(renju) is not bool or len(moves) > size * size:
                    raise ValueError("Invalid room settings")
                history = [tuple(point) for point in moves]
                game = self.game
                if game is None or game.history != history:
                    game = Game(size, FOULS if renju else ())
                    for point in history:
                        if (len(point) != 2 or any(type(value) is not int for value in point)
                                or not game.play(point)):
                            raise ValueError("Invalid room history")
                if starting:
                    self.token, self.color = token, color
                changed = (self.game is None or self.game.history != game.history
                           or self.ready != state["ready"] or was_disconnected)
                if action in ("move", "undo") or self.game and self.game.history != game.history:
                    self.error = ""
                self.game, self.ready = game, state["ready"]
                self.revision = state.get("revision", len(history))
                self.allow_undo = state.get("undo", False)
                self.disconnected = False
                self.next_poll = monotonic() + .35
            except RoomError as error:
                self.error = error.code
                self.closed = starting or error.code in ("room_closed", "pair_expired", "pair_failed")
                self.next_poll = monotonic()
                changed = True
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                self.disconnected = True
                if starting:
                    self.error = "connection_error"
                    self.closed = True
                self.next_poll = monotonic() + 1
                changed = not was_disconnected
        if self.token and not self.closed and self.job is None:
            if self.pending_action is not None:
                action, revision, body = self.pending_action
                self.pending_action = None
                if self.can_play and revision == self.revision:
                    self.action = action
                    self.job = self.worker.submit(self.transport, action, token=self.token,
                                                  revision=revision, **body)
            if self.job is None and monotonic() >= self.next_poll:
                self.action = "state"
                self.job = self.worker.submit(self.transport, "state", token=self.token)
        return changed

    def close(self):
        self.closed = True
        token, starting = self.token, self.job if self.action in ("create", "join") else None

        def leave():
            try:
                seat = token or (starting.result()["token"] if starting else None)
                if seat:
                    self.transport("leave", token=seat)
            except (OSError, ValueError, RoomError, KeyError, TypeError):
                pass
            finally:
                self.transport.close()

        self.worker.submit(leave)
        self.worker.shutdown(wait=False)
