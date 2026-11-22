"""Five entry point, keyboard controls, and local persistence."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import json
from math import ceil
import os
from pathlib import Path
from shutil import which
import subprocess
from tempfile import NamedTemporaryFile
from time import monotonic

from game import BLACK, WHITE, FOULS, Game
from lan_session import LanSession
from rapfi_engine import pick_move
from rtc_peer import RtcPeer

SIZES = (15, 13)
RULES = ("free", "renju")
LEVELS = ("easy", "normal", "hard")
LANGUAGES = ("zh", "en")
COLORS = (BLACK, WHITE)
EXIT_HOLD_SECONDS = 3
ENGINE_RETRY_DELAYS = (0.5, 1, 2, 4)
DIRECTIONS = {"up": (0, -1), "f": (0, -1), "down": (0, 1), "x": (0, 1),
              "left": (-1, 0), "z": (-1, 0), "right": (1, 0), "c": (1, 0)}


@dataclass(frozen=True)
class Settings:
    size: int = 15
    rule: str = "free"
    level: str = "normal"
    language: str = "zh"
    sound: bool = True
    player_color: int = BLACK
    show_fouls: bool = False
    foul_loss: bool = False

    @property
    def bans(self):
        return FOULS if self.rule == "renju" else ()


class App:
    def __init__(self, path):
        self.path = path
        self.settings = Settings()
        self.game = None
        self.mode = "cpu"
        self.level = "normal"
        self.player_color = BLACK
        self.cursor = (7, 7)
        self.page = "home"
        self.selected = 0
        self.pending = None
        self.lan = None
        self.room_host_first = True
        self.room_rule = "free"
        self.room_undo = False
        self.room_foul_loss = False
        self.room_size = self.settings.size
        self.room_code = ""
        self.running = True
        self.escape_started = None
        self.exit_countdown = None
        self.dirty = True
        self.notice = ""
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.job = None
        self.reset_engine_retry()
        self.sound_path = Path(__file__).with_name("stone.wav")
        self.menu_sound_path = Path(__file__).with_name("menu.wav")
        self.aplay = which("aplay")
        self.sound_process = None
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (ValueError, OSError):
            self.notice = "load_error"
            return
        try:
            config = data["settings"]
            rule = config["rule"]
            if rule == "custom":
                rule = "renju" if set(config.get("custom", ())) == set(FOULS) else "free"
            settings = Settings(config["size"], rule, config["level"], config["language"],
                                config.get("sound", True), config.get("player_color", BLACK),
                                config.get("show_fouls", False), config.get("foul_loss", False))
            if (settings.size not in SIZES or settings.rule not in RULES
                    or settings.level not in LEVELS or settings.language not in LANGUAGES
                    or any(type(value) is not bool for value in
                           (settings.sound, settings.show_fouls, settings.foul_loss))
                    or type(settings.player_color) is not int or settings.player_color not in COLORS):
                raise ValueError("Invalid settings")
            self.settings = settings
            saved = data.get("game")
            if saved is None:
                return
            size, bans, mode, level = (saved[key] for key in ("size", "bans", "mode", "level"))
            player_color = saved.get("player_color", BLACK)
            if (size not in SIZES or any(ban not in FOULS for ban in bans)
                    or mode not in ("cpu", "local") or level not in LEVELS
                    or type(player_color) is not int or player_color not in COLORS):
                raise ValueError("Invalid game")
            foul_loss = saved.get("foul_loss", settings.foul_loss)
            if type(foul_loss) is not bool:
                raise ValueError("Invalid foul policy")
            game = Game(size, bans, foul_loss)
            for move in saved["moves"]:
                if (len(move) != 2 or any(type(value) is not int for value in move)
                        or not game.play(tuple(move))):
                    raise ValueError("Invalid move")
            if game.ended:
                raise ValueError("Completed game")
            if mode == "cpu" and game.bans not in (frozenset(), frozenset(FOULS)):
                mode = "local"
                self.notice = "legacy_local"
            self.game, self.mode, self.level = game, mode, level
            self.player_color = player_color
            self.cursor = game.history[-1] if game.history else (size // 2,) * 2
        except (KeyError, ValueError, TypeError, AttributeError):
            self.notice = "load_error"

    def save(self):
        saved = None
        if self.game and not self.game.ended:
            saved = {"size": self.game.size, "bans": sorted(self.game.bans),
                     "mode": self.mode, "level": self.level, "moves": self.game.history,
                     "player_color": self.player_color, "foul_loss": self.game.foul_loss}
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                    delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"settings": vars(self.settings), "game": saved}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        except OSError:
            self.notice = "save_error"
            if temporary:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def menu(self):
        if self.page == "settings":
            rows = [
                ("size", self.settings.size), ("rules", self.settings.rule),
                ("difficulty", self.settings.level),
                ("player_color", "play_black" if self.settings.player_color == BLACK else "play_white"),
                ("language", self.settings.language),
                ("sound", "on" if self.settings.sound else "off"),
                ("rules_help", ""),
            ]
            if self.settings.rule == "renju":
                rows[2:2] = [
                    ("show_fouls", "on" if self.settings.show_fouls else "off"),
                    ("foul_action", "foul_loss" if self.settings.foul_loss else "foul_block"),
                ]
            return rows
        if self.page == "confirm":
            return [("cancel", ""), ("replace", "")]
        if self.page == "lan":
            if self.lan is not None:
                return [("lan_resume", ""), ("lan_leave", ""), ("lan_help", "")]
            return [("lan_host", ""), ("lan_join", ""), ("lan_help", "")]
        if self.page == "lan_setup":
            rows = [("lan_first", "lan_host_side" if self.room_host_first else "lan_guest_side"),
                    ("rules", self.room_rule), ("size", self.room_size),
                    ("undo", "on" if self.room_undo else "off"),
                    ("lan_host", "")]
            if self.room_rule == "renju":
                rows.insert(2, ("foul_action", "foul_loss" if self.room_foul_loss else "foul_block"))
            return rows
        rows = [("cpu", ""), ("local", ""), ("lan", ""), ("settings", "")]
        if self.game and not self.game.ended:
            rows.insert(0, ("resume", ""))
        return rows

    def open(self, page):
        self.page = page
        self.selected = 0
        self.reset_engine_retry()

    def reset_engine_retry(self):
        self.engine_failures = 0
        self.engine_retry_at = 0

    def start(self, mode):
        self.game = Game(self.settings.size, self.settings.bans, self.settings.foul_loss)
        self.mode, self.level = mode, self.settings.level
        self.player_color = self.settings.player_color
        self.begin_game()

    def begin_game(self):
        self.cursor = (self.game.size // 2,) * 2
        self.open("game")
        self.save()

    def update_setting(self, row, direction):
        field, options = {
            "size": ("size", SIZES), "rules": ("rule", RULES),
            "difficulty": ("level", LEVELS), "language": ("language", LANGUAGES),
            "player_color": ("player_color", COLORS),
            "sound": ("sound", (False, True)),
            "show_fouls": ("show_fouls", (False, True)),
            "foul_action": ("foul_loss", (False, True)),
        }[row]
        index = options.index(getattr(self.settings, field))
        value = options[(index + direction) % len(options)]
        self.settings = replace(self.settings, **{field: value})
        self.save()

    def handle(self, key, repeat=False):
        if not self.running:
            return
        if key == "escape":
            if not repeat and self.escape_started is None:
                self.escape_started = monotonic()
                self.exit_countdown = EXIT_HOLD_SECONDS
                self.dirty = True
            return
        if self.escape_started is not None:
            return
        direction = DIRECTIONS.get(key)
        if repeat and not direction:
            return
        self.dirty = True
        self.notice = ""
        if not repeat and self.page not in ("game", "lan_game"):
            typing_code = self.page == "lan_input" and (key == "backspace" or key in "0123456789")
            turning_off = (self.page == "settings" and self.menu()[self.selected][0] == "sound"
                           and self.settings.sound and (key == "enter" or direction and direction[0]))
            if (direction or key == "enter" or typing_code) and not turning_off:
                self.play_sound(menu=True)
        if self.page == "rules_help":
            if key == "enter":
                self.open("settings")
            return
        if self.page == "lan_help":
            if key == "enter":
                self.open("lan")
            return
        if self.page in ("lan_input", "lan_game"):
            self.handle_lan(key, direction)
            return
        if self.page == "game":
            if key == "enter" and self.game.ended:
                self.game = Game(self.game.size, self.game.bans, self.game.foul_loss)
                self.begin_game()
            elif key == "u":
                self.undo()
            elif direction:
                self.cursor = tuple((value + step) % self.game.size
                                    for value, step in zip(self.cursor, direction))
            elif key == "enter" and not self.computer_turn:
                if self.game.play(self.cursor):
                    self.play_sound()
                    self.save()
                elif not self.game.ended:
                    self.notice = ("forbidden" if self.game.empty(self.cursor) else "occupied")
            return
        rows = self.menu()
        if direction and direction[1]:
            self.selected = (self.selected + direction[1]) % len(rows)
            return
        action = rows[self.selected][0]
        if self.page == "lan_setup":
            if key == "enter" or direction:
                if action == "lan_first":
                    self.room_host_first = not self.room_host_first
                elif action == "rules":
                    self.room_rule = "renju" if self.room_rule == "free" else "free"
                elif action == "foul_action":
                    self.room_foul_loss = not self.room_foul_loss
                elif action == "size":
                    self.room_size = 13 if self.room_size == 15 else 15
                elif action == "undo":
                    self.room_undo = not self.room_undo
                elif key == "enter":
                    self.start_lan()
            return
        if self.page == "settings":
            if action == "rules_help":
                if key == "enter":
                    self.open("rules_help")
            elif key == "enter" or direction:
                self.update_setting(action, direction[0] if direction else 1)
                if action == "sound" and self.settings.sound:
                    self.play_sound(menu=True)
            return
        if key != "enter":
            return
        if action in ("cpu", "local"):
            if self.game and not self.game.ended:
                self.pending = action
                self.open("confirm")
            else:
                self.start(action)
        elif action == "replace":
            self.start(self.pending)
        elif action == "lan_host":
            self.room_host_first, self.room_rule, self.room_undo = True, "free", False
            self.room_foul_loss = self.settings.foul_loss
            self.room_size = self.settings.size
            self.open("lan_setup")
        elif action == "lan_help":
            self.open("lan_help")
        elif action == "lan_join":
            self.room_code = ""
            self.open("lan_input")
        elif action == "lan_resume":
            self.open("lan_game")
        elif action == "lan_leave":
            self.leave_lan()
            self.open("lan")
        elif action == "lan":
            self.open("lan")
        elif action == "cancel":
            self.open("home")
        else:
            self.open("game" if action == "resume" else "settings")

    def start_lan(self):
        options = {"size": self.room_size, "renju": self.room_rule == "renju",
                   "host_first": self.room_host_first, "undo": self.room_undo,
                   "foul_loss": self.room_foul_loss}
        self.lan = LanSession(RtcPeer(options))
        self.open("lan_game")

    def handle_lan(self, key, direction):
        if self.page == "lan_input":
            if key == "backspace":
                self.room_code = self.room_code[:-1]
            elif len(key) == 1 and key in "0123456789" and len(self.room_code) < 10:
                self.room_code += key
            elif key == "enter":
                if len(self.room_code) != 10:
                    self.notice = "lan_code_hint"
                    return
                self.lan = LanSession(RtcPeer(), self.room_code)
                self.open("lan_game")
            return
        session = self.lan
        if session.closed and key == "enter":
            self.leave_lan()
            self.open("lan")
        elif direction and session.game is not None:
            self.lan_cursor = tuple((value + step) % session.game.size
                                    for value, step in zip(self.lan_cursor, direction))
        elif key == "enter":
            if session.game and session.game.ended:
                session.rematch()
            elif session.game:
                session.move(self.lan_cursor)
        elif key == "u":
            session.undo()

    def leave_lan(self):
        if self.lan is not None:
            self.lan.close()
            self.lan = None

    def cancel_escape(self):
        if self.escape_started is not None:
            self.escape_started = None
            self.exit_countdown = None
            self.dirty = True

    def release_escape(self):
        if self.escape_started is None:
            return
        self.check_exit_hold()
        self.cancel_escape()
        if self.running and self.page != "home":
            self.play_sound(menu=True)
            if self.page in ("lan_game", "lan_input", "lan_setup", "lan_help"):
                if self.lan is not None and self.lan.closed:
                    self.leave_lan()
                self.open("lan")
            else:
                self.open("settings" if self.page == "rules_help" else "home")

    def check_exit_hold(self):
        if self.escape_started is None:
            return
        remaining = EXIT_HOLD_SECONDS - (monotonic() - self.escape_started)
        if remaining <= 0:
            self.running = False
        elif self.exit_countdown != ceil(remaining):
            self.exit_countdown = ceil(remaining)
            self.dirty = True

    @property
    def computer_turn(self):
        return self.mode == "cpu" and not self.game.ended and self.game.turn != self.player_color

    def undo(self):
        if not self.game.history:
            return
        count = 1
        if self.mode == "cpu" and self.game.board[self.game.history[-1]] != self.player_color:
            count = 2
        if count > len(self.game.history):
            return
        self.cursor = self.game.history[-count]
        self.game.undo(count)
        self.reset_engine_retry()
        self.save()

    def tick(self):
        self.check_exit_hold()
        if not self.running:
            return
        if self.lan is not None:
            before = self.lan.game
            previous_round = self.lan.round_number
            if self.lan.tick():
                current = self.lan.game
                new_round = previous_round != self.lan.round_number
                if current is not None and (before is None or new_round):
                    self.lan_cursor = (current.size // 2,) * 2
                elif (before and current and len(before.history) > len(current.history)
                      and current.turn == self.lan.color):
                    self.lan_cursor = before.history[len(current.history)]
                if (self.page == "lan_game" and not new_round and before and current
                        and len(before.history) < len(current.history)):
                    self.play_sound()
                self.dirty = True
        if self.job and self.job[0].done():
            future, game, moves = self.job
            self.job = None
            if (self.page == "game" and game is self.game and moves == tuple(game.history)
                    and self.computer_turn):
                point = future.result()
                if point is not None and game.play(point):
                    self.reset_engine_retry()
                    self.dirty = True
                    self.play_sound()
                    self.save()
                else:
                    delay = ENGINE_RETRY_DELAYS[self.engine_failures]
                    self.engine_retry_at = monotonic() + delay
                    self.engine_failures = min(self.engine_failures + 1, len(ENGINE_RETRY_DELAYS) - 1)
                    self.dirty = True
        if (self.page == "game" and self.computer_turn and self.job is None
                and monotonic() >= self.engine_retry_at):
            game = self.game
            snapshot = Game(game.size, game.bans)
            snapshot.board = game.board.copy()
            snapshot.history = game.history.copy()
            self.job = (self.executor.submit(pick_move, snapshot, self.level),
                        game, tuple(game.history))

    def play_sound(self, *, menu=False):
        if not self.settings.sound:
            return
        path = self.menu_sound_path if menu else self.sound_path
        try:
            if os.name == "nt":
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME |
                                   winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            elif self.aplay:
                self.stop_sound()
                self.sound_process = subprocess.Popen(
                    [self.aplay, "-q", str(path)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError):
            pass

    def stop_sound(self):
        if self.sound_process is not None and self.sound_process.poll() is None:
            self.sound_process.kill()
            self.sound_process.wait()

    def close(self):
        self.leave_lan()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.stop_sound()


def preview(app, screen):
    import tkinter as tk
    from PIL import Image, ImageTk
    from ui import TITLE

    window = tk.Tk()
    window.title(TITLE)
    label = tk.Label(window, borderwidth=0, highlightthickness=0)
    label.pack()
    window.resizable(False, False)
    pressed = set()
    escape_release = None

    def key_down(event):
        nonlocal escape_release
        key = {"return": "enter"}.get(event.keysym.lower(), event.keysym.lower())
        if key == "escape" and escape_release is not None:
            window.after_cancel(escape_release)
            escape_release = None
        app.handle(key, key in pressed)
        pressed.add(key)

    def finish_escape_release():
        nonlocal escape_release
        escape_release = None
        pressed.discard("escape")
        app.release_escape()

    def key_up(event):
        nonlocal escape_release
        key = {"return": "enter"}.get(event.keysym.lower(), event.keysym.lower())
        if key == "escape":
            # X11 can send a release immediately before an autorepeat press.
            if escape_release is None:
                escape_release = window.after_idle(finish_escape_release)
        else:
            pressed.discard(key)

    def focus_out(event):
        nonlocal escape_release
        if escape_release is not None:
            window.after_cancel(escape_release)
            escape_release = None
        pressed.clear()
        app.cancel_escape()

    window.bind("<KeyPress>", key_down)
    window.bind("<KeyRelease>", key_up)
    window.bind("<FocusOut>", focus_out)

    def tick():
        app.tick()
        if not app.running:
            window.destroy()
            return
        if app.dirty:
            image = screen.render(app).resize((640, 340), Image.Resampling.NEAREST)
            label.image = ImageTk.PhotoImage(image)
            label.configure(image=label.image)
            app.dirty = False
        window.after(24, tick)

    tick()
    window.mainloop()


def main():
    from ui import Screen

    parser = argparse.ArgumentParser(description="Five for Cardputer Zero")
    parser.add_argument("--device", action="store_true")
    parser.add_argument("--framebuffer", default="/dev/fb0")
    parser.add_argument("--keyboard")
    parser.add_argument("--rotate", action="store_true")
    parser.add_argument("--data", type=Path, default=Path(
        os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    ) / "five" / "state.json")
    args = parser.parse_args()
    screen = Screen()
    app = App(args.data)
    try:
        if args.device:
            from device import run
            run(app, screen, args.framebuffer, args.keyboard, args.rotate)
        else:
            preview(app, screen)
    finally:
        app.close()


if __name__ == "__main__":
    main()
