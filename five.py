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

from game import BLACK, WHITE, FOULS, Game, choose_move

SIZES = (15, 13)
RULES = ("free", "renju", "custom")
LEVELS = ("easy", "normal", "hard")
LANGUAGES = ("zh", "en")
COLORS = (BLACK, WHITE)
EXIT_HOLD_SECONDS = 3
DIRECTIONS = {"up": (0, -1), "f": (0, -1), "down": (0, 1), "x": (0, 1),
              "left": (-1, 0), "z": (-1, 0), "right": (1, 0), "c": (1, 0)}


@dataclass(frozen=True)
class Settings:
    size: int = 15
    rule: str = "free"
    level: str = "normal"
    language: str = "zh"
    custom: tuple = ()
    sound: bool = True
    player_color: int = BLACK

    @property
    def bans(self):
        return {"free": (), "renju": FOULS, "custom": self.custom}[self.rule]


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
        self.running = True
        self.escape_started = None
        self.exit_countdown = None
        self.dirty = True
        self.notice = ""
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.job = None
        self.sound_path = Path(__file__).with_name("stone.wav")
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
            settings = Settings(config["size"], config["rule"], config["level"],
                                config["language"], tuple(config["custom"]),
                                config.get("sound", True), config.get("player_color", BLACK))
            if (settings.size not in SIZES or settings.rule not in RULES
                    or settings.level not in LEVELS or settings.language not in LANGUAGES
                    or any(ban not in FOULS for ban in settings.custom)
                    or type(settings.sound) is not bool
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
            game = Game(size, bans)
            for move in saved["moves"]:
                if (len(move) != 2 or any(type(value) is not int for value in move)
                        or not game.play(tuple(move))):
                    raise ValueError("Invalid move")
            if game.ended:
                raise ValueError("Completed game")
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
                     "player_color": self.player_color}
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
            ]
            if self.settings.rule == "custom":
                rows[2:2] = [(ban, "on" if ban in self.settings.custom else "off")
                             for ban in FOULS]
            return rows
        if self.page == "confirm":
            return [("cancel", ""), ("replace", "")]
        rows = [("cpu", ""), ("local", ""), ("settings", "")]
        if self.game and not self.game.ended:
            rows.insert(0, ("resume", ""))
        return rows

    def open(self, page):
        self.page = page
        self.selected = 0

    def start(self, mode):
        self.game = Game(self.settings.size, self.settings.bans)
        self.mode, self.level = mode, self.settings.level
        self.player_color = self.settings.player_color
        self.cursor = (self.game.size // 2,) * 2
        self.open("game")
        self.save()

    def update_setting(self, row, direction):
        field, options = {
            "size": ("size", SIZES), "rules": ("rule", RULES),
            "difficulty": ("level", LEVELS), "language": ("language", LANGUAGES),
            "player_color": ("player_color", COLORS),
            "sound": ("sound", (False, True)),
        }.get(row, ("custom", ()))
        if options:
            index = options.index(getattr(self.settings, field))
            value = options[(index + direction) % len(options)]
        else:
            value = tuple(sorted(set(self.settings.custom) ^ {row}))
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
        if self.page == "game":
            if key == "u":
                self.undo()
            elif direction:
                self.cursor = tuple(max(0, min(self.game.size - 1, value + step))
                                    for value, step in zip(self.cursor, direction))
            elif key == "enter" and not self.computer_turn:
                if self.game.play(self.cursor):
                    self.play_sound()
                    self.save()
                elif not self.game.ended:
                    self.notice = "occupied"
            return
        rows = self.menu()
        if direction and direction[1]:
            self.selected = (self.selected + direction[1]) % len(rows)
            return
        action = rows[self.selected][0]
        if self.page == "settings":
            if key == "enter" or direction:
                self.update_setting(action, direction[0] if direction else 1)
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
        elif action == "cancel":
            self.open("home")
        else:
            self.open("game" if action == "resume" else "settings")

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
            self.open("home")

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
        self.save()

    def tick(self):
        self.check_exit_hold()
        if not self.running:
            return
        if self.job and self.job[0].done():
            future, game, moves = self.job
            self.job = None
            if (self.page == "game" and game is self.game and moves == tuple(game.history)
                    and self.computer_turn):
                point = future.result()
                if point is not None and game.play(point):
                    self.dirty = True
                    self.play_sound()
                    self.save()
        if self.page == "game" and self.computer_turn and self.job is None:
            game = self.game
            snapshot = Game(game.size, game.bans)
            snapshot.board = game.board.copy()
            snapshot.history = game.history.copy()
            self.job = (self.executor.submit(choose_move, snapshot, self.level),
                        game, tuple(game.history))

    def play_sound(self):
        if not self.settings.sound:
            return
        try:
            if os.name == "nt":
                import winsound
                winsound.PlaySound(str(self.sound_path), winsound.SND_FILENAME |
                                   winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            elif self.aplay:
                self.stop_sound()
                self.sound_process = subprocess.Popen(
                    [self.aplay, "-q", str(self.sound_path)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError):
            pass

    def stop_sound(self):
        if self.sound_process is not None and self.sound_process.poll() is None:
            self.sound_process.kill()
            self.sound_process.wait()

    def close(self):
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
