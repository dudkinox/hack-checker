#!/usr/bin/env python3
"""Tkinter screenshot-based checkers move advisor."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import mss
from PIL import Image, ImageDraw, ImageFont, ImageTk


RGB = Tuple[float, float, float]
Square = Tuple[int, int]

BOARD_SIZE = 8
OUR_COLOR = (0, 200, 83)
OPPONENT_COLOR = (229, 57, 53)
MOVE_COLOR = (255, 214, 10)
DEST_COLOR = (41, 121, 255)
CAPTURE_COLOR = (255, 145, 0)
GRID_COLOR = (255, 255, 255, 120)


@dataclass
class CellSample:
    row: int
    col: int
    center_color: RGB
    background_color: RGB
    diff: float
    luminance: float


@dataclass
class Piece:
    owner: str
    is_king: bool = False


@dataclass
class Move:
    path: List[Square]
    captures: List[Square]
    score: float = 0.0


Board = List[List[Optional[Piece]]]


@dataclass
class ScreenCapture:
    image: Image.Image
    left: int
    top: int


def capture_screen(monitor_number: int = 0) -> ScreenCapture:
    with mss.mss() as screenshotter:
        if monitor_number >= len(screenshotter.monitors):
            raise ValueError(
                f"Monitor {monitor_number} not found. "
                f"Available monitors: 0-{len(screenshotter.monitors) - 1}"
            )

        monitor = screenshotter.monitors[monitor_number]
        grabbed = screenshotter.grab(monitor)
        image = Image.frombytes("RGB", grabbed.size, grabbed.rgb)
        return ScreenCapture(image=image, left=monitor["left"], top=monitor["top"])


def capture_screen_region(rect: Tuple[int, int, int, int]) -> Image.Image:
    left, top, right, bottom = rect
    region = {
        "left": left,
        "top": top,
        "width": max(1, right - left),
        "height": max(1, bottom - top),
    }
    with mss.mss() as screenshotter:
        grabbed = screenshotter.grab(region)
        return Image.frombytes("RGB", grabbed.size, grabbed.rgb)


def color_distance(first: RGB, second: RGB) -> float:
    return math.sqrt(
        (first[0] - second[0]) ** 2
        + (first[1] - second[1]) ** 2
        + (first[2] - second[2]) ** 2
    )


def luminance(color: RGB) -> float:
    return color[0] * 0.2126 + color[1] * 0.7152 + color[2] * 0.0722


def mean_color_for_box(image: Image.Image, box: Tuple[float, float, float, float]) -> RGB:
    left, top, right, bottom = [int(round(value)) for value in box]
    left = max(0, min(image.width - 1, left))
    top = max(0, min(image.height - 1, top))
    right = max(left + 1, min(image.width, right))
    bottom = max(top + 1, min(image.height, bottom))

    red_total = 0
    green_total = 0
    blue_total = 0
    count = 0
    pixels = image.load()
    for y in range(top, bottom):
        for x in range(left, right):
            red, green, blue = pixels[x, y][:3]
            red_total += red
            green_total += green
            blue_total += blue
            count += 1

    if count == 0:
        return (0.0, 0.0, 0.0)
    return (red_total / count, green_total / count, blue_total / count)


def mean_color_for_boxes(
    image: Image.Image, boxes: Iterable[Tuple[float, float, float, float]]
) -> RGB:
    colors = list(mean_color_for_box(image, box) for box in boxes)
    if not colors:
        return (0.0, 0.0, 0.0)
    return (
        sum(color[0] for color in colors) / len(colors),
        sum(color[1] for color in colors) / len(colors),
        sum(color[2] for color in colors) / len(colors),
    )


def sample_board_cells(board_image: Image.Image, threshold: int) -> List[CellSample]:
    image = board_image.convert("RGB")
    cell_width = image.width / BOARD_SIZE
    cell_height = image.height / BOARD_SIZE
    samples: List[CellSample] = []

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            x0 = col * cell_width
            y0 = row * cell_height
            x1 = x0 + cell_width
            y1 = y0 + cell_height
            short_side = min(cell_width, cell_height)

            corner = short_side * 0.18
            inset = short_side * 0.08
            center_pad = short_side * 0.28

            corner_boxes = [
                (x0 + inset, y0 + inset, x0 + inset + corner, y0 + inset + corner),
                (x1 - inset - corner, y0 + inset, x1 - inset, y0 + inset + corner),
                (x0 + inset, y1 - inset - corner, x0 + inset + corner, y1 - inset),
                (x1 - inset - corner, y1 - inset - corner, x1 - inset, y1 - inset),
            ]
            center_box = (
                x0 + center_pad,
                y0 + center_pad,
                x1 - center_pad,
                y1 - center_pad,
            )

            background = mean_color_for_boxes(image, corner_boxes)
            center = mean_color_for_box(image, center_box)
            diff = color_distance(background, center)
            if diff >= threshold:
                samples.append(
                    CellSample(
                        row=row,
                        col=col,
                        center_color=center,
                        background_color=background,
                        diff=diff,
                        luminance=luminance(center),
                    )
                )

    return samples


def split_samples_by_color(samples: Sequence[CellSample]) -> Dict[int, List[CellSample]]:
    if not samples:
        return {0: [], 1: []}
    if len(samples) == 1:
        return {0: list(samples), 1: []}

    max_pair = (samples[0], samples[1])
    max_distance = -1.0
    for first in samples:
        for second in samples:
            distance = color_distance(first.center_color, second.center_color)
            if distance > max_distance:
                max_distance = distance
                max_pair = (first, second)

    centers = [max_pair[0].center_color, max_pair[1].center_color]
    groups: Dict[int, List[CellSample]] = {0: [], 1: []}

    for _ in range(8):
        groups = {0: [], 1: []}
        for sample in samples:
            first_distance = color_distance(sample.center_color, centers[0])
            second_distance = color_distance(sample.center_color, centers[1])
            groups[0 if first_distance <= second_distance else 1].append(sample)

        for index in (0, 1):
            if groups[index]:
                centers[index] = (
                    sum(sample.center_color[0] for sample in groups[index])
                    / len(groups[index]),
                    sum(sample.center_color[1] for sample in groups[index])
                    / len(groups[index]),
                    sum(sample.center_color[2] for sample in groups[index])
                    / len(groups[index]),
                )

    return groups


def group_mean_luminance(samples: Sequence[CellSample]) -> float:
    if not samples:
        return 0.0
    return sum(sample.luminance for sample in samples) / len(samples)


def group_mean_row(samples: Sequence[CellSample]) -> float:
    if not samples:
        return 3.5
    return sum(sample.row for sample in samples) / len(samples)


def choose_our_group(
    groups: Dict[int, List[CellSample]], our_side: str, our_color: str
) -> int:
    if not groups[0]:
        return 1
    if not groups[1]:
        return 0

    if our_color == "dark":
        return 0 if group_mean_luminance(groups[0]) <= group_mean_luminance(groups[1]) else 1
    if our_color == "light":
        return 0 if group_mean_luminance(groups[0]) >= group_mean_luminance(groups[1]) else 1

    if our_side == "bottom":
        return 0 if group_mean_row(groups[0]) >= group_mean_row(groups[1]) else 1
    return 0 if group_mean_row(groups[0]) <= group_mean_row(groups[1]) else 1


def detect_board(
    board_image: Image.Image, threshold: int, our_side: str, our_color: str
) -> Tuple[Board, List[CellSample]]:
    samples = sample_board_cells(board_image, threshold)
    groups = split_samples_by_color(samples)
    our_group = choose_our_group(groups, our_side, our_color)

    board: Board = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for group_index, group_samples in groups.items():
        owner = "ours" if group_index == our_group else "opponent"
        for sample in group_samples:
            board[sample.row][sample.col] = Piece(owner=owner)

    return board, samples


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def forward_direction(owner: str, our_side: str) -> int:
    if owner == "ours":
        return -1 if our_side == "bottom" else 1
    return 1 if our_side == "bottom" else -1


def simple_directions(piece: Piece, our_side: str) -> List[Square]:
    if piece.is_king:
        return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    direction = forward_direction(piece.owner, our_side)
    return [(direction, -1), (direction, 1)]


def capture_directions(piece: Piece, our_side: str, men_capture_backward: bool) -> List[Square]:
    if piece.is_king or men_capture_backward:
        return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    return simple_directions(piece, our_side)


def clone_board(board: Board) -> Board:
    return [
        [None if piece is None else Piece(piece.owner, piece.is_king) for piece in row]
        for row in board
    ]


def promotion_row(owner: str, our_side: str) -> int:
    if owner == "ours":
        return 0 if our_side == "bottom" else BOARD_SIZE - 1
    return BOARD_SIZE - 1 if our_side == "bottom" else 0


def maybe_promote(piece: Piece, row: int, our_side: str) -> Piece:
    if row == promotion_row(piece.owner, our_side):
        return Piece(piece.owner, True)
    return Piece(piece.owner, piece.is_king)


def find_captures_from(
    board: Board,
    start: Square,
    current: Square,
    piece: Piece,
    path: List[Square],
    captures: List[Square],
    our_side: str,
    men_capture_backward: bool,
) -> List[Move]:
    row, col = current
    moves: List[Move] = []

    for dr, dc in capture_directions(piece, our_side, men_capture_backward):
        middle = (row + dr, col + dc)
        destination = (row + dr * 2, col + dc * 2)
        if not in_bounds(*middle) or not in_bounds(*destination):
            continue

        middle_piece = board[middle[0]][middle[1]]
        destination_piece = board[destination[0]][destination[1]]
        if (
            middle_piece is None
            or middle_piece.owner == piece.owner
            or destination_piece is not None
        ):
            continue

        next_board = clone_board(board)
        next_board[start[0]][start[1]] = None
        next_board[current[0]][current[1]] = None
        next_board[middle[0]][middle[1]] = None
        moved_piece = maybe_promote(piece, destination[0], our_side)
        next_board[destination[0]][destination[1]] = moved_piece

        deeper = find_captures_from(
            next_board,
            destination,
            destination,
            moved_piece,
            path + [destination],
            captures + [middle],
            our_side,
            men_capture_backward,
        )
        if deeper:
            moves.extend(deeper)
        else:
            moves.append(Move(path=path + [destination], captures=captures + [middle]))

    return moves


def generate_moves_for_owner(
    board: Board, owner: str, our_side: str, men_capture_backward: bool
) -> List[Move]:
    captures: List[Move] = []
    simple_moves: List[Move] = []

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            piece = board[row][col]
            if piece is None or piece.owner != owner:
                continue

            captures.extend(
                find_captures_from(
                    board,
                    (row, col),
                    (row, col),
                    piece,
                    [(row, col)],
                    [],
                    our_side,
                    men_capture_backward,
                )
            )

            for dr, dc in simple_directions(piece, our_side):
                destination = (row + dr, col + dc)
                if in_bounds(*destination) and board[destination[0]][destination[1]] is None:
                    simple_moves.append(Move(path=[(row, col), destination], captures=[]))

    return captures if captures else simple_moves


def apply_move(board: Board, move: Move, our_side: str) -> Board:
    next_board = clone_board(board)
    start = move.path[0]
    destination = move.path[-1]
    piece = next_board[start[0]][start[1]]
    next_board[start[0]][start[1]] = None

    for captured in move.captures:
        next_board[captured[0]][captured[1]] = None

    if piece is not None:
        next_board[destination[0]][destination[1]] = maybe_promote(
            piece, destination[0], our_side
        )
    return next_board


def advancement_score(owner: str, row: int, our_side: str) -> float:
    if owner == "ours":
        return (BOARD_SIZE - 1 - row) if our_side == "bottom" else row
    return row if our_side == "bottom" else (BOARD_SIZE - 1 - row)


def score_move(
    board: Board, move: Move, our_side: str, men_capture_backward: bool
) -> float:
    start = move.path[0]
    destination = move.path[-1]
    piece = board[start[0]][start[1]]
    if piece is None:
        return -9999.0

    score = len(move.captures) * 100.0
    score += advancement_score(piece.owner, destination[0], our_side) * 4.0

    center_distance = abs(destination[0] - 3.5) + abs(destination[1] - 3.5)
    score += (7.0 - center_distance) * 1.5

    if not piece.is_king and destination[0] == promotion_row(piece.owner, our_side):
        score += 35.0

    next_board = apply_move(board, move, our_side)
    opponent_moves = generate_moves_for_owner(
        next_board, "opponent", our_side, men_capture_backward
    )
    opponent_capture_count = 0
    for opponent_move in opponent_moves:
        opponent_capture_count = max(opponent_capture_count, len(opponent_move.captures))
    score -= opponent_capture_count * 18.0
    return score


def best_move(
    board: Board, our_side: str, men_capture_backward: bool
) -> Optional[Move]:
    moves = generate_moves_for_owner(board, "ours", our_side, men_capture_backward)
    if not moves:
        return None

    for move in moves:
        move.score = score_move(board, move, our_side, men_capture_backward)
    return max(moves, key=lambda candidate: candidate.score)


def square_name(square: Square) -> str:
    row, col = square
    return f"{chr(ord('A') + col)}{BOARD_SIZE - row}"


def describe_move(move: Optional[Move]) -> str:
    if move is None:
        return "ไม่พบตาเดินของฝั่งเรา"

    path = " -> ".join(square_name(square) for square in move.path)
    if move.captures:
        return f"แนะนำให้กิน: {path} ({len(move.captures)} ตัว)"
    return f"แนะนำให้เดิน: {path}"


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: Tuple[float, float],
    end: Tuple[float, float],
    fill: Tuple[int, int, int],
    width: int,
) -> None:
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head_length = max(14, width * 4)
    head_angle = math.pi / 7
    left = (
        end[0] - head_length * math.cos(angle - head_angle),
        end[1] - head_length * math.sin(angle - head_angle),
    )
    right = (
        end[0] - head_length * math.cos(angle + head_angle),
        end[1] - head_length * math.sin(angle + head_angle),
    )
    draw.polygon([end, left, right], fill=fill)


def cell_center(cell_size: float, row: int, col: int) -> Tuple[float, float]:
    return (col * cell_size + cell_size / 2, row * cell_size + cell_size / 2)


def annotate_board(board_image: Image.Image, board: Board, move: Optional[Move]) -> Image.Image:
    base = board_image.convert("RGBA")
    side = min(base.width, base.height)
    base = base.crop((0, 0, side, side))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cell = side / BOARD_SIZE
    font = ImageFont.load_default()

    for index in range(BOARD_SIZE + 1):
        position = int(round(index * cell))
        draw.line([(position, 0), (position, side)], fill=GRID_COLOR, width=1)
        draw.line([(0, position), (side, position)], fill=GRID_COLOR, width=1)

    legend_pad = max(8, int(cell * 0.12))
    legend_h = max(22, int(cell * 0.25))
    legend_w = max(128, int(cell * 1.8))
    draw.rounded_rectangle(
        (legend_pad, legend_pad, legend_pad + legend_w, legend_pad + legend_h * 2 + 8),
        radius=6,
        fill=(20, 24, 30, 210),
    )
    draw.ellipse(
        (
            legend_pad + 8,
            legend_pad + 6,
            legend_pad + 8 + legend_h - 8,
            legend_pad + legend_h - 2,
        ),
        fill=OUR_COLOR + (230,),
    )
    draw.text(
        (legend_pad + legend_h + 10, legend_pad + 5),
        "OUR",
        fill=(255, 255, 255, 255),
        font=font,
    )
    draw.ellipse(
        (
            legend_pad + 8,
            legend_pad + legend_h + 10,
            legend_pad + 8 + legend_h - 8,
            legend_pad + legend_h * 2 + 2,
        ),
        fill=OPPONENT_COLOR + (230,),
    )
    draw.text(
        (legend_pad + legend_h + 10, legend_pad + legend_h + 9),
        "OPP",
        fill=(255, 255, 255, 255),
        font=font,
    )

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            piece = board[row][col]
            if piece is None:
                continue

            center_x, center_y = cell_center(cell, row, col)
            radius = cell * 0.34
            color = OUR_COLOR if piece.owner == "ours" else OPPONENT_COLOR
            draw.ellipse(
                (
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                ),
                fill=color + (80,),
                outline=color + (255,),
                width=max(3, int(cell * 0.055)),
            )
            if piece.is_king:
                draw.text(
                    (center_x - cell * 0.08, center_y - cell * 0.12),
                    "K",
                    fill=(255, 255, 255, 255),
                    font=font,
                )

    if move is not None and len(move.path) >= 2:
        start_row, start_col = move.path[0]
        end_row, end_col = move.path[-1]
        start_center = cell_center(cell, start_row, start_col)
        end_center = cell_center(cell, end_row, end_col)
        ring_radius = cell * 0.42
        draw.ellipse(
            (
                start_center[0] - ring_radius,
                start_center[1] - ring_radius,
                start_center[0] + ring_radius,
                start_center[1] + ring_radius,
            ),
            outline=MOVE_COLOR + (255,),
            width=max(4, int(cell * 0.08)),
        )
        draw.rectangle(
            (
                end_col * cell + cell * 0.08,
                end_row * cell + cell * 0.08,
                (end_col + 1) * cell - cell * 0.08,
                (end_row + 1) * cell - cell * 0.08,
            ),
            outline=DEST_COLOR + (255,),
            width=max(4, int(cell * 0.07)),
        )

        for first, second in zip(move.path, move.path[1:]):
            first_center = cell_center(cell, first[0], first[1])
            second_center = cell_center(cell, second[0], second[1])
            draw_arrow(
                draw,
                first_center,
                second_center,
                MOVE_COLOR,
                max(4, int(cell * 0.07)),
            )

        for captured_row, captured_col in move.captures:
            captured_center = cell_center(cell, captured_row, captured_col)
            x, y = captured_center
            size = cell * 0.26
            draw.line(
                [(x - size, y - size), (x + size, y + size)],
                fill=CAPTURE_COLOR + (255,),
                width=max(4, int(cell * 0.06)),
            )
            draw.line(
                [(x + size, y - size), (x - size, y + size)],
                fill=CAPTURE_COLOR + (255,),
                width=max(4, int(cell * 0.06)),
            )

    return Image.alpha_composite(base, overlay).convert("RGB")


class CheckersAdvisorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ตัวช่วยหมากฮอส")
        self.root.geometry("1180x760")
        self.root.minsize(940, 620)

        self.screenshot: Optional[Image.Image] = None
        self.screenshot_origin = (0, 0)
        self.result_image: Optional[Image.Image] = None
        self.screen_photo: Optional[ImageTk.PhotoImage] = None
        self.result_photo: Optional[ImageTk.PhotoImage] = None
        self.screen_scale = 1.0
        self.screen_offset = (0, 0)
        self.selection_display: Optional[Tuple[float, float, float, float]] = None
        self.selection_image: Optional[Tuple[int, int, int, int]] = None
        self.drag_start: Optional[Tuple[float, float]] = None
        self.start_realtime_on_selection = False
        self.realtime_running = False
        self.realtime_after_id: Optional[str] = None
        self.last_realtime_error = ""

        self.status_var = tk.StringVar(value="พร้อมใช้งาน")
        self.our_side_var = tk.StringVar(value="ล่าง")
        self.our_color_var = tk.StringVar(value="อัตโนมัติ")
        self.threshold_var = tk.IntVar(value=60)
        self.monitor_var = tk.IntVar(value=0)
        self.interval_var = tk.IntVar(value=700)
        self.backward_capture_var = tk.BooleanVar(value=False)
        self.realtime_button_text = tk.StringVar(value="เริ่มเรียลไทม์")

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self) -> None:
        style = ttk.Style()
        style.configure("Toolbar.TFrame", padding=8)
        style.configure("Status.TLabel", padding=(8, 4))

        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame")
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="เลือกพื้นที่หน้าจอ", command=self.select_live_region_clicked).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="จับภาพนิ่ง", command=self.capture_clicked).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="เปิดภาพ", command=self.open_image).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="วิเคราะห์", command=self.analyze_selection).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(
            toolbar,
            textvariable=self.realtime_button_text,
            command=self.toggle_realtime,
        ).pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Button(toolbar, text="บันทึกภาพ", command=self.save_result).pack(
            side=tk.LEFT, padx=(0, 12)
        )

        ttk.Label(toolbar, text="จอ").pack(side=tk.LEFT)
        ttk.Spinbox(
            toolbar,
            from_=0,
            to=8,
            width=3,
            textvariable=self.monitor_var,
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(toolbar, text="รีเฟรช ms").pack(side=tk.LEFT)
        ttk.Spinbox(
            toolbar,
            from_=250,
            to=3000,
            increment=50,
            width=5,
            textvariable=self.interval_var,
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(toolbar, text="เราอยู่").pack(side=tk.LEFT)
        ttk.Combobox(
            toolbar,
            width=7,
            values=("ล่าง", "บน"),
            textvariable=self.our_side_var,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(toolbar, text="สีเรา").pack(side=tk.LEFT)
        ttk.Combobox(
            toolbar,
            width=10,
            values=("อัตโนมัติ", "สีเข้ม", "สีอ่อน"),
            textvariable=self.our_color_var,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Checkbutton(
            toolbar,
            text="กินถอยหลัง",
            variable=self.backward_capture_var,
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(toolbar, text="ความไว").pack(side=tk.LEFT)
        ttk.Scale(
            toolbar,
            from_=20,
            to=85,
            orient=tk.HORIZONTAL,
            variable=self.threshold_var,
            length=120,
        ).pack(side=tk.LEFT, padx=(4, 0))

        panes = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        left_frame = ttk.Frame(panes)
        right_frame = ttk.Frame(panes)
        panes.add(left_frame, weight=3)
        panes.add(right_frame, weight=2)

        ttk.Label(left_frame, text="หน้าจอ").pack(anchor=tk.W)
        self.screen_canvas = tk.Canvas(
            left_frame,
            bg="#171a21",
            highlightthickness=0,
            width=700,
            height=620,
        )
        self.screen_canvas.pack(fill=tk.BOTH, expand=True)
        self.screen_canvas.bind("<ButtonPress-1>", self.on_screen_press)
        self.screen_canvas.bind("<B1-Motion>", self.on_screen_drag)
        self.screen_canvas.bind("<ButtonRelease-1>", self.on_screen_release)
        self.screen_canvas.bind("<Configure>", lambda _event: self.redraw_screenshot())

        ttk.Label(right_frame, text="ภาพแนะนำ").pack(anchor=tk.W)
        self.result_canvas = tk.Canvas(
            right_frame,
            bg="#11151b",
            highlightthickness=0,
            width=420,
            height=620,
        )
        self.result_canvas.pack(fill=tk.BOTH, expand=True)
        self.result_canvas.bind("<Configure>", lambda _event: self.redraw_result())

        status = ttk.Label(self.root, textvariable=self.status_var, style="Status.TLabel")
        status.pack(side=tk.BOTTOM, fill=tk.X)

        self.redraw_screenshot()
        self.redraw_result()

    def side_value(self) -> str:
        return "bottom" if self.our_side_var.get() == "ล่าง" else "top"

    def color_value(self) -> str:
        value = self.our_color_var.get()
        if value == "สีเข้ม":
            return "dark"
        if value == "สีอ่อน":
            return "light"
        return "auto"

    def select_live_region_clicked(self) -> None:
        self.prepare_screen_selection(auto_start_realtime=True)

    def capture_clicked(self) -> None:
        self.prepare_screen_selection(auto_start_realtime=False)

    def prepare_screen_selection(self, auto_start_realtime: bool) -> None:
        self.stop_realtime(status=False)
        self.start_realtime_on_selection = auto_start_realtime
        self.status_var.set("กำลังจับหน้าจอ...")
        self.root.update_idletasks()
        self.root.withdraw()
        self.root.after(450, self.capture_after_hide)

    def capture_after_hide(self) -> None:
        try:
            capture = capture_screen(self.monitor_var.get())
            self.screenshot = capture.image
            self.screenshot_origin = (capture.left, capture.top)
            self.selection_display = None
            self.selection_image = None
            self.result_image = None
            if self.start_realtime_on_selection:
                self.status_var.set("ลากเลือกกระดาน 8x8 แล้วจะเริ่มเรียลไทม์ทันที")
            else:
                self.status_var.set("จับภาพนิ่งแล้ว ลากเลือกกระดาน 8x8")
        except Exception as exc:
            messagebox.showerror("จับหน้าจอไม่สำเร็จ", str(exc))
            self.status_var.set("จับหน้าจอไม่สำเร็จ")
            self.start_realtime_on_selection = False
        finally:
            self.root.deiconify()
            self.root.lift()
            self.redraw_screenshot()
            self.redraw_result()

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            title="เปิดภาพ",
            filetypes=(
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All files", "*.*"),
            ),
        )
        if not path:
            return
        try:
            self.stop_realtime(status=False)
            self.screenshot = Image.open(path).convert("RGB")
            self.screenshot_origin = (0, 0)
            self.selection_display = None
            self.selection_image = None
            self.result_image = None
            self.status_var.set(f"เปิดภาพแล้ว: {path}")
            self.redraw_screenshot()
            self.redraw_result()
        except Exception as exc:
            messagebox.showerror("เปิดภาพไม่สำเร็จ", str(exc))

    def save_result(self) -> None:
        if self.result_image is None:
            messagebox.showinfo("ยังไม่มีภาพ", "ยังไม่มีภาพแนะนำให้บันทึก")
            return
        path = filedialog.asksaveasfilename(
            title="บันทึกภาพ",
            defaultextension=".png",
            filetypes=(("PNG image", "*.png"), ("All files", "*.*")),
        )
        if not path:
            return
        self.result_image.save(path)
        self.status_var.set(f"บันทึกภาพแล้ว: {path}")

    def redraw_screenshot(self) -> None:
        canvas = self.screen_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)

        if self.screenshot is None:
            canvas.create_text(
                width / 2,
                height / 2,
                text="เลือกพื้นที่หน้าจอหรือเปิดภาพ",
                fill="#d8dee9",
                font=("Helvetica", 16),
            )
            return

        scale = min(width / self.screenshot.width, height / self.screenshot.height)
        scale = min(scale, 1.0)
        display_width = max(1, int(self.screenshot.width * scale))
        display_height = max(1, int(self.screenshot.height * scale))
        offset_x = int((width - display_width) / 2)
        offset_y = int((height - display_height) / 2)
        self.screen_scale = scale
        self.screen_offset = (offset_x, offset_y)

        display_image = self.screenshot.resize(
            (display_width, display_height), Image.Resampling.LANCZOS
        )
        self.screen_photo = ImageTk.PhotoImage(display_image)
        canvas.create_image(offset_x, offset_y, anchor=tk.NW, image=self.screen_photo)

        if self.selection_image is not None:
            self.selection_display = self.image_rect_to_display_rect(self.selection_image)
            x0, y0, x1, y1 = self.selection_display
            canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                outline="#ffd60a",
                width=3,
            )
            canvas.create_rectangle(
                x0 + 4,
                y0 + 4,
                x1 - 4,
                y1 - 4,
                outline="#2979ff",
                width=1,
            )

    def redraw_result(self) -> None:
        canvas = self.result_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)

        if self.result_image is None:
            canvas.create_text(
                width / 2,
                height / 2,
                text="ภาพแนะนำจะแสดงที่นี่",
                fill="#d8dee9",
                font=("Helvetica", 16),
            )
            return

        scale = min(width / self.result_image.width, height / self.result_image.height)
        scale = min(scale, 1.0)
        display_width = max(1, int(self.result_image.width * scale))
        display_height = max(1, int(self.result_image.height * scale))
        offset_x = int((width - display_width) / 2)
        offset_y = int((height - display_height) / 2)
        display_image = self.result_image.resize(
            (display_width, display_height), Image.Resampling.LANCZOS
        )
        self.result_photo = ImageTk.PhotoImage(display_image)
        canvas.create_image(offset_x, offset_y, anchor=tk.NW, image=self.result_photo)

    def display_point_to_image(self, x: float, y: float) -> Tuple[float, float]:
        offset_x, offset_y = self.screen_offset
        return ((x - offset_x) / self.screen_scale, (y - offset_y) / self.screen_scale)

    def image_rect_to_display_rect(
        self, rect: Tuple[int, int, int, int]
    ) -> Tuple[float, float, float, float]:
        offset_x, offset_y = self.screen_offset
        left, top, right, bottom = rect
        return (
            offset_x + left * self.screen_scale,
            offset_y + top * self.screen_scale,
            offset_x + right * self.screen_scale,
            offset_y + bottom * self.screen_scale,
        )

    def clamp_to_display_image(self, x: float, y: float) -> Tuple[float, float]:
        if self.screenshot is None:
            return x, y
        offset_x, offset_y = self.screen_offset
        image_width = self.screenshot.width * self.screen_scale
        image_height = self.screenshot.height * self.screen_scale
        return (
            max(offset_x, min(offset_x + image_width, x)),
            max(offset_y, min(offset_y + image_height, y)),
        )

    def on_screen_press(self, event: tk.Event) -> None:
        if self.screenshot is None:
            return
        self.stop_realtime(status=False)
        self.drag_start = self.clamp_to_display_image(event.x, event.y)
        self.selection_display = None
        self.selection_image = None

    def on_screen_drag(self, event: tk.Event) -> None:
        if self.screenshot is None or self.drag_start is None:
            return
        current = self.clamp_to_display_image(event.x, event.y)
        x0, y0, x1, y1 = self.square_display_rect(self.drag_start, current)
        self.selection_display = (x0, y0, x1, y1)
        self.selection_image = self.display_rect_to_image_rect(self.selection_display)
        self.redraw_screenshot()

    def on_screen_release(self, event: tk.Event) -> None:
        self.on_screen_drag(event)
        if self.selection_image is not None:
            x0, y0, x1, y1 = self.selection_image
            if min(x1 - x0, y1 - y0) < 80:
                self.status_var.set("กรอบกระดานเล็กเกินไป")
                self.start_realtime_on_selection = False
                return
            self.status_var.set(f"เลือกกระดานแล้ว: {x1 - x0}x{y1 - y0}px")
            if self.start_realtime_on_selection:
                self.start_realtime_on_selection = False
                self.start_realtime()

    def square_display_rect(
        self, start: Tuple[float, float], end: Tuple[float, float]
    ) -> Tuple[float, float, float, float]:
        start_x, start_y = start
        end_x, end_y = end
        dx = end_x - start_x
        dy = end_y - start_y
        side = min(abs(dx), abs(dy))
        if side < 1:
            side = max(abs(dx), abs(dy), 1)
        x1 = start_x + side * (1 if dx >= 0 else -1)
        y1 = start_y + side * (1 if dy >= 0 else -1)
        x0, x1 = sorted((start_x, x1))
        y0, y1 = sorted((start_y, y1))
        return x0, y0, x1, y1

    def display_rect_to_image_rect(
        self, rect: Tuple[float, float, float, float]
    ) -> Tuple[int, int, int, int]:
        x0, y0 = self.display_point_to_image(rect[0], rect[1])
        x1, y1 = self.display_point_to_image(rect[2], rect[3])
        if self.screenshot is None:
            return (0, 0, 0, 0)
        left = max(0, min(self.screenshot.width - 1, int(round(min(x0, x1)))))
        top = max(0, min(self.screenshot.height - 1, int(round(min(y0, y1)))))
        right = max(left + 1, min(self.screenshot.width, int(round(max(x0, x1)))))
        bottom = max(top + 1, min(self.screenshot.height, int(round(max(y0, y1)))))
        side = min(right - left, bottom - top)
        return (left, top, left + side, top + side)

    def selected_screen_rect(self) -> Optional[Tuple[int, int, int, int]]:
        if self.selection_image is None:
            return None
        origin_x, origin_y = self.screenshot_origin
        left, top, right, bottom = self.selection_image
        return (
            origin_x + left,
            origin_y + top,
            origin_x + right,
            origin_y + bottom,
        )

    def analyze_board_image(
        self, board_image: Image.Image, realtime: bool = False
    ) -> Tuple[int, Optional[Move], List[CellSample]]:
        threshold = max(15, 105 - int(round(float(self.threshold_var.get()))))
        board, samples = detect_board(
            board_image,
            threshold,
            self.side_value(),
            self.color_value(),
        )
        move = best_move(
            board,
            self.side_value(),
            self.backward_capture_var.get(),
        )
        self.result_image = annotate_board(board_image, board, move)
        pieces = sum(1 for row in board for piece in row if piece is not None)

        if not samples:
            self.status_var.set("ไม่พบหมาก ลองเพิ่มค่า ความไว หรือเลือกกรอบใหม่")
        else:
            prefix = "เรียลไทม์" if realtime else "ภาพนิ่ง"
            self.status_var.set(f"{prefix}: {describe_move(move)} | พบหมาก {pieces} ตัว")

        self.redraw_result()
        return pieces, move, samples

    def analyze_selection(self) -> None:
        if self.screenshot is None:
            messagebox.showinfo("ยังไม่มีภาพ", "กรุณาจับหน้าจอหรือเปิดภาพก่อน")
            return
        if self.selection_image is None:
            messagebox.showinfo("ยังไม่ได้เลือกกระดาน", "ลากกรอบรอบกระดานก่อน")
            return

        left, top, right, bottom = self.selection_image
        board_image = self.screenshot.crop((left, top, right, bottom)).convert("RGB")
        self.analyze_board_image(board_image, realtime=False)

    def toggle_realtime(self) -> None:
        if self.realtime_running:
            self.stop_realtime(status=True)
        else:
            self.start_realtime()

    def start_realtime(self) -> None:
        if self.selected_screen_rect() is None:
            messagebox.showinfo("ยังไม่ได้เลือกกระดาน", "เลือกพื้นที่หน้าจอก่อน")
            return

        self.stop_realtime(status=False)
        self.realtime_running = True
        self.last_realtime_error = ""
        self.realtime_button_text.set("หยุดเรียลไทม์")
        self.status_var.set("เริ่มวิเคราะห์แบบเรียลไทม์")
        self.run_realtime_tick()

    def stop_realtime(self, status: bool = True) -> None:
        if self.realtime_after_id is not None:
            self.root.after_cancel(self.realtime_after_id)
            self.realtime_after_id = None
        was_running = self.realtime_running
        self.realtime_running = False
        self.realtime_button_text.set("เริ่มเรียลไทม์")
        if status and was_running:
            self.status_var.set("หยุดเรียลไทม์แล้ว")

    def run_realtime_tick(self) -> None:
        if not self.realtime_running:
            return

        try:
            screen_rect = self.selected_screen_rect()
            if screen_rect is None:
                self.stop_realtime(status=False)
                self.status_var.set("หยุดเรียลไทม์: ยังไม่ได้เลือกกระดาน")
                return

            board_image = capture_screen_region(screen_rect).convert("RGB")
            self.analyze_board_image(board_image, realtime=True)
            self.last_realtime_error = ""
        except Exception as exc:
            message = str(exc)
            if message != self.last_realtime_error:
                self.status_var.set(f"เรียลไทม์ผิดพลาด: {message}")
                self.last_realtime_error = message

        if self.realtime_running:
            delay = max(250, int(self.interval_var.get()))
            self.realtime_after_id = self.root.after(delay, self.run_realtime_tick)

    def close(self) -> None:
        self.stop_realtime(status=False)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = CheckersAdvisorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
