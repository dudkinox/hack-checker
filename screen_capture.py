#!/usr/bin/env python3
"""Capture screenshots from the command line."""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import mss
import mss.tools


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def output_path(target: Optional[str], index: Optional[int] = None) -> Path:
    if target:
        path = Path(target)
        if path.suffix:
            if index is not None:
                return path.with_name(f"{path.stem}-{index:03d}{path.suffix}")
            return path
        name = f"screenshot-{timestamp()}"
        if index is not None:
            name += f"-{index:03d}"
        return path / f"{name}.png"

    name = f"screenshot-{timestamp()}"
    if index is not None:
        name += f"-{index:03d}"
    return Path(f"{name}.png")


def capture_once(target: Optional[str], monitor_number: int, index: Optional[int] = None) -> Path:
    with mss.mss() as screenshotter:
        if monitor_number >= len(screenshotter.monitors):
            raise ValueError(
                f"Monitor {monitor_number} not found. "
                f"Available monitors: 0-{len(screenshotter.monitors) - 1}"
            )

        monitor = screenshotter.monitors[monitor_number]
        image = screenshotter.grab(monitor)
        path = output_path(target, index)
        path.parent.mkdir(parents=True, exist_ok=True)
        mss.tools.to_png(image.rgb, image.size, output=str(path))
        return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the screen and save it as PNG."
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file or folder. Defaults to screenshot-YYYYMMDD-HHMMSS.png.",
    )
    parser.add_argument(
        "-m",
        "--monitor",
        type=int,
        default=0,
        help="Monitor number. Use 0 for all monitors, 1 for primary. Default: 0.",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=0,
        help="Seconds between captures. Set this for repeated screenshots.",
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=1,
        help="Number of screenshots to capture. Use 0 to run until stopped.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.interval <= 0:
        saved = capture_once(args.output, args.monitor)
        print(f"Saved: {saved}")
        return

    current = 0
    while args.count == 0 or current < args.count:
        current += 1
        saved = capture_once(args.output, args.monitor, current)
        print(f"Saved: {saved}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
