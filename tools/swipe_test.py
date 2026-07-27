"""测试 WindowsController 的窗口滑动方式。

用法：
    python tools/swipe_test.py --window-title 雷霆战机：集结 --x1 360 --y1 1030 --x2 360 --y2 520 --duration 0.5 --press-delay 0.12 --release-delay 0.28 --click-method message
    python tools/swipe_test.py --window-title 雷霆战机：集结 --x1 360 --y1 1030 --x2 360 --y2 520 --duration 0.5 --press-delay 0.12 --release-delay 0.28 --click-method foreground
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    DEFAULT_CAPTURE_METHOD,
    DEFAULT_CLICK_METHOD,
    DEFAULT_FORCE_CLIENT_SIZE,
    DEFAULT_WINDOW_TITLE,
    TARGET_CLIENT_HEIGHT,
    TARGET_CLIENT_WIDTH,
)
from windows_controller import WindowsController


def main() -> None:
    parser = argparse.ArgumentParser(description="测试对窗口客户区坐标的滑动")
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE)
    parser.add_argument("--capture-method", choices=["printwindow", "mss"], default=DEFAULT_CAPTURE_METHOD)
    parser.add_argument("--click-method", choices=["message", "foreground"], default=DEFAULT_CLICK_METHOD)
    parser.add_argument("--no-force-client-size", dest="force_client_size", action="store_false", default=DEFAULT_FORCE_CLIENT_SIZE, help="滑动前不自动调整客户区尺寸")
    parser.add_argument("--client-width", type=int, default=TARGET_CLIENT_WIDTH, help="目标客户区宽度，默认720")
    parser.add_argument("--client-height", type=int, default=TARGET_CLIENT_HEIGHT, help="目标客户区高度，默认1280")
    parser.add_argument("--x1", type=float, required=True)
    parser.add_argument("--y1", type=float, required=True)
    parser.add_argument("--x2", type=float, required=True)
    parser.add_argument("--y2", type=float, required=True)
    parser.add_argument("--duration", type=float, default=0.5, help="滑动持续时间，秒")
    parser.add_argument("--press-delay", type=float, default=0.12, help="按下后到开始滑动前的等待时间，秒")
    parser.add_argument("--release-delay", type=float, default=0.28, help="滑动到终点后到抬起前的等待时间，秒")
    args = parser.parse_args()

    ctrl = WindowsController(
        window_title=args.window_title,
        capture_method=args.capture_method,
        click_method=args.click_method,
        client_width=args.client_width,
        client_height=args.client_height,
        force_client_size=args.force_client_size,
    )
    ctrl.swipe(
        args.x1,
        args.y1,
        args.x2,
        args.y2,
        duration=args.duration,
        press_delay=args.press_delay,
        release_delay=args.release_delay,
        delay=0.5,
    )
    print(
        f"swiped client=({args.x1}, {args.y1}) -> ({args.x2}, {args.y2}) "
        f"duration={args.duration}s press_delay={args.press_delay}s "
        f"release_delay={args.release_delay}s by {args.click_method}"
    )


if __name__ == "__main__":
    main()
