"""贪吃蛇 · Neon Snake

一个用 pygame 编写的霓虹风贪吃蛇小游戏。
首次运行如果缺少 pygame，会自动通过当前 Python 的 pip 安装。
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
from array import array
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Iterable

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

PROJECT_DIR = Path(__file__).resolve().parent
BEST_SCORE_FILE = PROJECT_DIR / "highscore.json"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"


def _install_pygame() -> None:
    """使用当前解释器对应的 pip 安装依赖。"""
    print("未检测到 pygame，正在为当前环境安装依赖...")
    command = [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)]
    if not REQUIREMENTS_FILE.exists():
        command = [sys.executable, "-m", "pip", "install", "pygame>=2.6,<3"]
    try:
        subprocess.check_call(command)
    except (OSError, subprocess.CalledProcessError) as exc:
        print("\n依赖安装失败。请确认已执行 `conda activate py313` 并且网络可用。")
        print(f"也可以手动运行：{sys.executable} -m pip install pygame")
        raise SystemExit(1) from exc
    print("依赖安装完成，正在启动游戏...\n")


try:
    import pygame
except ModuleNotFoundError as exc:
    if exc.name != "pygame":
        raise
    _install_pygame()
    import pygame


# ---------------------------------------------------------------------------
# 基础配置
# ---------------------------------------------------------------------------

WINDOW_W, WINDOW_H = 960, 760
FPS = 60
CELL = 32
COLS, ROWS = 26, 18
BOARD_W, BOARD_H = COLS * CELL, ROWS * CELL
BOARD_X = (WINDOW_W - BOARD_W) // 2
BOARD_Y = 130

START_STEP = 0.145
MIN_STEP = 0.066
FOOD_SCORE = 10

BG_TOP = (5, 10, 19)
BG_BOTTOM = (9, 17, 29)
BOARD_BG = (9, 16, 29)
BOARD_GRID = (70, 104, 124)
PANEL_BG = (12, 22, 36)
PANEL_BORDER = (38, 61, 78)
TEXT = (236, 245, 247)
MUTED = (132, 155, 169)
FAINT = (75, 96, 113)
ACCENT = (98, 240, 169)
ACCENT_BRIGHT = (142, 255, 199)
ACCENT_DIM = (53, 161, 118)
CYAN = (102, 218, 255)
GOLD = (255, 205, 105)
RED = (255, 101, 119)
DARK_TEXT = (4, 28, 19)
HEAD_GREEN = (135, 255, 190)
BODY_GREEN = (64, 224, 145)
TAIL_GREEN = (29, 143, 108)

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
KEY_DIRECTIONS = {
    pygame.K_UP: UP,
    pygame.K_w: UP,
    pygame.K_DOWN: DOWN,
    pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT,
    pygame.K_a: LEFT,
    pygame.K_RIGHT: RIGHT,
    pygame.K_d: RIGHT,
}

MENU_CARD = pygame.Rect(180, 213, 600, 410)
PAUSE_CARD = pygame.Rect(230, 268, 500, 300)
GAME_OVER_CARD = pygame.Rect(210, 218, 540, 400)


class GameState(Enum):
    MENU = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    kind: str = "primary"


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    radius: float
    color: tuple[int, int, int]
    gravity: float = 0.0


@dataclass
class FloatingText:
    x: float
    y: float
    text: str
    life: float
    max_life: float
    color: tuple[int, int, int]


@dataclass
class Mote:
    x: float
    y: float
    radius: float
    speed: float
    phase: float
    color: tuple[int, int, int]
    alpha: int


# ---------------------------------------------------------------------------
# 通用绘制工具
# ---------------------------------------------------------------------------


def mix_color(
    first: tuple[int, int, int], second: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return (
        int(first[0] + (second[0] - first[0]) * amount),
        int(first[1] + (second[1] - first[1]) * amount),
        int(first[2] + (second[2] - first[2]) * amount),
    )


def ease_out_cubic(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 3


def score_text(value: int) -> str:
    return f"{value:03d}" if value < 1000 else str(value)


def draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    pos: tuple[float, float],
    anchor: str = "topleft",
    alpha: int = 255,
) -> pygame.Rect:
    image = font.render(text, True, color)
    if alpha < 255:
        image.set_alpha(max(0, alpha))
    rect = image.get_rect()
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    surface.blit(image, rect)
    return rect


def draw_tracked_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center_x: float,
    top_y: float,
    spacing: float = 4.0,
) -> pygame.Rect:
    images = [font.render(char, True, color) for char in text]
    total_width = sum(image.get_width() for image in images) + spacing * max(
        0, len(images) - 1
    )
    x = center_x - total_width / 2
    top = int(top_y)
    max_height = 0
    for image in images:
        surface.blit(image, (int(x), top))
        x += image.get_width() + spacing
        max_height = max(max_height, image.get_height())
    return pygame.Rect(int(center_x - total_width / 2), top, int(total_width), max_height)


def draw_inline(
    surface: pygame.Surface,
    segments: Iterable[tuple[str, tuple[int, int, int]]],
    font: pygame.font.Font,
    center_x: float,
    top_y: float,
    gap: int = 10,
) -> None:
    rendered = [(font.render(text, True, color), color) for text, color in segments]
    total = sum(image.get_width() for image, _ in rendered) + gap * max(
        0, len(rendered) - 1
    )
    x = center_x - total / 2
    for image, _ in rendered:
        surface.blit(image, (int(x), int(top_y)))
        x += image.get_width() + gap


def draw_keycap(
    surface: pygame.Surface,
    label: str,
    font: pygame.font.Font,
    x: int,
    y: int,
    height: int = 22,
) -> int:
    image = font.render(label, True, TEXT)
    width = image.get_width() + 14
    rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, (17, 29, 44), rect, border_radius=5)
    pygame.draw.rect(surface, (47, 70, 88), rect, width=1, border_radius=5)
    surface.blit(image, image.get_rect(center=rect.center))
    return width


def draw_soft_glow(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    spread: int = 12,
    strength: int = 46,
    radius: int = 14,
) -> None:
    padding = spread + 4
    glow = pygame.Surface(
        (rect.width + padding * 2, rect.height + padding * 2), pygame.SRCALPHA
    )
    for offset in range(spread, 0, -2):
        alpha = max(1, int(strength * (1 - offset / spread) ** 1.6))
        glow_rect = pygame.Rect(
            padding - offset,
            padding - offset,
            rect.width + offset * 2,
            rect.height + offset * 2,
        )
        pygame.draw.rect(
            glow,
            (*color, alpha),
            glow_rect,
            width=2,
            border_radius=radius + offset,
        )
    surface.blit(glow, (rect.x - padding, rect.y - padding))


# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------


class FontBook:
    # 在 Windows 上优先直接读取字体文件。部分 pygame 版本在 Python 3.13
    # 下枚举系统字体时会因为注册表数据异常而崩溃，这样可绕开该问题。
    CJK_FILES = (
        "msyh.ttc",
        "msyh.ttf",
        "simhei.ttf",
        "Deng.ttf",
        "simsun.ttc",
        "NotoSansCJK-Regular.ttc",
    )
    CJK_NAMES = (
        "microsoftyaheiui",
        "microsoftyahei",
        "simhei",
        "notosanscjksc",
        "sourcehansanssc",
        "simsun",
        "arial",
    )
    DISPLAY_FILES = ("bahnschrift.ttf", "segoeui.ttf", "arial.ttf")
    DISPLAY_NAMES = ("bahnschrift", "segoeui", "trebuchetms", "arial")

    def __init__(self) -> None:
        cjk_path = self._find_file(self.CJK_FILES)
        display_path = self._find_file(self.DISPLAY_FILES)
        if cjk_path is None:
            cjk_path = self._find_named(self.CJK_NAMES)
        if display_path is None:
            display_path = self._find_named(self.DISPLAY_NAMES)
        self.cjk_path = cjk_path
        self.display_path = display_path or cjk_path
        self._cache: dict[tuple[int, bool, bool], pygame.font.Font] = {}

    @staticmethod
    def _font_directories() -> list[Path]:
        directories = []
        windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
        if windir:
            directories.append(Path(windir) / "Fonts")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            directories.append(Path(local_app_data) / "Microsoft" / "Windows" / "Fonts")
        directories.extend(
            [
                Path("/usr/share/fonts/truetype/dejavu"),
                Path("/usr/share/fonts/truetype/noto"),
                Path("/Library/Fonts"),
                Path("/System/Library/Fonts"),
            ]
        )
        return directories

    @classmethod
    def _find_file(cls, filenames: Iterable[str]) -> str | None:
        for directory in cls._font_directories():
            for filename in filenames:
                candidate = directory / filename
                try:
                    if candidate.is_file():
                        return str(candidate)
                except OSError:
                    continue
        return None

    @staticmethod
    def _find_named(names: Iterable[str]) -> str | None:
        for name in names:
            try:
                path = pygame.font.match_font(name)
            except Exception:
                # pygame 2.6.1 在部分 Windows + Python 3.13 环境会失败。
                return None
            if path:
                return path
        return None

    def get(
        self, size: int, *, bold: bool = False, display: bool = False
    ) -> pygame.font.Font:
        key = (size, bold, display)
        if key not in self._cache:
            path = self.display_path if display else self.cjk_path
            font = pygame.font.Font(path, size)
            font.set_bold(bold)
            self._cache[key] = font
        return self._cache[key]


# ---------------------------------------------------------------------------
# 音效
# ---------------------------------------------------------------------------


class SoundBank:
    """用标准库合成简短音效，不额外依赖音频文件。"""

    def __init__(self) -> None:
        self.muted = False
        self.available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        if pygame.mixer.get_init() is None:
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            except pygame.error:
                return
        try:
            self.sounds = {
                "eat": self._sequence([(740, 0.045), (988, 0.08)], 0.20),
                "start": self._sequence([(392, 0.055), (523, 0.055), (659, 0.11)], 0.16),
                "pause": self._sequence([(440, 0.045)], 0.11),
                "resume": self._sequence([(523, 0.045), (659, 0.065)], 0.12),
                "click": self._sequence([(560, 0.035)], 0.08),
                "game_over": self._sequence(
                    [(330, 0.10), (262, 0.12), (196, 0.22)], 0.19
                ),
                "record": self._sequence(
                    [(659, 0.055), (784, 0.055), (988, 0.11)], 0.17
                ),
            }
            self.available = True
        except (pygame.error, ValueError):
            self.available = False

    @staticmethod
    def _sequence(notes: list[tuple[float, float]], volume: float) -> pygame.mixer.Sound:
        mixer_info = pygame.mixer.get_init()
        if mixer_info is None:
            raise pygame.error("mixer is not initialized")
        sample_rate, _, channels = mixer_info
        samples = array("h")
        for frequency, duration in notes:
            count = max(1, int(sample_rate * duration))
            fade_in = max(1, int(sample_rate * 0.006))
            fade_out = max(1, int(sample_rate * 0.025))
            for index in range(count):
                envelope = min(1.0, index / fade_in, (count - index) / fade_out)
                wave = math.sin(2 * math.pi * frequency * index / sample_rate)
                wave += 0.18 * math.sin(4 * math.pi * frequency * index / sample_rate)
                value = int(32767 * volume * envelope * wave / 1.18)
                for _ in range(channels):
                    samples.append(value)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play(self, name: str) -> None:
        if not self.available or self.muted:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def toggle(self) -> None:
        self.muted = not self.muted
        if not self.muted:
            self.play("click")


# ---------------------------------------------------------------------------
# 静态图形生成
# ---------------------------------------------------------------------------


def make_background(size: tuple[int, int]) -> pygame.Surface:
    width, height = size
    background = pygame.Surface(size)
    for y in range(height):
        color = mix_color(BG_TOP, BG_BOTTOM, y / max(1, height - 1))
        pygame.draw.line(background, color, (0, y), (width, y))

    glow = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(45, 0, -1):
        radius = int(330 * i / 45)
        alpha = max(1, int(28 * (1 - i / 45) ** 2.2))
        pygame.draw.circle(glow, (65, 230, 160, alpha), (90, 50), radius)
    for i in range(38, 0, -1):
        radius = int(300 * i / 38)
        alpha = max(1, int(30 * (1 - i / 38) ** 2.2))
        pygame.draw.circle(glow, (70, 175, 255, alpha), (900, 750), radius)
    background.blit(glow, (0, 0))
    return background


def make_board_background(size: tuple[int, int]) -> pygame.Surface:
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(surface, (*BOARD_BG, 255), surface.get_rect(), border_radius=18)

    light = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(28, 0, -1):
        radius = int(400 * i / 28)
        alpha = max(1, int(15 * (1 - i / 28) ** 2))
        pygame.draw.circle(light, (80, 255, 180, alpha), (0, 0), radius)
    surface.blit(light, (0, 0))

    for col in range(1, COLS):
        x = col * CELL
        pygame.draw.line(surface, (*BOARD_GRID, 18), (x, 1), (x, height - 1))
    for row in range(1, ROWS):
        y = row * CELL
        pygame.draw.line(surface, (*BOARD_GRID, 18), (1, y), (width - 1, y))

    for col in range(0, COLS + 1, 4):
        for row in range(0, ROWS + 1, 4):
            pygame.draw.circle(
                surface, (*BOARD_GRID, 42), (col * CELL, row * CELL), 1
            )

    pygame.draw.rect(
        surface, (42, 70, 90, 170), surface.get_rect(), width=1, border_radius=18
    )

    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(
        mask, (255, 255, 255, 255), mask.get_rect(), border_radius=18
    )
    surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return surface


def make_board_deco() -> pygame.Surface:
    padding = 34
    surface = pygame.Surface(
        (BOARD_W + padding * 2, BOARD_H + padding * 2), pygame.SRCALPHA
    )
    base = pygame.Rect(padding, padding, BOARD_W, BOARD_H)

    shadow = base.move(0, 12).inflate(10, 10)
    for i in range(12, 0, -1):
        alpha = int(4 + (12 - i) * 2.2)
        pygame.draw.rect(
            surface,
            (0, 0, 0, alpha),
            shadow.inflate(i * 3, i * 4),
            border_radius=22 + i,
        )

    for offset in range(18, 0, -2):
        alpha = max(1, int(6 * (1 - offset / 18) ** 1.4))
        pygame.draw.rect(
            surface,
            (75, 235, 168, alpha),
            base.inflate(offset * 2, offset * 2),
            width=2,
            border_radius=18 + offset,
        )
    return surface


def make_emblem(size: int) -> pygame.Surface:
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    rect = surface.get_rect()
    pygame.draw.rect(surface, (16, 32, 43), rect, border_radius=max(6, size // 6))
    pygame.draw.rect(
        surface,
        (52, 108, 91),
        rect,
        width=max(1, size // 32),
        border_radius=max(6, size // 6),
    )
    unit = size / 48
    points = [
        (18 * unit, 14 * unit),
        (30 * unit, 14 * unit),
        (35 * unit, 19 * unit),
        (34 * unit, 24 * unit),
        (28 * unit, 28 * unit),
        (19 * unit, 28 * unit),
        (15 * unit, 33 * unit),
        (20 * unit, 37 * unit),
        (31 * unit, 37 * unit),
    ]
    int_points = [(int(x), int(y)) for x, y in points]
    pygame.draw.lines(surface, (*ACCENT, 255), False, int_points, max(2, int(4 * unit)))
    for point in int_points[1:]:
        pygame.draw.circle(surface, ACCENT, point, max(1, int(2 * unit)))
    head = int_points[0]
    pygame.draw.circle(surface, ACCENT_BRIGHT, head, max(2, int(3 * unit)))
    pygame.draw.circle(surface, DARK_TEXT, head, max(1, int(1.2 * unit)))
    return surface


def make_radial_glow(
    size: int, color: tuple[int, int, int], falloff: float = 2.0
) -> pygame.Surface:
    """生成用于加色混合的平滑径向光晕。"""
    surface = pygame.Surface((size, size))
    surface.fill((0, 0, 0))
    center = (size - 1) / 2
    radius = size / 2
    for y in range(size):
        for x in range(size):
            distance = math.hypot(x - center, y - center)
            if distance >= radius:
                continue
            strength = (1.0 - distance / radius) ** falloff
            surface.set_at(
                (x, y),
                (
                    int(color[0] * strength),
                    int(color[1] * strength),
                    int(color[2] * strength),
                ),
            )
    return surface


def make_food_image(size: int = 128) -> pygame.Surface:
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    scale = size / 128
    center = (int(64 * scale), int(76 * scale))
    body_radius = 40 * scale

    # 果梗
    pygame.draw.line(
        surface,
        (103, 80, 50),
        (int(64 * scale), int(43 * scale)),
        (int(70 * scale), int(20 * scale)),
        max(2, int(5 * scale)),
    )

    # 叶子
    leaf = pygame.Surface((int(38 * scale), int(22 * scale)), pygame.SRCALPHA)
    pygame.draw.ellipse(leaf, (89, 217, 132), leaf.get_rect())
    pygame.draw.ellipse(
        leaf, (40, 133, 82), leaf.get_rect(), max(1, int(2 * scale))
    )
    pygame.draw.line(
        leaf,
        (35, 114, 69),
        (int(7 * scale), int(11 * scale)),
        (int(30 * scale), int(11 * scale)),
        max(1, int(1.5 * scale)),
    )
    leaf = pygame.transform.rotate(leaf, -30)
    surface.blit(leaf, (int(71 * scale), int(11 * scale)))

    # 边缘与径向高光，使小尺寸下也有体积感
    pygame.draw.circle(
        surface, (112, 22, 49), center, int(body_radius + 2 * scale)
    )
    steps = 18
    for index in range(steps):
        t = index / max(1, steps - 1)
        radius = body_radius * (1 - t * 0.82)
        color = mix_color((210, 53, 78), (255, 129, 143), t)
        pygame.draw.circle(surface, color, center, max(1, int(radius)))

    highlight = pygame.Surface((int(36 * scale), int(36 * scale)), pygame.SRCALPHA)
    for i in range(8, 0, -1):
        alpha = int(18 + i * 8)
        pygame.draw.circle(
            highlight,
            (255, 238, 235, alpha),
            (int(18 * scale), int(18 * scale)),
            max(1, int(i * 2.2 * scale)),
        )
    surface.blit(highlight, (int(44 * scale), int(52 * scale)))

    pygame.draw.circle(
        surface,
        (255, 239, 232),
        (int(51 * scale), int(59 * scale)),
        max(1, int(4 * scale)),
    )
    return surface


# ---------------------------------------------------------------------------
# 最高分存储
# ---------------------------------------------------------------------------


def load_best_score() -> int:
    try:
        data = json.loads(BEST_SCORE_FILE.read_text(encoding="utf-8"))
        return max(0, int(data.get("best", 0)))
    except (OSError, ValueError, TypeError):
        return 0


def save_best_score(value: int) -> None:
    temporary = BEST_SCORE_FILE.with_suffix(".tmp")
    try:
        temporary.write_text(
            json.dumps({"best": int(value)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(BEST_SCORE_FILE)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 游戏主体
# ---------------------------------------------------------------------------


class SnakeGame:
    def __init__(self) -> None:
        pygame.display.set_caption("贪吃蛇 · Neon Snake")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_icon(make_emblem(64))
        self.clock = pygame.time.Clock()
        self.fonts = FontBook()
        self.rng = random.Random()
        self.background = make_background((WINDOW_W, WINDOW_H))
        self.board_background = make_board_background((BOARD_W, BOARD_H))
        self.board_deco = make_board_deco()
        self.board_layer = pygame.Surface((BOARD_W, BOARD_H), pygame.SRCALPHA)
        self.glow_layer = pygame.Surface((BOARD_W // 2, BOARD_H // 2))
        self.glow_full = pygame.Surface((BOARD_W, BOARD_H))
        self.fx_layer = pygame.Surface((BOARD_W, BOARD_H), pygame.SRCALPHA)
        self.ambient_layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        self.ui_layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        self.food_image = make_food_image(128)
        self.food_glow_image = make_radial_glow(96, (102, 25, 33), 2.1)
        self.snake_head_glow_image = make_radial_glow(96, (38, 112, 73), 2.2)
        self.hud_emblem = make_emblem(48)

        self.sound = SoundBank()
        self.best = load_best_score()
        self.score = 0
        self.new_record = False
        self.victory = False

        self.state = GameState.MENU
        self.state_time = 0.0
        self.time = 0.0
        self.running = True
        self.active_buttons: list[Button] = []
        self.mouse_pos = (0, 0)
        self._cursor_hand = False

        self.snake: list[tuple[int, int]] = []
        self.prev_snake: list[tuple[int, int]] = []
        self.direction = RIGHT
        self.direction_queue: deque[tuple[int, int]] = deque()
        self.food: tuple[int, int] | None = None
        self.food_born = 0.0
        self.step_interval = START_STEP
        self.move_accumulator = 0.0
        self.move_progress = 0.0
        self.particles: list[Particle] = []
        self.floaters: list[FloatingText] = []
        self.shake_time = 0.0
        self.shake_duration = 0.0
        self.shake_strength = 0.0

        self.motes = self._create_motes(38)
        self._prepare_preview()
        self._rebuild_buttons()
        self._draw()

    # ------------------------------------------------------------------
    # 状态与一局游戏
    # ------------------------------------------------------------------

    def _create_motes(self, count: int) -> list[Mote]:
        motes = []
        palette = (ACCENT, CYAN, (230, 245, 255))
        for _ in range(count):
            motes.append(
                Mote(
                    x=self.rng.uniform(16, WINDOW_W - 16),
                    y=self.rng.uniform(0, WINDOW_H),
                    radius=self.rng.uniform(0.6, 1.9),
                    speed=self.rng.uniform(3.0, 10.0),
                    phase=self.rng.uniform(0, math.tau),
                    color=self.rng.choice(palette),
                    alpha=self.rng.randint(18, 65),
                )
            )
        return motes

    def _prepare_preview(self) -> None:
        center_x, center_y = COLS // 2, ROWS // 2
        self.snake = [
            (center_x, center_y),
            (center_x - 1, center_y),
            (center_x - 2, center_y),
            (center_x - 3, center_y),
        ]
        self.prev_snake = self.snake.copy()
        self.direction = RIGHT
        self.direction_queue.clear()
        self.score = 0
        self.new_record = False
        self.victory = False
        self.step_interval = START_STEP
        self.move_accumulator = 0.0
        self.move_progress = 0.0
        self.particles.clear()
        self.floaters.clear()
        self.shake_time = 0.0
        self.food = self._random_food_cell()
        # 预览/开局时直接展示食物，避免开头有半秒空棋盘。
        self.food_born = self.time - 1.0

    def _start_game(self) -> None:
        self._prepare_preview()
        self.state = GameState.PLAYING
        self.state_time = 0.0
        self.active_buttons = []
        self.sound.play("start")

    def _go_menu(self) -> None:
        self._prepare_preview()
        self.state = GameState.MENU
        self.state_time = 0.0
        self.sound.play("click")
        self._rebuild_buttons()

    def _pause_game(self) -> None:
        if self.state is not GameState.PLAYING:
            return
        self.state = GameState.PAUSED
        self.state_time = 0.0
        self.sound.play("pause")
        self._rebuild_buttons()

    def _resume_game(self) -> None:
        if self.state is not GameState.PAUSED:
            return
        self.state = GameState.PLAYING
        self.state_time = 0.0
        self.active_buttons = []
        self.sound.play("resume")

    def _end_game(self, victory: bool = False) -> None:
        if self.state is not GameState.PLAYING:
            return
        self.victory = victory
        self.state = GameState.GAME_OVER
        self.state_time = 0.0
        self.prev_snake = self.snake.copy()
        self.move_progress = 0.0
        self._rebuild_buttons()
        if victory:
            self.sound.play("record")
            self._burst_snake_head((GOLD, ACCENT_BRIGHT, CYAN), count=34)
        else:
            self.sound.play("game_over")
            self.shake_duration = 0.38
            self.shake_time = self.shake_duration
            self.shake_strength = 5.0
            self._burst_snake_head((RED, GOLD, (255, 160, 120)), count=30)

    def _rebuild_buttons(self) -> None:
        if self.state is GameState.MENU:
            self.active_buttons = [
                Button(
                    pygame.Rect(350, MENU_CARD.top + 276, 260, 56),
                    "开始游戏",
                    "start",
                )
            ]
        elif self.state is GameState.PAUSED:
            self.active_buttons = [
                Button(
                    pygame.Rect(288, PAUSE_CARD.top + 160, 184, 52),
                    "继续游戏",
                    "resume",
                ),
                Button(
                    pygame.Rect(488, PAUSE_CARD.top + 160, 184, 52),
                    "重新开始",
                    "restart",
                    "secondary",
                ),
            ]
        elif self.state is GameState.GAME_OVER:
            self.active_buttons = [
                Button(
                    pygame.Rect(250, GAME_OVER_CARD.top + 262, 220, 52),
                    "再来一局",
                    "restart",
                ),
                Button(
                    pygame.Rect(490, GAME_OVER_CARD.top + 262, 220, 52),
                    "返回菜单",
                    "menu",
                    "secondary",
                ),
            ]
        else:
            self.active_buttons = []

    # ------------------------------------------------------------------
    # 输入
    # ------------------------------------------------------------------

    def _action_for_key(self, key: int) -> None:
        if key == pygame.K_m:
            self.sound.toggle()
            return

        if key == pygame.K_ESCAPE:
            if self.state is GameState.MENU:
                self.running = False
            elif self.state is GameState.PLAYING:
                self._pause_game()
            elif self.state is GameState.PAUSED:
                self._go_menu()
            elif self.state is GameState.GAME_OVER:
                self._go_menu()
            return

        if self.state is GameState.MENU:
            if key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self._start_game()
        elif self.state is GameState.PLAYING:
            if key in (pygame.K_SPACE, pygame.K_p):
                self._pause_game()
            elif key in KEY_DIRECTIONS:
                self._queue_direction(KEY_DIRECTIONS[key])
        elif self.state is GameState.PAUSED:
            if key in (pygame.K_SPACE, pygame.K_p):
                self._resume_game()
            elif key == pygame.K_r:
                self._start_game()
        elif self.state is GameState.GAME_OVER:
            if key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_r):
                self._start_game()

    def _queue_direction(self, new_direction: tuple[int, int]) -> None:
        reference = self.direction_queue[-1] if self.direction_queue else self.direction
        if new_direction == reference:
            return
        if new_direction == (-reference[0], -reference[1]):
            return
        if len(self.direction_queue) < 2:
            self.direction_queue.append(new_direction)

    def _handle_click(self, position: tuple[int, int]) -> None:
        for button in self.active_buttons:
            if not button.rect.collidepoint(position):
                continue
            if button.kind == "primary":
                self.sound.play("click")
            if button.action == "start":
                self._start_game()
            elif button.action == "resume":
                self._resume_game()
            elif button.action == "restart":
                self._start_game()
            elif button.action == "menu":
                self._go_menu()
            return

    def _process_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._action_for_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos
            elif event.type == pygame.WINDOWFOCUSLOST:
                if self.state is GameState.PLAYING:
                    self._pause_game()

    # ------------------------------------------------------------------
    # 更新
    # ------------------------------------------------------------------

    def _random_food_cell(self) -> tuple[int, int]:
        occupied = set(self.snake)
        free = [
            (col, row)
            for row in range(ROWS)
            for col in range(COLS)
            if (col, row) not in occupied
        ]
        return self.rng.choice(free) if free else (0, 0)

    def _spawn_food(self) -> bool:
        occupied = set(self.snake)
        free = [
            (col, row)
            for row in range(ROWS)
            for col in range(COLS)
            if (col, row) not in occupied
        ]
        if not free:
            self.food = None
            return False
        self.food = self.rng.choice(free)
        self.food_born = self.time
        return True

    def _advance_direction(self) -> None:
        while self.direction_queue:
            candidate = self.direction_queue.popleft()
            if candidate != (-self.direction[0], -self.direction[1]):
                self.direction = candidate
                break

    def _step(self) -> None:
        if self.state is not GameState.PLAYING:
            return
        self._advance_direction()
        head_x, head_y = self.snake[0]
        new_head = (head_x + self.direction[0], head_y + self.direction[1])

        if not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS):
            self._end_game()
            return

        eating = self.food is not None and new_head == self.food
        collision_body = self.snake if eating else self.snake[:-1]
        if new_head in collision_body:
            self._end_game()
            return

        old_snake = self.snake
        old_food = self.food
        if eating:
            self.prev_snake = old_snake + [old_snake[-1]]
            self.snake = [new_head] + old_snake
        else:
            self.prev_snake = old_snake.copy()
            self.snake = [new_head] + old_snake[:-1]
        self.move_progress = 0.0

        if not eating:
            return

        self.score += FOOD_SCORE
        if self.score > self.best:
            self.best = self.score
            self.new_record = True
            save_best_score(self.best)
        center = self._cell_center(*old_food) if old_food else (0, 0)
        self._emit_food_burst(center)
        text_y = center[1] - CELL * 0.95
        if text_y < CELL:
            text_y = center[1] + CELL * 0.95
        self.floaters.append(
            FloatingText(center[0], text_y, f"+{FOOD_SCORE}", 0.9, 0.9, GOLD)
        )
        self.sound.play("eat")
        self.step_interval = max(
            MIN_STEP, START_STEP - (len(self.snake) - 4) * 0.0041
        )
        if not self._spawn_food():
            self._end_game(victory=True)

    def _update(self, dt: float) -> None:
        self.time += dt
        self.state_time += dt
        self.mouse_pos = pygame.mouse.get_pos()

        for mote in self.motes:
            mote.y -= mote.speed * dt
            mote.x += math.sin(self.time * 0.55 + mote.phase) * 3.5 * dt
            if mote.y < -4:
                mote.y = WINDOW_H + 4
                mote.x = self.rng.uniform(16, WINDOW_W - 16)
            if mote.x < -4:
                mote.x = WINDOW_W + 4
            elif mote.x > WINDOW_W + 4:
                mote.x = -4

        if self.shake_time > 0:
            self.shake_time = max(0.0, self.shake_time - dt)

        for particle in self.particles:
            particle.life -= dt
            particle.vy += particle.gravity * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vx *= max(0.0, 1.0 - 1.7 * dt)
            particle.vy *= max(0.0, 1.0 - 0.5 * dt)
        self.particles = [p for p in self.particles if p.life > 0]

        for floater in self.floaters:
            floater.life -= dt
            floater.y -= 32 * dt
        self.floaters = [f for f in self.floaters if f.life > 0]

        if self.state is GameState.PLAYING:
            self.move_accumulator += dt
            while (
                self.move_accumulator >= self.step_interval
                and self.state is GameState.PLAYING
            ):
                self.move_accumulator -= self.step_interval
                self._step()
            if self.state is GameState.PLAYING:
                self.move_progress = min(
                    1.0, self.move_accumulator / max(0.001, self.step_interval)
                )

        hovering = any(
            button.rect.collidepoint(self.mouse_pos) for button in self.active_buttons
        )
        if hovering != self._cursor_hand:
            self._cursor_hand = hovering
            cursor = (
                pygame.SYSTEM_CURSOR_HAND if hovering else pygame.SYSTEM_CURSOR_ARROW
            )
            try:
                pygame.mouse.set_cursor(cursor)
            except pygame.error:
                pass

    # ------------------------------------------------------------------
    # 特效
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_center(col: int, row: int) -> tuple[float, float]:
        return ((col + 0.5) * CELL, (row + 0.5) * CELL)

    def _emit_food_burst(self, center: tuple[float, float]) -> None:
        colors = (RED, (255, 154, 151), GOLD, ACCENT)
        for _ in range(20):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(35, 150)
            life = self.rng.uniform(0.35, 0.75)
            self.particles.append(
                Particle(
                    x=center[0],
                    y=center[1],
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=life,
                    max_life=life,
                    radius=self.rng.uniform(1.4, 3.6),
                    color=self.rng.choice(colors),
                    gravity=55,
                )
            )

    def _burst_snake_head(
        self, colors: tuple[tuple[int, int, int], ...], count: int
    ) -> None:
        if not self.snake:
            return
        center = self._cell_center(*self.snake[0])
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(30, 190)
            life = self.rng.uniform(0.4, 0.9)
            self.particles.append(
                Particle(
                    x=center[0],
                    y=center[1],
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=life,
                    max_life=life,
                    radius=self.rng.uniform(1.2, 4.0),
                    color=self.rng.choice(colors),
                    gravity=30,
                )
            )

    # ------------------------------------------------------------------
    # 绘制：棋盘与游戏对象
    # ------------------------------------------------------------------

    def _snake_points(self) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        progress = self.move_progress
        for index, cell in enumerate(self.snake):
            previous = (
                self.prev_snake[index]
                if index < len(self.prev_snake)
                else cell
            )
            x = (previous[0] + (cell[0] - previous[0]) * progress + 0.5) * CELL
            y = (previous[1] + (cell[1] - previous[1]) * progress + 0.5) * CELL
            points.append((x, y))
        return points

    def _segment_radius(self, index: int, count: int) -> float:
        if count <= 1:
            return CELL * 0.38
        factor = index / (count - 1)
        return CELL * (0.40 - 0.165 * factor**1.25)

    def _segment_color(self, index: int, count: int) -> tuple[int, int, int]:
        if count <= 1:
            return HEAD_GREEN
        factor = (index / (count - 1)) ** 0.85
        return mix_color(HEAD_GREEN, TAIL_GREEN, factor)

    def _draw_food(self) -> None:
        if self.food is None:
            return
        center_x, center_y = self._cell_center(*self.food)
        age = self.time - self.food_born
        grow = ease_out_cubic(min(1.0, age / 0.22))
        if grow <= 0.01:
            return
        pulse = 1.0 + math.sin(self.time * 4.4) * 0.035
        bob = math.sin(self.time * 3.0 + self.food[0] * 0.7) * 1.3
        center = (int(center_x), int(center_y + bob))

        glow_pulse = 1.0 + math.sin(self.time * 4.4) * 0.08
        glow_size = max(1, int(CELL * 2.55 * grow * glow_pulse))
        glow = pygame.transform.smoothscale(
            self.food_glow_image, (glow_size, glow_size)
        )
        self.board_layer.blit(
            glow,
            glow.get_rect(center=center),
            special_flags=pygame.BLEND_RGB_ADD,
        )

        final_size = CELL * 1.32 * grow * pulse
        image = pygame.transform.smoothscale(
            self.food_image, (max(1, int(final_size)), max(1, int(final_size)))
        )
        self.board_layer.blit(image, image.get_rect(center=center))

    def _draw_snake_glow(self, points: list[tuple[float, float]]) -> None:
        count = len(points)
        scale = 0.5
        scaled_points = [(x * scale, y * scale) for x, y in points]
        for width_extra, color in (
            (28, (2, 8, 6)),
            (23, (2, 11, 7)),
            (18, (3, 15, 10)),
            (13, (4, 20, 13)),
            (8, (6, 27, 18)),
        ):
            for index in range(count - 1, 0, -1):
                radius = self._segment_radius(index, count)
                width = max(1, int((radius * 2 + width_extra) * scale))
                pygame.draw.line(
                    self.glow_layer,
                    color,
                    scaled_points[index],
                    scaled_points[index - 1],
                    width,
                )
                pygame.draw.circle(
                    self.glow_layer,
                    color,
                    (int(scaled_points[index][0]), int(scaled_points[index][1])),
                    max(1, int((radius + width_extra / 2) * scale)),
                )

    def _draw_snake(self) -> None:
        if not self.snake:
            return
        points = self._snake_points()
        count = len(points)

        # 头部柔和光晕
        head_glow_size = max(1, int(CELL * 2.2))
        head_glow = pygame.transform.smoothscale(
            self.snake_head_glow_image, (head_glow_size, head_glow_size)
        )
        self.board_layer.blit(
            head_glow,
            head_glow.get_rect(
                center=(int(points[0][0]), int(points[0][1]))
            ),
            special_flags=pygame.BLEND_RGB_ADD,
        )

        # 深色描边把蛇身从棋盘背景中分离出来
        for index in range(count - 1, -1, -1):
            radius = self._segment_radius(index, count)
            if index > 0:
                line_width = int(
                    2 * min(radius, self._segment_radius(index - 1, count)) + 4.5
                )
                pygame.draw.line(
                    self.board_layer, (5, 22, 16), points[index], points[index - 1], line_width
                )
            pygame.draw.circle(
                self.board_layer,
                (5, 22, 16),
                (int(points[index][0]), int(points[index][1])),
                int(radius + 2.5),
            )

        # 颜色由尾部到头部渐变
        for index in range(count - 1, -1, -1):
            radius = self._segment_radius(index, count)
            color = self._segment_color(index, count)
            if index > 0:
                next_radius = self._segment_radius(index - 1, count)
                segment_color = mix_color(
                    color, self._segment_color(index - 1, count), 0.5
                )
                pygame.draw.line(
                    self.board_layer,
                    segment_color,
                    points[index],
                    points[index - 1],
                    int(2 * min(radius, next_radius)),
                )
            pygame.draw.circle(
                self.board_layer,
                color,
                (int(points[index][0]), int(points[index][1])),
                int(radius),
            )

        # 头部
        head_x, head_y = points[0]
        head_radius = int(CELL * 0.445)
        pygame.draw.circle(
            self.board_layer,
            (5, 22, 16),
            (int(head_x), int(head_y)),
            head_radius + 2,
        )
        pygame.draw.circle(
            self.board_layer,
            HEAD_GREEN,
            (int(head_x), int(head_y)),
            head_radius,
        )

        # 背部高光
        if count > 2:
            highlight_points = [(x, y - 2.6) for x, y in points[1:]]
            for index in range(len(highlight_points) - 1, 0, -1):
                color = mix_color(
                    self._segment_color(index + 1, count), (255, 255, 255), 0.28
                )
                pygame.draw.line(
                    self.board_layer,
                    color,
                    highlight_points[index],
                    highlight_points[index - 1],
                    2,
                )

        self._draw_eyes((head_x, head_y), head_radius)

    def _draw_eyes(
        self, head_center: tuple[float, float], head_radius: int
    ) -> None:
        direction_x, direction_y = self.direction
        perpendicular = (-direction_y, direction_x)
        forward_offset = 3.8
        side_offset = 5.3
        dead = self.state is GameState.GAME_OVER and not self.victory

        for side in (-1, 1):
            eye_x = (
                head_center[0]
                + direction_x * forward_offset
                + perpendicular[0] * side_offset * side
            )
            eye_y = (
                head_center[1]
                + direction_y * forward_offset
                + perpendicular[1] * side_offset * side
            )
            if dead:
                pygame.draw.line(
                    self.board_layer,
                    (9, 36, 25),
                    (int(eye_x - 3), int(eye_y - 3)),
                    (int(eye_x + 3), int(eye_y + 3)),
                    2,
                )
                pygame.draw.line(
                    self.board_layer,
                    (9, 36, 25),
                    (int(eye_x + 3), int(eye_y - 3)),
                    (int(eye_x - 3), int(eye_y + 3)),
                    2,
                )
                continue
            pygame.draw.circle(
                self.board_layer,
                (8, 43, 29),
                (int(eye_x), int(eye_y)),
                5,
            )
            pygame.draw.circle(
                self.board_layer,
                (244, 255, 249),
                (int(eye_x), int(eye_y)),
                4,
            )
            pupil_x = eye_x + direction_x * 1.25
            pupil_y = eye_y + direction_y * 1.25
            pygame.draw.circle(
                self.board_layer,
                (7, 31, 22),
                (int(pupil_x), int(pupil_y)),
                2,
            )
            pygame.draw.circle(
                self.board_layer,
                (255, 255, 255),
                (int(eye_x - 1), int(eye_y - 1)),
                1,
            )

    def _draw_particles(self) -> None:
        if not self.particles:
            return
        self.fx_layer.fill((0, 0, 0, 0))
        for particle in self.particles:
            alpha = int(255 * max(0.0, particle.life / particle.max_life))
            color = (*particle.color, alpha)
            radius = max(1, int(particle.radius))
            pygame.draw.circle(
                self.fx_layer,
                color,
                (int(particle.x), int(particle.y)),
                radius,
            )
        self.board_layer.blit(self.fx_layer, (0, 0))

    def _draw_floaters(self) -> None:
        if not self.floaters:
            return
        font = self.fonts.get(18, bold=True, display=True)
        for floater in self.floaters:
            ratio = max(0.0, floater.life / floater.max_life)
            alpha = int(255 * min(1.0, ratio * 2.2))
            image = font.render(floater.text, True, floater.color)
            image.set_alpha(alpha)
            self.board_layer.blit(
                image, image.get_rect(center=(int(floater.x), int(floater.y)))
            )

    def _build_board(self) -> None:
        self.board_layer.fill((0, 0, 0, 0))
        self.glow_layer.fill((0, 0, 0))
        self.board_layer.blit(self.board_background, (0, 0))
        if self.state is not GameState.MENU:
            if self.snake:
                self._draw_snake_glow(self._snake_points())
            pygame.transform.smoothscale(
                self.glow_layer, (BOARD_W, BOARD_H), self.glow_full
            )
            self.board_layer.blit(
                self.glow_full, (0, 0), special_flags=pygame.BLEND_RGB_ADD
            )
            self._draw_food()
            self._draw_snake()
            self._draw_particles()
            self._draw_floaters()

    def _board_shake_offset(self) -> tuple[int, int]:
        if self.shake_time <= 0 or self.shake_duration <= 0:
            return 0, 0
        ratio = self.shake_time / self.shake_duration
        amplitude = self.shake_strength * ratio
        return (
            int(random.uniform(-amplitude, amplitude)),
            int(random.uniform(-amplitude, amplitude)),
        )

    # ------------------------------------------------------------------
    # 绘制：HUD 与界面
    # ------------------------------------------------------------------

    def _draw_hud(self) -> None:
        self.screen.blit(self.hud_emblem, (BOARD_X, 30))
        draw_tracked_text(
            self.screen,
            "SNAKE",
            self.fonts.get(30, bold=True, display=True),
            TEXT,
            BOARD_X + 106,
            32,
            2.2,
        )
        draw_text(
            self.screen,
            "霓虹贪吃蛇  ·  NEON",
            self.fonts.get(11),
            MUTED,
            (BOARD_X + 123, 67),
        )

        score_rect = pygame.Rect(600, 32, 140, 64)
        best_rect = pygame.Rect(752, 32, 144, 64)
        self._draw_stat_card(score_rect, "得分", score_text(self.score), ACCENT)
        self._draw_stat_card(best_rect, "最高分", score_text(self.best), GOLD)

        pygame.draw.line(
            self.screen,
            (27, 45, 61),
            (BOARD_X, 112),
            (WINDOW_W - BOARD_X, 112),
        )

        self._draw_footer()

    def _draw_stat_card(
        self,
        rect: pygame.Rect,
        label: str,
        value: str,
        accent: tuple[int, int, int],
    ) -> None:
        pygame.draw.rect(self.screen, PANEL_BG, rect, border_radius=13)
        pygame.draw.rect(
            self.screen, PANEL_BORDER, rect, width=1, border_radius=13
        )
        pygame.draw.rect(
            self.screen,
            accent,
            pygame.Rect(rect.x + 14, rect.bottom - 12, 24, 2),
            border_radius=1,
        )
        draw_text(
            self.screen,
            label,
            self.fonts.get(11),
            MUTED,
            (rect.x + 14, rect.centery - 16),
        )
        draw_text(
            self.screen,
            value,
            self.fonts.get(28, bold=True, display=True),
            accent,
            (rect.right - 14, rect.centery - 3),
            anchor="midright",
        )

    def _draw_footer(self) -> None:
        key_font = self.fonts.get(11, bold=True)
        action_font = self.fonts.get(12)
        groups = [
            ("方向键 / WASD", "移动"),
            ("SPACE", "暂停"),
            ("M", "开启声音" if self.sound.muted else "静音"),
            ("ESC", "菜单"),
        ]

        gap_key_to_action = 6
        gap_group = 22
        measured: list[tuple[int, int, str, str]] = []
        for key_label, action in groups:
            key_width = key_font.size(key_label)[0] + 14
            action_width = action_font.size(action)[0]
            measured.append((key_width, action_width, key_label, action))
        total_width = sum(
            key_width + gap_key_to_action + action_width
            for key_width, action_width, _, _ in measured
        ) + gap_group * (len(measured) - 1)
        x = (WINDOW_W - total_width) // 2
        y = 722
        for key_width, action_width, key_label, action in measured:
            draw_keycap(self.screen, key_label, key_font, x, y)
            draw_text(
                self.screen,
                action,
                action_font,
                MUTED,
                (x + key_width + gap_key_to_action, y + 11),
                anchor="midleft",
            )
            x += key_width + gap_key_to_action + action_width + gap_group

        sound_dot = ACCENT if not self.sound.muted else FAINT
        pygame.draw.circle(self.screen, sound_dot, (BOARD_X + 5, 733), 3)
        draw_text(
            self.screen,
            "声音开启" if not self.sound.muted else "已静音",
            self.fonts.get(10),
            FAINT,
            (BOARD_X + 14, 733),
            anchor="midleft",
        )

    def _draw_menu(self) -> None:
        card = MENU_CARD
        self._draw_card(card, ACCENT)
        center = card.centerx
        draw_tracked_text(
            self.screen,
            "NEON ARCADE",
            self.fonts.get(11, bold=True, display=True),
            ACCENT_DIM,
            center,
            card.top + 30,
            4.0,
        )
        draw_text(
            self.screen,
            "贪吃蛇",
            self.fonts.get(58, bold=True),
            TEXT,
            (center, card.top + 54),
            anchor="midtop",
        )
        draw_text(
            self.screen,
            "吞噬果实，越长越快。别撞墙，也别咬到自己。",
            self.fonts.get(14),
            MUTED,
            (center, card.top + 132),
            anchor="midtop",
        )

        chip_y = card.top + 170
        chip_width = 160
        chip_gap = 12
        chip_start = center - (chip_width * 3 + chip_gap * 2) // 2
        chips = [
            ("移动", "WASD / 方向键"),
            ("暂停", "SPACE"),
            ("静音", "M"),
        ]
        for index, (title, keys) in enumerate(chips):
            rect = pygame.Rect(
                chip_start + index * (chip_width + chip_gap), chip_y, chip_width, 46
            )
            self._draw_control_chip(rect, title, keys)

        draw_inline(
            self.screen,
            [("最高纪录", MUTED), (score_text(self.best), GOLD)],
            self.fonts.get(13),
            center,
            card.top + 233,
            gap=12,
        )

        for button in self.active_buttons:
            self._draw_button(button)

        draw_inline(
            self.screen,
            [
                ("SPACE / ENTER", ACCENT_DIM),
                ("开始", MUTED),
                ("·", FAINT),
                ("ESC", FAINT),
                ("退出", FAINT),
            ],
            self.fonts.get(11),
            center,
            card.top + 350,
            gap=6,
        )

    def _draw_pause(self) -> None:
        card = PAUSE_CARD
        self._draw_card(card, ACCENT)
        center = card.centerx
        draw_tracked_text(
            self.screen,
            "PAUSED",
            self.fonts.get(11, bold=True, display=True),
            ACCENT_DIM,
            center,
            card.top + 28,
            4.0,
        )
        draw_text(
            self.screen,
            "已暂停",
            self.fonts.get(38, bold=True),
            TEXT,
            (center, card.top + 54),
            anchor="midtop",
        )
        draw_text(
            self.screen,
            "休息一下，节奏不会丢。",
            self.fonts.get(13),
            MUTED,
            (center, card.top + 112),
            anchor="midtop",
        )
        for button in self.active_buttons:
            self._draw_button(button)
        draw_inline(
            self.screen,
            [
                ("SPACE", ACCENT_DIM),
                ("继续", MUTED),
                ("·", FAINT),
                ("R", FAINT),
                ("重开", FAINT),
                ("·", FAINT),
                ("ESC", FAINT),
                ("菜单", FAINT),
            ],
            self.fonts.get(11),
            center,
            card.top + 238,
            gap=6,
        )

    def _draw_game_over(self) -> None:
        card = GAME_OVER_CARD
        accent = GOLD if self.victory else RED
        self._draw_card(card, accent)
        center = card.centerx
        draw_tracked_text(
            self.screen,
            "VICTORY" if self.victory else "GAME OVER",
            self.fonts.get(11, bold=True, display=True),
            accent,
            center,
            card.top + 28,
            4.0,
        )
        draw_text(
            self.screen,
            "完美通关！" if self.victory else "游戏结束",
            self.fonts.get(40, bold=True),
            TEXT,
            (center, card.top + 52),
            anchor="midtop",
        )
        draw_text(
            self.screen,
            "本局得分",
            self.fonts.get(11),
            MUTED,
            (center, card.top + 126),
            anchor="midtop",
        )
        draw_text(
            self.screen,
            score_text(self.score),
            self.fonts.get(56, bold=True, display=True),
            accent,
            (center, card.top + 144),
            anchor="midtop",
        )

        if self.new_record:
            record_segments = [
                ("新纪录", GOLD),
                ("·", MUTED),
                (f"最高分 {score_text(self.best)}", MUTED),
            ]
        else:
            record_segments = [("最高分", MUTED), (score_text(self.best), GOLD)]
        draw_inline(
            self.screen,
            record_segments,
            self.fonts.get(12),
            center,
            card.top + 212,
            gap=8,
        )

        for button in self.active_buttons:
            self._draw_button(button)
        draw_inline(
            self.screen,
            [
                ("SPACE", ACCENT_DIM),
                ("再来一局", MUTED),
                ("·", FAINT),
                ("ESC", FAINT),
                ("返回菜单", FAINT),
            ],
            self.fonts.get(11),
            center,
            card.top + 338,
            gap=6,
        )

    def _draw_card(self, card: pygame.Rect, accent: tuple[int, int, int]) -> None:
        self.ui_layer.fill((0, 0, 0, 0))
        shade_alpha = 188 if self.state is GameState.MENU else 202
        pygame.draw.rect(
            self.ui_layer,
            (3, 8, 15, shade_alpha),
            pygame.Rect(BOARD_X, BOARD_Y, BOARD_W, BOARD_H),
            border_radius=18,
        )

        shadow = card.move(0, 15)
        pygame.draw.rect(
            self.ui_layer, (0, 0, 0, 135), shadow, border_radius=24
        )
        for offset in range(16, 0, -2):
            alpha = max(1, int(34 * (1 - offset / 16) ** 1.8))
            pygame.draw.rect(
                self.ui_layer,
                (*accent, alpha),
                card.inflate(offset * 2, offset * 2),
                width=2,
                border_radius=20 + offset,
            )
        pygame.draw.rect(self.ui_layer, (11, 21, 34, 255), card, border_radius=20)
        pygame.draw.rect(
            self.ui_layer, (*mix_color(PANEL_BORDER, accent, 0.25), 210), card, width=1, border_radius=20
        )
        pygame.draw.rect(
            self.ui_layer,
            (*accent, 185),
            pygame.Rect(card.centerx - 24, card.top, 48, 2),
            border_radius=1,
        )
        self.screen.blit(self.ui_layer, (0, 0))

    def _draw_control_chip(self, rect: pygame.Rect, title: str, keys: str) -> None:
        pygame.draw.rect(self.screen, (15, 27, 42), rect, border_radius=11)
        pygame.draw.rect(
            self.screen, (34, 54, 71), rect, width=1, border_radius=11
        )
        draw_text(
            self.screen,
            title,
            self.fonts.get(10),
            MUTED,
            (rect.centerx, rect.top + 7),
            anchor="midtop",
        )
        draw_text(
            self.screen,
            keys,
            self.fonts.get(12, bold=True),
            TEXT,
            (rect.centerx, rect.top + 24),
            anchor="midtop",
        )

    def _draw_button(self, button: Button) -> None:
        rect = button.rect
        hovered = rect.collidepoint(self.mouse_pos)
        label_font = self.fonts.get(16, bold=True)

        if button.kind == "primary":
            fill = ACCENT_BRIGHT if hovered else ACCENT
            shadow = rect.move(0, 4)
            pygame.draw.rect(
                self.screen, (26, 85, 62), shadow, border_radius=13
            )
            if hovered:
                draw_soft_glow(self.screen, rect, ACCENT, spread=14, strength=65, radius=13)
            pygame.draw.rect(self.screen, fill, rect, border_radius=13)
            draw_text(
                self.screen,
                button.label,
                label_font,
                DARK_TEXT,
                rect.center,
                anchor="center",
            )
        else:
            fill = (23, 39, 55) if hovered else (17, 30, 45)
            border = (64, 94, 111) if hovered else (43, 64, 80)
            pygame.draw.rect(self.screen, fill, rect, border_radius=13)
            pygame.draw.rect(
                self.screen, border, rect, width=1, border_radius=13
            )
            draw_text(
                self.screen,
                button.label,
                label_font,
                TEXT if hovered else MUTED,
                rect.center,
                anchor="center",
            )

    def _draw_overlay(self) -> None:
        if self.state is GameState.MENU:
            self._draw_menu()
        elif self.state is GameState.PAUSED:
            self._draw_pause()
        elif self.state is GameState.GAME_OVER:
            self._draw_game_over()

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        self.screen.blit(self.background, (0, 0))

        self.ambient_layer.fill((0, 0, 0, 0))
        for mote in self.motes:
            pygame.draw.circle(
                self.ambient_layer,
                (*mote.color, mote.alpha),
                (int(mote.x), int(mote.y)),
                max(1, int(mote.radius)),
            )
        self.screen.blit(self.ambient_layer, (0, 0))

        self.screen.blit(self.board_deco, (BOARD_X - 34, BOARD_Y - 34))
        self._build_board()
        shake_x, shake_y = self._board_shake_offset()
        self.screen.blit(self.board_layer, (BOARD_X + shake_x, BOARD_Y + shake_y))

        self._draw_hud()
        if self.state is not GameState.PLAYING:
            self._draw_overlay()

        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self._process_events()
            if not self.running:
                break
            self._update(dt)
            self._draw()
        pygame.quit()


def main() -> None:
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
    except pygame.error:
        pass
    game = SnakeGame()
    game.run()


if __name__ == "__main__":
    main()
