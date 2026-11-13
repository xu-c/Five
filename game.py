"""Board rules and offline opponent."""

from dataclasses import dataclass
from random import choice

BLACK, WHITE = 1, 2
AXES = ((1, 0), (0, 1), (1, 1), (1, -1))
FOULS = ("three", "four", "overline")


def offset(point, axis, step):
    return point[0] + axis[0] * step, point[1] + axis[1] * step


@dataclass(frozen=True)
class Move:
    winner: int = 0
    line: tuple = ()
    foul: str = ""


class Game:
    def __init__(self, size=15, bans=()):
        self.size = size
        self.bans = frozenset(bans)
        self.board = {}
        self.history = []
        self.result = Move()

    @property
    def turn(self):
        return BLACK + len(self.history) % 2

    @property
    def ended(self):
        return bool(self.result.winner) or len(self.history) == self.size ** 2

    def inside(self, point):
        return all(0 <= coordinate < self.size for coordinate in point)

    def empty(self, point):
        return self.inside(point) and point not in self.board

    def line(self, point, axis, color):
        ends = []
        for step in (-1, 1):
            distance = step
            while self.board.get(offset(point, axis, distance)) == color:
                distance += step
            ends.append(distance)
        return tuple(offset(point, axis, i) for i in range(ends[0] + 1, ends[1]))

    def fours(self, point):
        found = set()
        for axis in AXES:
            for start in range(-4, 1):
                cells = tuple(offset(point, axis, i) for i in range(start, start + 5))
                stones = frozenset(cell for cell in cells if self.board.get(cell) == BLACK)
                if len(stones) != 4:
                    continue
                gap, = set(cells) - stones
                if not self.empty(gap):
                    continue
                if any(self.board.get(offset(point, axis, i)) == BLACK
                       for i in (start - 1, start + 5)):
                    continue
                found.add(stones)
                if len(found) >= 2:
                    return found
        return found

    def double_three(self, point):
        found = set()
        for axis in AXES:
            for start in range(-3, 1):
                cells = tuple(offset(point, axis, i) for i in range(start, start + 4))
                stones = frozenset(cell for cell in cells if self.board.get(cell) == BLACK)
                if len(stones) != 3 or stones in found:
                    continue
                gap, = set(cells) - stones
                ends = [offset(point, axis, i) for i in (start - 1, start + 4)]
                if not all(self.empty(cell) for cell in (gap, *ends)):
                    continue
                if any(self.board.get(offset(point, axis, i)) == BLACK
                       for i in (start - 2, start + 5)):
                    continue
                outcome = self.inspect(gap, BLACK)
                if not outcome.foul and not outcome.winner:
                    found.add(stones)
                    if len(found) >= 2:
                        return True
        return False

    def inspect(self, point, color):
        """Evaluate an empty intersection without changing the position."""
        self.board[point] = color
        try:
            lines = [self.line(point, axis, color) for axis in AXES]
            longest = max(lines, key=len)
            if color == WHITE or "overline" not in self.bans:
                if len(longest) >= 5:
                    return Move(color, longest)
            else:
                for line in lines:
                    if len(line) == 5:
                        return Move(color, line)
                if len(longest) > 5:
                    return Move(foul="overline")
            if color == BLACK and self.bans:
                if "four" in self.bans and len(self.fours(point)) >= 2:
                    return Move(foul="four")
                if "three" in self.bans and self.double_three(point):
                    return Move(foul="three")
            return Move()
        finally:
            del self.board[point]

    def play(self, point):
        if self.ended or not self.empty(point):
            return False
        outcome = self.inspect(point, self.turn)
        self.board[point] = self.turn
        self.history.append(point)
        self.result = Move(WHITE, foul=outcome.foul) if outcome.foul else outcome
        return True

    def undo(self, count=1):
        for _ in range(min(count, len(self.history))):
            del self.board[self.history.pop()]
        self.result = Move()

    def candidates(self):
        if not self.board:
            return [(self.size // 2, self.size // 2)]
        nearby = {
            (x + dx, y + dy)
            for x, y in self.board
            for dx in range(-2, 3)
            for dy in range(-2, 3)
            if self.empty((x + dx, y + dy))
        }
        return sorted(nearby)


def potential(game, point, color):
    game.board[point] = color
    try:
        score = 0
        for axis in AXES:
            line = game.line(point, axis, color)
            openings = (game.empty(offset(line[0], axis, -1))
                        + game.empty(offset(line[-1], axis, 1)))
            if openings:
                score += (0, 2, 12, 75, 700, 4000)[min(len(line), 5)] * openings ** 2
        return score
    finally:
        del game.board[point]


def choose_move(game, level):
    color = game.turn
    other = BLACK + WHITE - color
    moves = []
    for point in game.candidates():
        own = game.inspect(point, color)
        if own.foul:
            continue
        if own.winner:
            return point
        threat = game.inspect(point, other)
        score = 8000 if threat.winner else 0
        score += potential(game, point, color)
        if not threat.foul:
            score += potential(game, point, other)
        moves.append((score, point))
    if not moves:
        for x in range(game.size):
            for y in range(game.size):
                point = (x, y)
                if game.empty(point) and not game.inspect(point, color).foul:
                    return point
        return next(iter(game.candidates()), None)
    moves.sort(reverse=True)
    if level == "easy" and moves[0][0] < 8000:
        return choice(moves[:5])[1]
    if level != "hard":
        return moves[0][1]
    return max(moves[:8], key=lambda move: hard_score(game, color, other, *move))[1]


def hard_score(game, color, other, score, point):
    game.board[point] = color
    try:
        threats = 0
        reply = 0
        for target in game.candidates():
            if game.inspect(target, other).winner:
                return -100000 + score
            if game.inspect(target, color).winner:
                threats += 1
            reply = max(reply, potential(game, target, other))
        return score + 11000 * threats - reply
    finally:
        del game.board[point]
