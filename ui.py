"""Shared 320 × 170 renderer."""

from functools import lru_cache
from math import sin, sqrt
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from game import BLACK

SIZE = (320, 170)
TITLE = "Five"
BG, PANEL, TEXT = "#141c20", "#243136", "#faf4e9"
MUTED, ACCENT = "#b6c4c2", "#a7e7ca"
WOOD, GRID = "#d8af75", "#78542f"

LABELS = {
    "cpu": ("离线人机", "Play computer"), "local": ("同机双人", "Two players"),
    "resume": ("继续对局", "Resume game"), "settings": ("设置", "Settings"),
    "size": ("棋盘", "Board size"), "rules": ("规则", "Rules"),
    "free": ("自由", "Freestyle"), "renju": ("连珠禁手", "Renju fouls"),
    "custom": ("自定义", "Custom"), "difficulty": ("人机难度", "Difficulty"),
    "easy": ("简单", "Easy"), "normal": ("普通", "Normal"), "hard": ("困难", "Hard"),
    "language": ("语言", "Language"), "zh": ("简体中文", "简体中文"), "en": ("English", "English"),
    "three": ("三三", "Double three"), "four": ("四四", "Double four"),
    "overline": ("长连", "Overline"), "on": ("开", "On"), "off": ("关", "Off"),
    "sound": ("落子音效", "Move sound"),
    "rules_help": ("规则说明", "Rules guide"),
    "legacy_local": ("旧自定义棋局可用双人模式续下", "Resume old custom game in two-player mode"),
    "player_color": ("人机执棋", "Play as"),
    "play_black": ("执黑", "Black"), "play_white": ("执白", "White"),
    "black_turn": ("黑棋落子", "Black to move"), "white_turn": ("白棋落子", "White to move"),
    "your_black": ("你执黑，请落子", "Your turn (Black)"),
    "your_white": ("你执白，请落子", "Your turn (White)"),
    "black_win": ("黑棋胜", "Black wins"), "white_win": ("白棋胜", "White wins"),
    "cpu_black": ("电脑执黑，思考中", "Black CPU thinking"),
    "cpu_white": ("电脑执白，思考中", "White CPU thinking"), "draw": ("和棋", "Draw"),
    "move_number": ("第 {} 手", "Move {}"), "foul": ("黑棋禁手", "Black foul"),
    "occupied": ("这里已有棋子", "Point occupied"),
    "save_error": ("无法保存", "Could not save"), "load_error": ("无法读取存档", "Could not load save"),
    "replace_title": ("替换上次对局？", "Replace saved game?"),
    "cancel": ("取消", "Cancel"), "replace": ("开始新局", "Start new game"),
    "choose": ("选择", "Select"), "change": ("修改", "Change"), "back": ("返回", "Back"),
    "place": ("落子", "Place"), "undo": ("悔棋", "Undo"), "menu": ("菜单", "Menu"),
    "hold_exit": ("长按 Esc 3 秒退出", "Hold Esc 3s to quit"),
    "exit_countdown": ("继续按住 Esc · {} 秒后退出", "Keep holding Esc · {}s to quit"),
}


def label(key, language):
    if isinstance(key, int):
        return f"{key} × {key}"
    return LABELS[key][language == "en"]


def board(draw, rect, size, stones, cursor=None, last=None, winning=(), foul=False,
          *, gameplay=False):
    left, top, right, bottom = rect
    draw.rounded_rectangle(rect, radius=5 if gameplay else 9, fill=WOOD)
    margin = 5 if gameplay else 10
    step = (min(right - left, bottom - top) - 2 * margin) // (size - 1)
    span = step * (size - 1)
    x0, y0 = (left + right - span) // 2, (top + bottom - span) // 2

    def pixel(point):
        return x0 + point[0] * step, y0 + point[1] * step

    for i in range(size):
        x, y = pixel((i, i))
        draw.line((x, y0, x, y0 + span), fill=GRID)
        draw.line((x0, y, x0 + span, y), fill=GRID)
    center = size // 2
    for point in ((center, center), (3, 3), (3, size - 4), (size - 4, 3), (size - 4, size - 4)):
        x, y = pixel(point)
        draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=GRID)
    radius = (step - 3) // 2 if gameplay else max(2, (step - 2) // 2)
    for point, color in stones.items():
        x, y = pixel(point)
        fill = "#16191b" if color == BLACK else "#fffdf7"
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=fill, outline="#4f3623" if color != BLACK else fill)
        if point in winning:
            draw.point((x, y), fill="#e98743")
    if winning:
        draw.line((*pixel(winning[0]), *pixel(winning[-1])), fill="#e98743")
    if last:
        x, y = pixel(last)
        draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill="#e26047" if foul else "#4db99d")
    if cursor is not None:
        x, y = pixel(cursor)
        r = radius + 2 if gameplay else radius + 1
        for dx in (-1, 1):
            for dy in (-1, 1):
                corner = (x + dx * (r - 3), y + dy * r, x + dx * r, y + dy * r,
                          x + dx * r, y + dy * (r - 3))
                draw.line(corner, fill="#134d3d", width=2)


def icon():
    image = Image.new("RGBA", (256, 256))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((3, 8, 252, 252), radius=34, fill="#583419")
    mask = Image.new("L", image.size)
    ImageDraw.Draw(mask).rounded_rectangle((3, 3, 252, 240), radius=34, fill=255)
    wood = Image.new("RGB", image.size)
    wood.putdata([
        (222 + grain, 175 + grain, 117 + grain)
        for y in range(256) for x in range(256)
        for grain in (int(8 * sin(y * .13 + 1.2 * sin(x * .018))
                          + 3 * sin(y * .55 + sin(x * .031)) + 6 - x / 32),)
    ])
    image.paste(wood, mask=mask)
    for coordinate in range(35, 216, 30):
        draw.line((coordinate, 32, coordinate, 212), fill="#825630", width=2)
    for coordinate in range(32, 213, 30):
        draw.line((35, coordinate, 215, coordinate), fill="#825630", width=2)
    # Nine legal alternating moves, ending on Black's diagonal five.
    moves = ((1, 1), (1, 3), (2, 2), (4, 2), (3, 3), (2, 5), (4, 4), (5, 3), (5, 5))
    radius = 12
    for index, (column, row) in enumerate(moves):
        x, y = 35 + 30 * column, 32 + 30 * row
        draw.ellipse((x - radius + 2, y - radius + 4, x + radius + 2, y + radius + 4),
                     fill="#916039")
        base = (26, 25, 24) if index % 2 == 0 else (216, 211, 199)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                distance = (dx * dx + dy * dy) / radius ** 2
                if distance <= 1:
                    light = (sqrt(1 - distance) - (dx + dy) / (2.5 * radius)) * 29
                    draw.point((x + dx, y + dy),
                               fill=tuple(max(0, min(255, int(value + light))) for value in base))
    return image.resize((128, 128), Image.Resampling.LANCZOS)


class Screen:
    def __init__(self):
        fonts = (os.environ.get("FIVE_FONT"), "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "C:/Windows/Fonts/msyh.ttc", "/System/Library/Fonts/PingFang.ttc")
        self.font_path = next((path for path in fonts if path and Path(path).is_file()), None)
        if not self.font_path:
            raise OSError("Five needs a CJK font. Install fonts-noto-cjk or set FIVE_FONT.")

    @lru_cache(maxsize=8)
    def font(self, size):
        return ImageFont.truetype(self.font_path, size, index=2 if "NotoSansCJK-Regular.ttc" in self.font_path else 0)

    def render(self, app):
        image = Image.new("RGB", SIZE, BG)
        draw = ImageDraw.Draw(image)
        lang = app.settings.language

        def tr(key):
            return label(key, lang)

        def text(x, y, value, size=12, color=TEXT, anchor="lt"):
            draw.text((x, y), value, fill=color, font=self.font(size), anchor=anchor)

        countdown = app.exit_countdown
        if countdown is not None:
            exit_message = tr("exit_countdown").format(countdown)

        if app.page == "game":
            game = app.game
            last = game.history[-1] if game.history else None
            board(draw, (1, 1, 168, 168), game.size, game.board,
                  None if game.ended else app.cursor, last, game.result.line,
                  bool(game.result.foul), gameplay=True)
            text(177, 10, TITLE, 21)
            text(177, 37, tr(app.mode) + "  ·  " + (
                tr(app.level) if app.mode == "cpu" else tr(game.size)), 11, MUTED)
            color = game.result.winner if game.ended else game.turn
            if game.ended:
                status = {0: "draw", 1: "black_win", 2: "white_win"}[game.result.winner]
            elif app.computer_turn:
                status = "cpu_black" if color == BLACK else "cpu_white"
            elif app.mode == "cpu":
                status = "your_black" if color == BLACK else "your_white"
            else:
                status = "black_turn" if game.turn == BLACK else "white_turn"
            draw.rounded_rectangle((174, 54, 315, 84), radius=6, fill=PANEL, outline="#496561")
            if color:
                draw.ellipse((181, 63, 193, 75), fill="#14191c" if color == BLACK else "#fff9ee",
                             outline="#d6e7df")
            status_size = 12 if lang == "en" and app.mode == "cpu" and not game.ended else 14
            text(200 if color else 182, 69, tr(status), status_size, ACCENT, "lm")
            if game.result.foul:
                details = tr(game.result.foul) if lang == "en" else tr("foul") + " · " + tr(game.result.foul)
            elif app.notice:
                details = tr(app.notice)
            else:
                x, y = app.cursor
                details = tr("move_number").format(len(game.history) + (not game.ended))
                if not game.ended:
                    details += f"   {chr(65 + x)}{y + 1}"
            if app.engine_failures:
                error, retry = (("引擎故障", "正在自动重试") if lang == "zh"
                                else ("Engine error", "Retrying automatically"))
                text(177, 88, error, 11, MUTED)
                text(177, 106, retry, 11, TEXT)
            else:
                text(177, 88, details, 11, MUTED)
                text(177, 111, "↑↓←→  /  F X Z C", 11, MUTED)
            text(177, 129, "Enter  " + tr("place") + "     U  " + tr("undo"), 11)
            if countdown is not None:
                draw.rectangle((5, 139, 315, 164), fill=PANEL)
                text(160, 151, exit_message, 12, ACCENT, "mm")
            else:
                text(177, 147, "Esc  " + tr("menu"), 11)
            return image

        if app.page == "rules_help":
            text(14, 7, tr("rules_help"), 18)
            text(14, 32, tr("free"), 13, ACCENT)
            text(14, 50, "黑白连成五颗或更多即胜。" if lang == "zh"
                 else "Either side wins with five or more in a row.")
            text(14, 73, tr("renju"), 13, ACCENT)
            if lang == "zh":
                lines = ("黑棋恰好五连获胜，白棋五连或更长即胜。",
                         "黑棋三三、四四或长连，判白胜。恰好五连优先。",
                         "人机和双人都可选这两套规则。")
            else:
                lines = ("Black wins with exactly five. White wins with five or more.",
                         "Black loses on double three, double four or overline",
                         "unless the move also makes exactly five.",
                         "Both rules are available in either play mode.")
            for y, line in zip((89, 104, 119, 134), lines):
                text(14, y, line, 10 if lang == "en" else 12)
            text(14, 151, exit_message if countdown is not None else "Esc / Enter  " + tr("back"),
                 11, ACCENT if countdown is not None else MUTED)
            return image

        if app.page == "home":
            text(14, 10, TITLE, 23)
            board(draw, (190, 15, 305, 129), 9,
                  {(2, 6): 1, (3, 5): 1, (4, 4): 1, (5, 3): 1, (6, 2): 1,
                   (3, 6): 2, (4, 5): 2, (5, 4): 2, (4, 3): 2}, last=(6, 2))
            left, right, top, height = 14, 173, 38, 20
        elif app.page == "settings":
            text(14, 7, tr("settings"), 18)
            left, right, top, height = 14, 305, 27, 13
        else:
            text(14, 13, tr("replace_title"), 19)
            left, right, top, height = 14, 305, 48, 24

        for index, (key, value) in enumerate(app.menu()):
            y = top + index * height
            active = index == app.selected
            if active:
                draw.rounded_rectangle((left, y, right, y + height - 1), radius=4, fill=PANEL)
                draw.line((left + 2, y + 4, left + 2, y + height - 5), fill=ACCENT, width=2)
            text(left + 9, y + (height - 12) // 2, tr(key), 12, ACCENT if active else TEXT)
            if value:
                text(right - 9, y + (height - 12) // 2, tr(value), 12, MUTED, "rt")

        footer = ("↑↓ / F X    ←→ / Z C  " + tr("change") + "    Esc  " + tr("back")
                  if app.page == "settings" else "Enter  " + tr("choose") + "     " + tr("hold_exit"))
        if countdown is not None:
            text(14, 152, exit_message, 11, ACCENT)
            return image
        text(14, 151, tr(app.notice) if app.notice else footer, 11, MUTED)
        return image
