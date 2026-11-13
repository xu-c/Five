"""Run Rapfi as a separate process using the Gomocup text protocol."""

import logging
import os
from pathlib import Path
from queue import Empty, Queue
import re
import subprocess
from threading import Thread
from time import monotonic

ENGINE = Path(os.environ.get("FIVE_RAPFI") or Path(__file__).resolve().with_name("rapfi")).resolve()
LIMITS = {"easy": (25, 120, 2), "normal": (65, 350, 6), "hard": (100, 1000, 16)}
COORDINATE = re.compile(r"(\d+),(\d+)")
LOG = logging.getLogger(__name__)


def pick_move(game, level):
    try:
        move = rapfi_move(game, level)
        if game.empty(move) and not game.inspect(move, game.turn).foul:
            return move
        LOG.warning("Rapfi returned an illegal move: %s", move)
    except (OSError, TimeoutError, ValueError) as error:
        LOG.warning("Rapfi could not return a move: %s", error)
    return None


def rapfi_move(game, level):
    strength, time_ms, depth = LIMITS[level]
    lines = [
        f"START {game.size}", f"INFO RULE {4 if game.bans else 0}",
        "INFO THREAD_NUM 1", "INFO PONDERING 0", "INFO MAX_MEMORY 33554432",
        f"INFO STRENGTH {strength}", f"INFO TIMEOUT_TURN {time_ms}", f"INFO MAX_DEPTH {depth}",
    ]
    if game.history:
        lines.append("BOARD")
        for x, y in game.history:
            side = 1 if game.board[x, y] == game.turn else 2
            lines.append(f"{x},{y},{side}")
        lines.append("DONE")
    else:
        lines.append("BEGIN")

    with subprocess.Popen(
        [str(ENGINE), "--config", str(ENGINE.with_name("config.toml"))],
        cwd=ENGINE.parent, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        errors="replace",
    ) as process:
        replies = Queue()

        def read_reply():
            for line in process.stdout:
                line = line.strip()
                if COORDINATE.fullmatch(line) or line.startswith("ERROR"):
                    replies.put(line)
                    return
            replies.put("")

        reader = Thread(target=read_reply, daemon=True)
        reader.start()
        try:
            deadline = monotonic() + 2 + time_ms / 1000
            process.stdin.write("\n".join(lines) + "\n")
            process.stdin.flush()
            try:
                reply = replies.get(timeout=max(0, deadline - monotonic()))
            except Empty:
                raise TimeoutError("engine response deadline exceeded") from None
            match = COORDINATE.fullmatch(reply)
            if not match:
                raise ValueError(reply or "engine exited before returning a move")
            return int(match[1]), int(match[2])
        finally:
            if process.poll() is None:
                process.kill()
            reader.join()
